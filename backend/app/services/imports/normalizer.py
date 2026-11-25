import datetime as dt
import hashlib
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from openpyxl.utils.datetime import from_excel

SUPPORTED_CURRENCIES = {"INR"}

INDIAN_AUTO_DATE_FORMATS = [
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d-%b-%Y",
    "%d %b %Y",
    "%d-%B-%Y",
    "%d %B %Y",
    "%d/%m/%y",
    "%d-%m-%y",
    "%m/%d/%Y",
]

DATE_FORMAT_MAP = {
    "DD/MM/YYYY": ["%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y"],
    "DD-MM-YYYY": ["%d-%m-%Y", "%d/%m/%Y", "%d-%m-%y", "%d/%m/%y"],
    "YYYY-MM-DD": ["%Y-%m-%d", "%Y/%m/%d"],
    "DD MMM YYYY": ["%d %b %Y", "%d-%b-%Y", "%d %B %Y", "%d-%B-%Y"],
    "MM/DD/YYYY": ["%m/%d/%Y", "%m-%d-%Y"],
}


@dataclass
class NormalizedRowResult:
    normalized_date: dt.date | None
    normalized_description: str | None
    normalized_merchant: str | None
    normalized_notes: str | None
    normalized_amount: Decimal | None
    normalized_type: str | None  # income, expense
    currency: str
    transaction_reference: str | None
    running_balance: Decimal | None
    row_fingerprint: str | None
    validation_status: str  # valid, invalid, needs_review
    validation_errors: list[str]


def canonicalize_description(desc: str | None) -> str:
    """Produces a deterministic canonical string for matching while keeping raw text untouched."""
    if not desc:
        return ""
    lowered = desc.lower().strip()
    cleaned = re.sub(r"[^a-z0-9\s]+", " ", lowered)
    return re.sub(r"\s+", " ", cleaned).strip()


def compute_row_fingerprint(
    tx_date: dt.date | None,
    amount: Decimal | None,
    tx_type: str | None,
    description: str | None,
) -> str | None:
    if tx_date is None or amount is None or not tx_type:
        return None
    canonical_desc = canonicalize_description(description)
    payload = f"{tx_date.isoformat()}|{amount:.2f}|{tx_type}|{canonical_desc}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def parse_indian_date(raw_val: Any, date_format: str = "auto") -> tuple[dt.date | None, str | None]:
    """Parses strings (with Indian DD/MM/YYYY priority), date objects, or Excel serial numbers."""
    if raw_val is None or str(raw_val).strip() == "":
        return None, "Missing transaction date."

    if isinstance(raw_val, dt.datetime):
        return raw_val.date(), None
    if isinstance(raw_val, dt.date):
        return raw_val, None

    # Excel numeric serial date check (e.g. 46351 -> 2026-11-25)
    if isinstance(raw_val, (int, float)) and not isinstance(raw_val, bool):
        if 1 <= raw_val <= 100000:
            try:
                converted = from_excel(raw_val)
                return converted.date() if isinstance(converted, dt.datetime) else converted, None
            except Exception:
                return None, f"Invalid Excel serial date '{raw_val}'."
        return None, f"Unrecognized numeric date '{raw_val}'."

    text = str(raw_val).strip()
    # Handle numeric serial passed as string from JSON
    if re.fullmatch(r"\d{5}(?:\.\d+)?", text):
        serial = float(text)
        if 20000 <= serial <= 90000:
            try:
                converted = from_excel(serial)
                return converted.date() if isinstance(converted, dt.datetime) else converted, None
            except Exception:
                pass

    # Strip timestamp tail if ISO datetime or space-separated time
    date_part = text.split("T")[0].strip()
    if re.match(r"^\d{2,4}[-/]\d{2}[-/]\d{2,4}\s+\d{2}:\d{2}", date_part):
        date_part = date_part.split()[0]

    formats = DATE_FORMAT_MAP.get(date_format, INDIAN_AUTO_DATE_FORMATS)
    for fmt in formats:
        try:
            return dt.datetime.strptime(date_part, fmt).date(), None
        except ValueError:
            continue

    return None, f"Invalid transaction date '{text}' (expected {date_format})."


def parse_decimal_amount(raw_val: Any) -> tuple[Decimal | None, str | None, str | None]:
    """
    Strictly converts monetary strings/numbers into Decimal(0.01).
    Returns (Decimal | None, dr_cr_hint | None, error_message | None).
    Never silently coerces malformed input to 0.
    """
    if raw_val is None:
        return None, None, None
    if isinstance(raw_val, Decimal):
        if raw_val.is_nan() or raw_val.is_infinite():
            return None, None, "Malformed numeric amount."
        return raw_val.quantize(Decimal("0.01")), None, None
    if isinstance(raw_val, (int, float)) and not isinstance(raw_val, bool):
        try:
            d = Decimal(str(raw_val))
            if d.is_nan() or d.is_infinite():
                return None, None, "Malformed numeric amount."
            return d.quantize(Decimal("0.01")), None, None
        except InvalidOperation:
            return None, None, f"Malformed amount '{raw_val}'."

    text = str(raw_val).strip()
    if text == "" or text in {"-", "--"}:
        return None, None, None

    hint: str | None = None
    upper = text.upper()
    if re.search(r"\bDR\.?$", upper):
        hint = "dr"
        text = re.sub(r"(?i)\bDR\.?$", "", text).strip()
    elif re.search(r"\bCR\.?$", upper):
        hint = "cr"
        text = re.sub(r"(?i)\bCR\.?$", "", text).strip()

    is_paren_negative = False
    if text.startswith("(") and text.endswith(")"):
        is_paren_negative = True
        text = text[1:-1].strip()

    # Strip INR currency prefixes, spaces, commas
    text = re.sub(r"(?i)(₹|INR|Rs\.?|\s|,)", "", text)
    if not text:
        return None, hint, None

    if not re.fullmatch(r"[+-]?\d+(?:\.\d+)?", text):
        return None, hint, f"Malformed monetary amount '{raw_val}'."

    try:
        dec = Decimal(text)
    except InvalidOperation:
        return None, hint, f"Malformed monetary amount '{raw_val}'."

    if dec.is_nan() or dec.is_infinite():
        return None, hint, "Invalid numeric amount."

    if is_paren_negative and dec > Decimal("0.00"):
        dec = -dec

    return dec.quantize(Decimal("0.01")), hint, None


def normalize_row(raw_row: dict[str, Any], mapping: dict[str, Any]) -> NormalizedRowResult:
    """Normalizes and deterministically validates one raw statement row against confirmed mapping."""
    errors: list[str] = []
    needs_review = False

    date_col = mapping.get("date_column")
    desc_col = mapping.get("description_column")
    amount_mode = mapping.get("amount_mode", "single")
    amount_col = mapping.get("amount_column")
    debit_col = mapping.get("debit_column")
    credit_col = mapping.get("credit_column")
    type_col = mapping.get("type_column")
    sign_convention = mapping.get("sign_convention", "negative_is_expense")
    ref_col = mapping.get("reference_column")
    bal_col = mapping.get("balance_column")
    merch_col = mapping.get("merchant_column")
    notes_col = mapping.get("notes_column")
    curr_col = mapping.get("currency_column")
    date_format = mapping.get("date_format", "auto")
    default_currency = str(mapping.get("default_currency") or "INR").strip().upper()

    # 1. Currency
    raw_curr = raw_row.get(curr_col) if curr_col else None
    currency = str(raw_curr).strip().upper() if raw_curr and str(raw_curr).strip() else default_currency
    if currency not in SUPPORTED_CURRENCIES:
        errors.append(f"Unsupported currency '{currency}'. Only INR is supported in Phase 3.")

    # 2. Transaction Date
    raw_date = raw_row.get(date_col) if date_col else None
    norm_date, date_err = parse_indian_date(raw_date, date_format=date_format)
    if date_err:
        errors.append(date_err)

    # 3. Description
    raw_desc = raw_row.get(desc_col) if desc_col else None
    norm_desc = str(raw_desc).strip() if raw_desc is not None else ""
    if not norm_desc:
        errors.append("Missing transaction description.")
        norm_desc_val: str | None = None
    else:
        norm_desc_val = norm_desc[:255]

    # 4. Optional metadata fields
    raw_ref = raw_row.get(ref_col) if ref_col else None
    norm_ref = str(raw_ref).strip()[:100] if raw_ref is not None and str(raw_ref).strip() else None

    raw_merch = raw_row.get(merch_col) if merch_col else None
    norm_merch = (
        str(raw_merch).strip()[:150] if raw_merch is not None and str(raw_merch).strip() else None
    )

    raw_notes = raw_row.get(notes_col) if notes_col else None
    norm_notes = str(raw_notes).strip() if raw_notes is not None and str(raw_notes).strip() else None

    raw_bal = raw_row.get(bal_col) if bal_col else None
    norm_bal: Decimal | None = None
    if raw_bal is not None and str(raw_bal).strip() != "":
        bal_dec, _, bal_err = parse_decimal_amount(raw_bal)
        if bal_err:
            # Running balance parsing failure does not break row if valid, or note warning
            needs_review = True
            errors.append(f"Running balance could not be parsed: {bal_err}")
        else:
            norm_bal = bal_dec

    # 5. Amount & Debit/Credit interpretation
    norm_amount: Decimal | None = None
    norm_type: str | None = None

    if amount_mode == "split":
        debit_val, _, debit_err = parse_decimal_amount(
            raw_row.get(debit_col) if debit_col else None
        )
        credit_val, _, credit_err = parse_decimal_amount(
            raw_row.get(credit_col) if credit_col else None
        )
        if debit_err:
            errors.append(f"Debit column: {debit_err}")
        if credit_err:
            errors.append(f"Credit column: {credit_err}")

        if not debit_err and not credit_err:
            has_debit = debit_val is not None and debit_val != Decimal("0.00")
            has_credit = credit_val is not None and credit_val != Decimal("0.00")

            if has_debit and has_credit:
                needs_review = True
                errors.append(
                    "Ambiguous debit/credit interpretation: both Debit and Credit columns have non-zero values."
                )
            elif not has_debit and not has_credit:
                errors.append("Missing or zero transaction amount in both Debit and Credit columns.")
            elif has_debit and debit_val is not None:
                norm_amount = abs(debit_val)
                norm_type = "expense"
            elif has_credit and credit_val is not None:
                norm_amount = abs(credit_val)
                norm_type = "income"
    else:
        raw_amt = raw_row.get(amount_col) if amount_col else None
        amt_dec, amt_hint, amt_err = parse_decimal_amount(raw_amt)
        if amt_err:
            errors.append(amt_err)
        elif amt_dec is None or amt_dec == Decimal("0.00"):
            errors.append("Missing or zero monetary amount.")
        else:
            norm_amount = abs(amt_dec)
            type_indicator = (
                str(raw_row.get(type_col)).strip().lower()
                if type_col and raw_row.get(type_col) is not None
                else ""
            )

            if type_indicator in {"dr", "debit", "withdrawal", "expense", "d"} or amt_hint == "dr":
                norm_type = "expense"
            elif type_indicator in {"cr", "credit", "deposit", "income", "c"} or amt_hint == "cr":
                norm_type = "income"
            elif type_indicator:
                needs_review = True
                errors.append(
                    f"Ambiguous debit/credit type indicator '{type_indicator}'."
                )
            else:
                # Infer from sign using explicitly confirmed sign_convention
                if sign_convention == "positive_is_expense":
                    norm_type = "expense" if amt_dec > Decimal("0.00") else "income"
                else:
                    # negative_is_expense
                    norm_type = "expense" if amt_dec < Decimal("0.00") else "income"

    fingerprint = compute_row_fingerprint(norm_date, norm_amount, norm_type, norm_desc_val)

    # Determine validation status
    hard_invalid = (
        norm_date is None
        or norm_desc_val is None
        or norm_amount is None
        or norm_amount <= Decimal("0.00")
        or currency not in SUPPORTED_CURRENCIES
        or (norm_type is None and not needs_review)
    )
    if hard_invalid:
        v_status = "invalid"
    elif needs_review or norm_type is None:
        v_status = "needs_review"
    elif errors:
        # e.g. unparseable optional balance warning
        v_status = "needs_review"
    else:
        v_status = "valid"

    return NormalizedRowResult(
        normalized_date=norm_date,
        normalized_description=norm_desc_val,
        normalized_merchant=norm_merch,
        normalized_notes=norm_notes,
        normalized_amount=norm_amount,
        normalized_type=norm_type,
        currency=currency,
        transaction_reference=norm_ref,
        running_balance=norm_bal,
        row_fingerprint=fingerprint,
        validation_status=v_status,
        validation_errors=errors,
    )

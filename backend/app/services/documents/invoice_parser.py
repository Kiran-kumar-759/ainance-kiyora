import datetime as dt
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from app.services.documents.ocr_engine import OcrDocumentOutput

GSTIN_REGEX = re.compile(r"\b(\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z])\b")
PHONE_REGEX = re.compile(r"(?:\+91[\-\s]?|0)?([6-9]\d{9})\b")
MONEY_NUM_RE = r"(?:₹|Rs\.?|INR|[\u20a0-\u20cf\ufffd\x7f\u00b7])?\s*([0-9][0-9,]*(?:\.\d{1,2})?)"

MONTH_MAP = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

GENERIC_HEADER_TERMS = {
    "tax invoice",
    "invoice",
    "retail invoice",
    "gst invoice",
    "receipt",
    "payment receipt",
    "bill",
    "bill of supply",
    "statement",
    "e-statement",
    "duplicate",
    "original for recipient",
    "credit card statement",
}


def _to_decimal(val: str | None) -> Decimal | None:
    if not val:
        return None
    cleaned = val.replace(",", "").replace("₹", "").replace("Rs.", "").replace("INR", "").strip()
    try:
        d = Decimal(cleaned)
        if d < Decimal("0"):
            return None
        return d.quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def parse_indian_date_str(raw: str | None) -> tuple[dt.date | None, str | None]:
    """
    Parses Indian/ISO dates cleanly:
    DD/MM/YYYY, DD-MM-YYYY, YYYY-MM-DD, DD MMM YYYY.
    Returns (parsed_date, invalid_date_error_or_None).
    """
    if not raw:
        return None, None
    s = raw.strip()

    # ISO YYYY-MM-DD
    m_iso = re.search(r"\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b", s)
    if m_iso:
        try:
            return dt.date(int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3))), None
        except ValueError:
            return None, f"Invalid calendar date encountered: '{m_iso.group(0)}'."

    # DD/MM/YYYY or DD-MM-YYYY
    m_dmy = re.search(r"\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})\b", s)
    if m_dmy:
        d_i, m_i, y_i = int(m_dmy.group(1)), int(m_dmy.group(2)), int(m_dmy.group(3))
        if y_i < 100:
            y_i += 2000
        try:
            return dt.date(y_i, m_i, d_i), None
        except ValueError:
            return None, f"Invalid Indian date encountered: '{m_dmy.group(0)}'."

    # DD MMM YYYY (e.g. 25 Nov 2026)
    m_txt = re.search(r"\b(\d{1,2})\s+([A-Za-z]{3,9})[,\s]+(\d{4})\b", s)
    if m_txt:
        mon = MONTH_MAP.get(m_txt.group(2).lower())
        if mon:
            try:
                return dt.date(int(m_txt.group(3)), mon, int(m_txt.group(1))), None
            except ValueError:
                return None, f"Invalid text date encountered: '{m_txt.group(0)}'."

    return None, None


@dataclass
class ParsedInvoiceResult:
    merchant_name: str | None = None
    merchant_address: str | None = None
    merchant_phone: str | None = None
    invoice_number: str | None = None
    invoice_date: dt.date | None = None
    due_date: dt.date | None = None
    payment_date: dt.date | None = None
    bill_period: str | None = None
    detected_document_type: str | None = None

    currency: str | None = "INR"
    subtotal: Decimal | None = None
    taxable_amount: Decimal | None = None
    total_tax: Decimal | None = None
    grand_total: Decimal | None = None
    amount_paid: Decimal | None = None
    outstanding_amount: Decimal | None = None

    gstin: str | None = None
    cgst: Decimal | None = None
    sgst: Decimal | None = None
    igst: Decimal | None = None
    tax_percentage: Decimal | None = None

    line_items: list[dict[str, Any]] = field(default_factory=list)
    field_confidence: dict[str, float] = field(default_factory=dict)
    validation_errors: list[str] = field(default_factory=list)
    validation_warnings: list[str] = field(default_factory=list)
    overall_confidence: Decimal = Decimal("0.0000")

    def to_snapshot_dict(self) -> dict[str, Any]:
        def _fmt(v: Any) -> Any:
            if isinstance(v, Decimal):
                return str(v)
            if isinstance(v, (dt.date, dt.datetime)):
                return v.isoformat()
            return v

        return {
            k: _fmt(v)
            for k, v in {
                "merchant_name": self.merchant_name,
                "merchant_address": self.merchant_address,
                "merchant_phone": self.merchant_phone,
                "invoice_number": self.invoice_number,
                "invoice_date": self.invoice_date,
                "due_date": self.due_date,
                "payment_date": self.payment_date,
                "bill_period": self.bill_period,
                "detected_document_type": self.detected_document_type,
                "currency": self.currency,
                "subtotal": self.subtotal,
                "taxable_amount": self.taxable_amount,
                "total_tax": self.total_tax,
                "grand_total": self.grand_total,
                "amount_paid": self.amount_paid,
                "outstanding_amount": self.outstanding_amount,
                "gstin": self.gstin,
                "cgst": self.cgst,
                "sgst": self.sgst,
                "igst": self.igst,
                "tax_percentage": self.tax_percentage,
                "line_items": self.line_items,
                "field_confidence": self.field_confidence,
                "validation_errors": self.validation_errors,
                "validation_warnings": self.validation_warnings,
            }.items()
        }


def validate_extraction_consistency(res: ParsedInvoiceResult) -> None:
    """Runs deterministic validation & arithmetic reconciliation rules."""
    if res.gstin:
        if not GSTIN_REGEX.fullmatch(res.gstin.strip().upper()):
            res.validation_errors.append(
                f"GSTIN '{res.gstin}' does not match standard 15-character Indian GSTIN format."
            )

    if res.grand_total is not None and res.grand_total < Decimal("0.00"):
        res.validation_errors.append("Grand total cannot be negative.")

    if res.invoice_date and res.due_date and res.due_date < res.invoice_date:
        res.validation_warnings.append(
            f"Due date ({res.due_date.isoformat()}) is earlier than invoice date ({res.invoice_date.isoformat()})."
        )

    # GST reconciliation without double counting
    gst_parts = [x for x in (res.cgst, res.sgst, res.igst) if x is not None]
    if gst_parts:
        gst_sum = sum(gst_parts, Decimal("0.00"))
        if res.cgst is not None and res.sgst is not None and res.igst is not None:
            res.validation_warnings.append(
                "Both intra-state (CGST/SGST) and inter-state (IGST) values extracted; verify to avoid double-counting."
            )
        elif res.total_tax is not None and abs(res.total_tax - gst_sum) > Decimal("1.00"):
            res.validation_warnings.append(
                f"Extracted GST components sum (₹{gst_sum}) differs from Total Tax (₹{res.total_tax})."
            )

    # Subtotal + tax vs grand total check
    tax_base = res.taxable_amount if res.taxable_amount is not None else res.subtotal
    effective_tax = (
        res.total_tax
        if res.total_tax is not None
        else (sum(gst_parts, Decimal("0.00")) if gst_parts else None)
    )
    if tax_base is not None and effective_tax is not None and res.grand_total is not None:
        expected = tax_base + effective_tax
        if abs(expected - res.grand_total) > Decimal("2.00"):
            res.validation_warnings.append(
                f"Taxable/Subtotal (₹{tax_base}) + Tax (₹{effective_tax}) = ₹{expected} "
                f"differs from Grand Total (₹{res.grand_total}). Flagged for review."
            )

    # Line items sum comparison
    item_totals = [
        _to_decimal(str(it.get("total")))
        for it in res.line_items
        if it.get("total") is not None
    ]
    valid_totals = [x for x in item_totals if x is not None]
    if valid_totals and (res.subtotal is not None or res.grand_total is not None):
        items_sum = sum(valid_totals, Decimal("0.00"))
        compare_target = res.subtotal if res.subtotal is not None else res.grand_total
        if compare_target is not None and abs(items_sum - compare_target) > Decimal("2.00"):
            res.validation_warnings.append(
                f"Sum of extracted line items (₹{items_sum}) differs from invoice target (₹{compare_target})."
            )

    if res.grand_total is None and res.subtotal is None and not res.line_items:
        res.validation_warnings.append(
            "No clear grand total or subtotal could be extracted automatically; please enter/verify amounts."
        )


def parse_ocr_output(ocr_doc: OcrDocumentOutput) -> ParsedInvoiceResult:
    """
    Deterministically parses structured invoice, financial, Indian GST, and line-item
    fields from raw OCR text + line confidences. Leaves missing data as None.
    """
    res = ParsedInvoiceResult()
    text = ocr_doc.full_text or ""
    lines_with_conf: list[tuple[str, float]] = [
        (ln.text.strip(), float(ln.confidence))
        for page in ocr_doc.pages
        for ln in page.lines
        if ln.text.strip()
    ]
    if not text.strip():
        res.validation_warnings.append("Empty OCR text extracted from document.")
        return res

    lower_full = text.lower()

    # Document type classification (distinct receipt vs invoice vs statement)
    if "credit card statement" in lower_full or "account statement" in lower_full or "bank statement" in lower_full:
        res.detected_document_type = "statement"
    elif "payment receipt" in lower_full or ("receipt" in lower_full and "invoice" not in lower_full):
        res.detected_document_type = "receipt"
    elif "invoice" in lower_full or "gstin" in lower_full or "bill no" in lower_full or "due date" in lower_full:
        res.detected_document_type = "invoice"
    else:
        res.detected_document_type = "other"

    # Currency detection (default INR only when justified or standard domestic document)
    if "usd" in lower_full or ("$" in text and "₹" not in text and "inr" not in lower_full):
        res.currency = "USD"
    elif "eur" in lower_full or ("€" in text and "₹" not in text and "inr" not in lower_full):
        res.currency = "EUR"
    else:
        res.currency = "INR"

    def _match_line_amount(patterns: list[str]) -> tuple[Decimal | None, float]:
        for ln, conf in lines_with_conf:
            for pat in patterns:
                m = re.search(pat, ln, re.IGNORECASE)
                if m:
                    amt = _to_decimal(m.group(1))
                    if amt is not None:
                        return amt, min(0.99, round(conf * 0.96, 3))
        return None, 0.0

    # Merchant Name: explicit label first, then cleanest top-of-page heading line
    for ln, conf in lines_with_conf[:12]:
        m_merch = re.search(
            r"(?:merchant|vendor|seller|billed by|company|from)\s*[:\-]\s*(.+)$",
            ln,
            re.IGNORECASE,
        )
        if m_merch and len(m_merch.group(1).strip()) >= 2:
            res.merchant_name = m_merch.group(1).strip()[:140]
            res.field_confidence["merchant_name"] = round(conf * 0.92, 3)
            break
    if not res.merchant_name:
        for ln, conf in lines_with_conf[:8]:
            low = ln.lower().strip(" :-")
            if re.search(r"\b(?:dish|particulars|qty|0ty|amnt|unit\s*price)\b", low):
                break
            if (
                low in GENERIC_HEADER_TERMS
                or GSTIN_REGEX.search(ln)
                or re.match(
                    r"^(?:invoice|bill|receipt|date|gst|ph|tel|to|customer|cashier|waiter|server|covers|table|order|kot|dish|item|qty|0ty|amnt|amount|description|sl\.?\s*no|tax|service)",
                    low,
                )
                or re.search(r"\d+\.\d{2}\s*\.?\s*$", ln)
                or re.fullmatch(r"[\d\W]+", ln)
            ):
                continue
            if 3 <= len(ln) <= 80:
                res.merchant_name = ln[:140]
                res.field_confidence["merchant_name"] = round(conf * 0.85, 3)
                break

    # Phone number
    for ln, conf in lines_with_conf[:15]:
        m_ph = PHONE_REGEX.search(ln)
        if m_ph:
            res.merchant_phone = m_ph.group(0).strip()[:35]
            res.field_confidence["merchant_phone"] = round(conf * 0.9, 3)
            break

    # Address lines (heuristic: header lines containing India pin/city/road/floor)
    addr_lines: list[str] = []
    for ln, conf in lines_with_conf[1:12]:
        if re.search(r"\b(\d{6}|road|street|nagar|layout|park|india|bengaluru|mumbai|delhi|hyderabad|chennai|pune)\b", ln, re.IGNORECASE):
            if res.merchant_name and ln != res.merchant_name and not GSTIN_REGEX.search(ln):
                addr_lines.append(ln)
    if addr_lines:
        res.merchant_address = ", ".join(addr_lines)[:300]
        res.field_confidence["merchant_address"] = 0.78

    # GSTIN
    for ln, conf in lines_with_conf:
        m_gst = GSTIN_REGEX.search(ln.upper())
        if m_gst:
            res.gstin = m_gst.group(1)
            res.field_confidence["gstin"] = round(conf * 0.95, 3)
            break
    # Also flag invalid labeled GSTIN if present
    if not res.gstin:
        m_bad_gst = re.search(r"GSTIN\s*[:#\-]?\s*([A-Z0-9\-]{6,22})", text, re.IGNORECASE)
        if m_bad_gst:
            candidate_gst = m_bad_gst.group(1).strip()
            res.gstin = candidate_gst
            res.field_confidence["gstin"] = 0.45

    # Invoice / Bill Number
    for ln, conf in lines_with_conf:
        m_inv = re.search(
            r"(?:invoice|inv|bill|receipt|order)\s*(?:no\.?|number|#)\s*[:\-]?\s*([A-Za-z0-9][A-Za-z0-9/\-_]{2,40})",
            ln,
            re.IGNORECASE,
        )
        if m_inv:
            res.invoice_number = m_inv.group(1).strip()
            res.field_confidence["invoice_number"] = round(conf * 0.93, 3)
            break

    # Bill Period
    for ln, conf in lines_with_conf:
        m_per = re.search(r"(?:billing|bill)\s*period\s*[:\-]\s*(.+)$", ln, re.IGNORECASE)
        if m_per:
            res.bill_period = m_per.group(1).strip()[:95]
            res.field_confidence["bill_period"] = round(conf * 0.88, 3)
            break

    # Dates: Invoice Date, Due Date, Payment Date
    for ln, conf in lines_with_conf:
        if not res.due_date and re.search(r"due\s*date", ln, re.IGNORECASE):
            d_val, d_err = parse_indian_date_str(ln)
            if d_err:
                res.validation_errors.append(d_err)
            elif d_val:
                res.due_date = d_val
                res.field_confidence["due_date"] = round(conf * 0.94, 3)
        elif not res.payment_date and re.search(r"(?:payment|paid)\s*date", ln, re.IGNORECASE):
            d_val, d_err = parse_indian_date_str(ln)
            if d_err:
                res.validation_errors.append(d_err)
            elif d_val:
                res.payment_date = d_val
                res.field_confidence["payment_date"] = round(conf * 0.92, 3)
        elif not res.invoice_date and re.search(r"(?:invoice|bill|receipt|issue)?\s*date", ln, re.IGNORECASE):
            d_val, d_err = parse_indian_date_str(ln)
            if d_err:
                res.validation_errors.append(d_err)
            elif d_val:
                res.invoice_date = d_val
                res.field_confidence["invoice_date"] = round(conf * 0.92, 3)

    # Financial amounts
    sub_v, sub_c = _match_line_amount([rf"(?:sub[\-\s]?total)\s*[:\-]?\s*{MONEY_NUM_RE}"])
    if sub_v is not None:
        res.subtotal = sub_v
        res.field_confidence["subtotal"] = sub_c

    taxable_v, taxable_c = _match_line_amount([rf"(?:taxable\s*(?:value|amount))\s*[:\-]?\s*{MONEY_NUM_RE}"])
    if taxable_v is not None:
        res.taxable_amount = taxable_v
        res.field_confidence["taxable_amount"] = taxable_c

    cgst_v, cgst_c = _match_line_amount(
        [rf"\bCGST\b(?:\s*\(?\s*@?\s*\d+(?:\.\d+)?\s*%\s*\)?)?\s*[:\-]?\s*{MONEY_NUM_RE}(?!\s*%)"]
    )
    if cgst_v is not None:
        res.cgst = cgst_v
        res.field_confidence["cgst"] = cgst_c

    sgst_v, sgst_c = _match_line_amount(
        [rf"\bSGST\b(?:\s*\(?\s*@?\s*\d+(?:\.\d+)?\s*%\s*\)?)?\s*[:\-]?\s*{MONEY_NUM_RE}(?!\s*%)"]
    )
    if sgst_v is not None:
        res.sgst = sgst_v
        res.field_confidence["sgst"] = sgst_c

    igst_v, igst_c = _match_line_amount(
        [rf"\bIGST\b(?:\s*\(?\s*@?\s*\d+(?:\.\d+)?\s*%\s*\)?)?\s*[:\-]?\s*{MONEY_NUM_RE}(?!\s*%)"]
    )
    if igst_v is not None:
        res.igst = igst_v
        res.field_confidence["igst"] = igst_c

    ttax_v, ttax_c = _match_line_amount(
        [
            rf"(?:total\s*tax|total\s*gst|gst\s*amount)\s*[:\-]?\s*{MONEY_NUM_RE}(?!\s*%)",
            rf"(?:service\s*charge|service\s*tax|s\.?\s*charge)\b.*?(?::|\+|\-)\s*{MONEY_NUM_RE}(?!\s*%)",
        ]
    )
    if ttax_v is not None:
        res.total_tax = ttax_v
        res.field_confidence["total_tax"] = ttax_c
    elif res.cgst is not None or res.sgst is not None or res.igst is not None:
        parts = [p for p in (res.cgst, res.sgst, res.igst) if p is not None]
        res.total_tax = sum(parts, Decimal("0.00")).quantize(Decimal("0.01"))
        res.field_confidence["total_tax"] = 0.85

    m_pct = re.search(r"(?:GST|Tax)\s*(?:@|Rate)?\s*(\d{1,2}(?:\.\d{1,2})?)\s*%", text, re.IGNORECASE)
    if m_pct:
        try:
            res.tax_percentage = Decimal(m_pct.group(1)).quantize(Decimal("0.01"))
            res.field_confidence["tax_percentage"] = 0.84
        except Exception:
            pass

    gt_v, gt_c = _match_line_amount(
        [
            rf"(?:grand\s*total|net\s*payable|total\s*payable|total\s*amount|bill\s*amount|invoice\s*total|amount\s*payable)\s*[:\-]?\s*{MONEY_NUM_RE}",
            rf"^\s*Total\s*[:\-]?\s*{MONEY_NUM_RE}",
        ]
    )
    if gt_v is not None:
        res.grand_total = gt_v
        res.field_confidence["grand_total"] = gt_c

    paid_v, paid_c = _match_line_amount([rf"(?:amount\s*paid|total\s*paid)\s*[:\-]?\s*{MONEY_NUM_RE}"])
    if paid_v is not None:
        res.amount_paid = paid_v
        res.field_confidence["amount_paid"] = paid_c

    due_v, due_c = _match_line_amount([rf"(?:balance\s*due|outstanding\s*amount|amount\s*due)\s*[:\-]?\s*{MONEY_NUM_RE}"])
    if due_v is not None:
        res.outstanding_amount = due_v
        res.field_confidence["outstanding_amount"] = due_c

    # Extract tabular line items safely (supports dot-matrix POS receipts + GST invoices)
    summary_ignore_re = re.compile(
        r"(?:sub[\-\s]?total|grand\s*total|cgst|sgst|igst|total\s*tax|total\s*gst|taxable|amount\s*paid|balance|gstin|service\s*charge|service\s*tax|covers|cashier|round\s*off|discount|net\s*amount)",
        re.IGNORECASE,
    )
    for ln, _conf in lines_with_conf:
        clean_ln = ln.strip().rstrip(".")
        if summary_ignore_re.search(clean_ln):
            continue
        if re.match(r"^(?:dish|item|qty|0ty|amnt|amount|particulars|description)\b", clean_ln, re.IGNORECASE):
            continue

        # Normalize OCR dot-matrix quantity noise glyphs (e.g. '1案', '2米', '2.米', '4#', '5*')
        norm_ln = re.sub(
            r"(\s\d+(?:\.\d{1,2})?)\s*(?:[*#x×\.]|[^\x00-\x7f])+\s+",
            r"\1   ",
            clean_ln,
        )

        # 1. Match 4 columns: "Description   Qty   UnitPrice   Total"
        m_4col = re.match(
            r"^[-\s]*([A-Za-z][A-Za-z0-9\s\-/&().]{2,70}?)\s+(\d+(?:\.\d{1,2})?)\s+(?:₹|Rs\.?)?\s*([0-9,]+\.\d{2})\s+(?:₹|Rs\.?)?\s*([0-9,]+\.\d{2})\s*$",
            norm_ln,
        )
        if m_4col:
            qty = _to_decimal(m_4col.group(2))
            unit_p = _to_decimal(m_4col.group(3))
            tot_p = _to_decimal(m_4col.group(4))
            if tot_p is not None:
                res.line_items.append(
                    {
                        "description": m_4col.group(1).strip(" -"),
                        "quantity": str(qty) if qty is not None else None,
                        "unit_price": str(unit_p) if unit_p is not None else None,
                        "total": str(tot_p),
                    }
                )
            continue

        # 2. Match 3 columns: "Description   Qty   Total"
        m_3col = re.match(
            r"^[-\s]*([A-Za-z][A-Za-z0-9\s\-/&().]{2,70}?)\s+(\d+(?:\.\d{1,2})?)\s+(?:₹|Rs\.?|INR)?\s*([0-9,]+\.\d{2})\s*$",
            norm_ln,
        )
        if m_3col:
            qty = _to_decimal(m_3col.group(2))
            tot_p = _to_decimal(m_3col.group(3))
            if tot_p is not None and qty is not None and qty > 0:
                unit_p = (tot_p / qty).quantize(Decimal("0.01"))
                res.line_items.append(
                    {
                        "description": m_3col.group(1).strip(" -"),
                        "quantity": str(qty),
                        "unit_price": str(unit_p),
                        "total": str(tot_p),
                    }
                )
            continue

        # 3. Match 2 columns: "Description   ₹499.00" or "Description   180.00"
        m_simple = re.match(
            r"^[-\s]*([A-Za-z][A-Za-z0-9\s\-/&().]{2,70}?)\s+(?:₹|Rs\.?|INR)?\s*([0-9][0-9,]*\.\d{2})\s*$",
            clean_ln,
        )
        if m_simple and not re.match(r"^(?:total|net|paid|due)\b", m_simple.group(1), re.IGNORECASE):
            tot_p = _to_decimal(m_simple.group(2))
            if tot_p is not None:
                res.line_items.append(
                    {
                        "description": m_simple.group(1).strip(" -"),
                        "quantity": "1.00",
                        "unit_price": str(tot_p),
                        "total": str(tot_p),
                    }
                )

    if res.line_items:
        res.field_confidence["line_items"] = 0.82
        items_sum = sum(
            (Decimal(str(it["total"])) for it in res.line_items if it.get("total") is not None),
            Decimal("0.00"),
        ).quantize(Decimal("0.01"))
        if res.subtotal is None and items_sum > Decimal("0.00"):
            # Look for matching standalone subtotal line near bottom of table
            for ln, conf in lines_with_conf:
                m_solo = re.fullmatch(r"\s*(?:₹|Rs\.?|INR)?\s*([0-9][0-9,]*\.\d{2})\.?\s*", ln)
                if m_solo:
                    cand = _to_decimal(m_solo.group(1))
                    if cand is not None and abs(cand - items_sum) <= Decimal("1.00"):
                        res.subtotal = cand
                        res.field_confidence["subtotal"] = round(conf * 0.9, 3)
                        break
            if res.subtotal is None and len(res.line_items) >= 2:
                res.subtotal = items_sum
                res.field_confidence["subtotal"] = 0.78

    if res.grand_total is None and res.subtotal is not None and res.total_tax is not None:
        res.grand_total = (res.subtotal + res.total_tax).quantize(Decimal("0.01"))
        res.field_confidence["grand_total"] = 0.72
        res.validation_warnings.append(
            f"Grand Total (₹{res.grand_total}) calculated from Subtotal + Tax/Charges because final total line was not detected — please verify."
        )

    # Overall confidence average
    if res.field_confidence:
        avg_f = sum(res.field_confidence.values()) / len(res.field_confidence)
        res.overall_confidence = Decimal(str(round(avg_f, 4))).quantize(Decimal("0.0001"))
    else:
        res.overall_confidence = Decimal(str(round(ocr_doc.average_confidence, 4))).quantize(
            Decimal("0.0001")
        )

    validate_extraction_consistency(res)
    return res

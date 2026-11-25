import csv
import datetime as dt
import hashlib
import io
import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

ALLOWED_EXTENSIONS = {".csv", ".xlsx"}


@dataclass
class ParsedStatementInspection:
    file_type: str
    available_sheets: list[str]
    selected_sheet: str
    delimiter: str | None
    header_row_index: int
    total_raw_rows: int
    columns: list[str]
    preview_rows: list[list[str]]
    sample_mapped_rows: list[dict[str, Any]]
    all_rows: list[dict[str, Any]]
    suggested_mapping: dict[str, Any]


def sanitize_filename(filename: str | None) -> str:
    """Strips directory components and unsafe characters from user-supplied filenames."""
    base = Path(filename or "statement").name
    cleaned = re.sub(r"[^A-Za-z0-9._\- ]+", "_", base).strip()
    return (cleaned or "statement")[:255]


def validate_upload_content(
    filename: str | None,
    data: bytes,
    max_size_bytes: int,
) -> tuple[str, str, str]:
    """
    Validates uploaded file extension, size, and actual binary/text content.
    Returns (sanitized_filename, file_type, sha256_hex).
    """
    safe_name = sanitize_filename(filename)
    ext = Path(safe_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file format '{ext or 'unknown'}'. Only .csv and .xlsx files are supported."
        )

    if not data or len(data) == 0:
        raise ValueError("Uploaded file is empty.")

    if len(data) > max_size_bytes:
        max_mb = round(max_size_bytes / (1024 * 1024), 1)
        raise ValueError(f"File exceeds maximum allowed size of {max_mb} MB.")

    file_hash = hashlib.sha256(data).hexdigest()

    if ext == ".xlsx":
        # Must start with ZIP local file header PK\x03\x04
        if not data.startswith(b"PK\x03\x04"):
            raise ValueError("Invalid XLSX file content (corrupted or mismatched file signature).")
        try:
            wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
            sheet_names = wb.sheetnames
            wb.close()
            if not sheet_names:
                raise ValueError("XLSX workbook contains no sheets.")
        except ValueError:
            raise
        except Exception as err:
            raise ValueError(f"Failed to read XLSX workbook: {err}") from err
        return safe_name, "xlsx", file_hash

    # CSV validation: reject null bytes / ZIP masquerading as CSV, require valid UTF-8 / UTF-8-BOM
    if b"\x00" in data[:4096] or data.startswith(b"PK\x03\x04"):
        raise ValueError("Invalid CSV content: binary data detected in CSV upload.")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as err:
        raise ValueError(
            "CSV file must be UTF-8 encoded (UTF-8 and UTF-8 with BOM are supported)."
        ) from err

    if not text.strip():
        raise ValueError("Uploaded CSV file contains no rows.")

    return safe_name, "csv", file_hash


def _cell_to_serializable(val: Any) -> Any:
    """Converts openpyxl cell values into JSON-serializable, lossless primitives."""
    if val is None:
        return ""
    if isinstance(val, dt.datetime):
        return val.strftime("%Y-%m-%d")
    if isinstance(val, dt.date):
        return val.strftime("%Y-%m-%d")
    if isinstance(val, Decimal):
        return str(val)
    if isinstance(val, bool):
        return str(val)
    if isinstance(val, int):
        return val
    if isinstance(val, float):
        # Preserve exact human decimal representation without scientific drift
        return format(Decimal(str(val)), "f").rstrip("0").rstrip(".") if "." in str(val) else val
    return str(val).strip()


def _detect_header_row(grid: list[list[str]]) -> int:
    """Finds the most likely 0-based header row index in the top 20 rows."""
    header_keywords = {
        "date",
        "txn",
        "transaction",
        "description",
        "narration",
        "particulars",
        "remarks",
        "amount",
        "debit",
        "credit",
        "withdrawal",
        "deposit",
        "balance",
        "ref",
        "utr",
    }
    best_idx = 0
    best_score = -1

    for idx, row in enumerate(grid[:20]):
        non_empty = [c.strip() for c in row if str(c).strip() != ""]
        if len(non_empty) < 2:
            continue
        score = len(non_empty)
        lowered = " ".join(c.lower() for c in non_empty)
        for kw in header_keywords:
            if kw in lowered:
                score += 5
        if score > best_score:
            best_score = score
            best_idx = idx
    return best_idx


def _build_unique_headers(raw_header_cells: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    headers: list[str] = []
    for idx, cell in enumerate(raw_header_cells):
        name = str(cell).strip() if cell is not None else ""
        if not name:
            name = f"Column_{idx + 1}"
        base = name
        if base in seen:
            seen[base] += 1
            name = f"{base}_{seen[base]}"
        else:
            seen[base] = 1
        headers.append(name)
    return headers


def _extract_rows_from_grid(
    grid: list[list[Any]],
    header_row_index: int,
    max_rows: int,
) -> tuple[list[str], list[dict[str, Any]], list[list[str]]]:
    if not grid:
        raise ValueError("Statement contains no data rows.")
    if header_row_index < 0 or header_row_index >= len(grid):
        raise ValueError(f"Invalid header row index {header_row_index}.")

    raw_headers = [str(_cell_to_serializable(c)) for c in grid[header_row_index]]
    # Trim trailing blank header cells
    while raw_headers and raw_headers[-1].strip() == "":
        raw_headers.pop()
    if not raw_headers:
        raise ValueError("Selected header row contains no column headers.")

    headers = _build_unique_headers(raw_headers)
    num_cols = len(headers)

    preview_rows: list[list[str]] = [
        [str(_cell_to_serializable(c)) for c in r[: max(num_cols, 12)]] for r in grid[:15]
    ]

    parsed_rows: list[dict[str, Any]] = []
    for row_idx in range(header_row_index + 1, len(grid)):
        raw_cells = grid[row_idx]
        # Skip completely empty rows
        if not any(str(_cell_to_serializable(c)).strip() != "" for c in raw_cells):
            continue
        row_dict: dict[str, Any] = {"__source_row_number__": row_idx + 1}
        for col_idx, col_name in enumerate(headers):
            val = raw_cells[col_idx] if col_idx < len(raw_cells) else ""
            row_dict[col_name] = _cell_to_serializable(val)
        parsed_rows.append(row_dict)
        if len(parsed_rows) > max_rows:
            raise ValueError(f"Statement exceeds maximum limit of {max_rows} data rows.")

    if not parsed_rows:
        raise ValueError("No transaction data rows found below the header row.")

    return headers, parsed_rows, preview_rows


def _detect_csv_delimiter(sample_text: str) -> str:
    try:
        dialect = csv.Sniffer().sniff(sample_text, delimiters=",;\t|")
        return dialect.delimiter
    except csv.Error:
        counts = {d: sample_text.count(d) for d in (",", ";", "\t")}
        best = max(counts, key=lambda k: counts[k])
        return best if counts[best] > 0 else ","


def suggest_column_mapping(columns: list[str], sample_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Heuristically proposes initial column mapping (requires explicit user confirmation)."""

    def find_match(patterns: list[str], exclude: set[str] | None = None) -> str | None:
        excluded = exclude or set()
        for pat in patterns:
            for col in columns:
                if col in excluded:
                    continue
                norm = col.lower().strip()
                if re.search(pat, norm):
                    return col
        return None

    used: set[str] = set()
    date_col = find_match(
        [r"\b(txn|transaction|tran|posting|value)?\s*date\b", r"^date$", r"\bdt\b"], used
    )
    if date_col:
        used.add(date_col)

    desc_col = find_match(
        [
            r"\b(description|narration|particulars|remarks|details|memo|transaction details)\b",
        ],
        used,
    )
    if desc_col:
        used.add(desc_col)

    debit_col = find_match([r"\b(debit|withdrawal|dr\s*amt|debit\s*amount|paid\s*out)\b"], used)
    credit_col = find_match([r"\b(credit|deposit|cr\s*amt|credit\s*amount|paid\s*in)\b"], used)
    amount_col = find_match([r"\b(txn\s*amount|transaction\s*amount|amount|amt)\b"], used)

    if debit_col and credit_col:
        amount_mode = "split"
        used.update({debit_col, credit_col})
        amount_col = None
    elif amount_col:
        amount_mode = "single"
        used.add(amount_col)
        debit_col = None
        credit_col = None
    else:
        amount_mode = "split" if (debit_col or credit_col) else "single"

    type_col = find_match([r"\b(dr/cr|dr_cr|cr/dr|type|txn\s*type|indicator)\b"], used)
    if type_col:
        used.add(type_col)

    ref_col = find_match(
        [r"\b(ref|reference|utr|chq|cheque|txn\s*id|transaction\s*id|ref\s*no)\b"], used
    )
    if ref_col:
        used.add(ref_col)

    balance_col = find_match([r"\b(balance|closing\s*balance|running\s*balance|bal)\b"], used)
    if balance_col:
        used.add(balance_col)

    merchant_col = find_match([r"\b(merchant|payee|beneficiary|vendor|party)\b"], used)
    if merchant_col:
        used.add(merchant_col)

    notes_col = find_match([r"\b(notes|comment|remarks)\b"], used)
    currency_col = find_match([r"\b(currency|curr|ccy)\b"], used)

    return {
        "date_column": date_col,
        "description_column": desc_col,
        "amount_mode": amount_mode,
        "amount_column": amount_col,
        "debit_column": debit_col,
        "credit_column": credit_col,
        "type_column": type_col,
        "sign_convention": "negative_is_expense",
        "reference_column": ref_col,
        "balance_column": balance_col,
        "merchant_column": merchant_col,
        "notes_column": notes_col,
        "currency_column": currency_col,
        "date_format": "auto",
        "default_currency": "INR",
    }


def _parse_xlsx_worksheet(
    wb: Any,
    target_sheet: str,
    sheets: list[str],
    header_row_index: int | None,
    max_rows: int,
) -> ParsedStatementInspection:
    ws = wb[target_sheet]
    grid: list[list[Any]] = []
    for row in ws.iter_rows(values_only=True):
        row_vals = list(row)
        if any(v is not None and str(v).strip() != "" for v in row_vals):
            grid.append(row_vals)
    if not grid:
        raise ValueError(f"Selected sheet '{target_sheet}' is empty.")

    # Trim leading/trailing empty columns across the whole grid cleanly
    non_empty_col_indices = [
        col_i
        for col_i in range(max(len(r) for r in grid))
        for _ in [0]
        if any(
            col_i < len(r) and r[col_i] is not None and str(r[col_i]).strip() != ""
            for r in grid
        )
    ]
    if non_empty_col_indices:
        min_col = min(non_empty_col_indices)
        max_col = max(non_empty_col_indices)
        grid = [r[min_col : max_col + 1] for r in grid]

    str_grid = [[str(_cell_to_serializable(c)) for c in r] for r in grid[:20]]
    hdr_idx = (
        header_row_index if header_row_index is not None else _detect_header_row(str_grid)
    )
    headers, all_rows, preview_rows = _extract_rows_from_grid(grid, hdr_idx, max_rows)
    sample_rows = [
        {k: v for k, v in row.items() if k != "__source_row_number__"} for row in all_rows[:5]
    ]
    return ParsedStatementInspection(
        file_type="xlsx",
        available_sheets=sheets,
        selected_sheet=target_sheet,
        delimiter=None,
        header_row_index=hdr_idx,
        total_raw_rows=len(all_rows),
        columns=headers,
        preview_rows=preview_rows,
        sample_mapped_rows=sample_rows,
        all_rows=all_rows,
        suggested_mapping=suggest_column_mapping(headers, sample_rows),
    )


def inspect_statement_bytes(
    data: bytes,
    file_type: str,
    max_rows: int = 5000,
    sheet_name: str | None = None,
    header_row_index: int | None = None,
    delimiter: str | None = None,
) -> ParsedStatementInspection:
    """Parses raw CSV or XLSX bytes for inspection, preview, and normalized row extraction."""
    if file_type == "csv":
        text = data.decode("utf-8-sig")
        detected_delim = delimiter or _detect_csv_delimiter(text[:8192])
        reader = csv.reader(io.StringIO(text), delimiter=detected_delim)
        grid = [[cell.strip() for cell in row] for row in reader if any(c.strip() for c in row)]
        if not grid:
            raise ValueError("CSV file contains no non-empty rows.")
        hdr_idx = header_row_index if header_row_index is not None else _detect_header_row(grid)
        headers, all_rows, preview_rows = _extract_rows_from_grid(grid, hdr_idx, max_rows)
        sample_rows = [
            {k: v for k, v in row.items() if k != "__source_row_number__"} for row in all_rows[:5]
        ]
        return ParsedStatementInspection(
            file_type="csv",
            available_sheets=["CSV"],
            selected_sheet="CSV",
            delimiter=detected_delim,
            header_row_index=hdr_idx,
            total_raw_rows=len(all_rows),
            columns=headers,
            preview_rows=preview_rows,
            sample_mapped_rows=sample_rows,
            all_rows=all_rows,
            suggested_mapping=suggest_column_mapping(headers, sample_rows),
        )

    if file_type == "xlsx":
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        try:
            sheets = list(wb.sheetnames)
            if not sheets:
                raise ValueError("XLSX workbook contains no sheets.")
            if sheet_name:
                if sheet_name not in sheets:
                    raise ValueError(f"Sheet '{sheet_name}' not found in workbook.")
                return _parse_xlsx_worksheet(wb, sheet_name, sheets, header_row_index, max_rows)

            last_err: ValueError | None = None
            for candidate_sheet in sheets:
                try:
                    return _parse_xlsx_worksheet(
                        wb, candidate_sheet, sheets, header_row_index, max_rows
                    )
                except ValueError as exc:
                    last_err = exc
                    continue
            raise last_err or ValueError("XLSX workbook contains no valid transaction sheets.")
        finally:
            wb.close()

    raise ValueError(f"Unsupported file type: {file_type}")

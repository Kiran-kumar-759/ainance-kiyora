import io
import shutil
import uuid
from collections.abc import Generator
from decimal import Decimal

import pymupdf
import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from sqlalchemy import delete, select

from app.core.rate_limit import rate_limiter
from app.db.session import get_db
from app.main import create_application
from app.models.bills import (
    Bill,
    BillDocument,
    BillPayment,
    BillRecurrenceSchedule,
    BillReminder,
    Notification,
)
from app.models.documents import (
    DocumentExtraction,
    DocumentLink,
    DocumentProcessingJob,
    DocumentReviewEvent,
    FinancialDocument,
)
from app.models.finance import (
    FinancialAccount,
    FinancialCategory,
    FinancialTransaction,
    LedgerEntry,
    LedgerJournal,
)
from app.models.loans import Loan
from app.models.subscriptions import Subscription
from app.models.user import User
from app.services.documents.doc_storage import PrivateDocumentStorage
from app.services.documents.invoice_parser import parse_ocr_output
from app.services.documents.ocr_engine import (
    OcrDocumentOutput,
    OcrLineItem,
    OcrPageOutput,
    extract_document_text,
    get_ocr_provider,
)
from app.services.documents.worker import document_ocr_worker
from tests.conftest import TestingSessionLocal


@pytest.fixture
def live_doc_client() -> Generator[tuple[TestClient, list[str]], None, None]:
    created_emails: list[str] = []
    app = create_application()

    def _override_db():
        db = TestingSessionLocal()
        try:
            yield db
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_db
    rate_limiter._requests.clear()

    with TestClient(app, raise_server_exceptions=False) as tc:
        yield tc, created_emails

    app.dependency_overrides.clear()
    storage = PrivateDocumentStorage()
    cleanup = TestingSessionLocal()
    try:
        for email in created_emails:
            user = cleanup.execute(select(User).where(User.email == email)).scalar_one_or_none()
            if user:
                shutil.rmtree(storage.base_dir / str(user.id), ignore_errors=True)
                cleanup.execute(delete(DocumentLink).where(DocumentLink.user_id == user.id))
                cleanup.execute(delete(DocumentReviewEvent).where(DocumentReviewEvent.user_id == user.id))
                cleanup.execute(delete(DocumentExtraction).where(DocumentExtraction.user_id == user.id))
                cleanup.execute(delete(DocumentProcessingJob).where(DocumentProcessingJob.user_id == user.id))
                cleanup.execute(delete(FinancialDocument).where(FinancialDocument.user_id == user.id))
                cleanup.execute(delete(Notification).where(Notification.user_id == user.id))
                cleanup.execute(delete(BillReminder).where(BillReminder.user_id == user.id))
                cleanup.execute(delete(BillDocument).where(BillDocument.user_id == user.id))
                cleanup.execute(delete(BillPayment).where(BillPayment.user_id == user.id))
                cleanup.execute(delete(Bill).where(Bill.user_id == user.id))
                cleanup.execute(
                    delete(BillRecurrenceSchedule).where(BillRecurrenceSchedule.user_id == user.id)
                )
                cleanup.execute(delete(Subscription).where(Subscription.user_id == user.id))
                cleanup.execute(delete(Loan).where(Loan.user_id == user.id))
                cleanup.execute(delete(FinancialTransaction).where(FinancialTransaction.user_id == user.id))
                cleanup.execute(
                    delete(LedgerEntry).where(
                        LedgerEntry.journal_id.in_(
                            select(LedgerJournal.id).where(LedgerJournal.user_id == user.id)
                        )
                    )
                )
                cleanup.execute(delete(LedgerJournal).where(LedgerJournal.user_id == user.id))
                cleanup.execute(delete(FinancialAccount).where(FinancialAccount.user_id == user.id))
                cleanup.execute(delete(FinancialCategory).where(FinancialCategory.user_id == user.id))
                cleanup.execute(delete(User).where(User.id == user.id))
        cleanup.commit()
    finally:
        cleanup.close()


def _register_and_login(tc: TestClient, created_emails: list[str], prefix: str) -> dict[str, str]:
    email = f"{prefix}_{uuid.uuid4().hex[:8]}@example.in"
    created_emails.append(email)
    pw = "StrongPass#2026"
    r1 = tc.post(
        "/api/v1/auth/register",
        json={"email": email, "password": pw, "full_name": f"Test {prefix}", "mobile_number": "+919876543210"},
    )
    assert r1.status_code in (200, 201), r1.text
    r2 = tc.post("/api/v1/auth/login", json={"email": email, "password": pw})
    assert r2.status_code == 200, r2.text
    csrf = r2.cookies.get("pfm_csrf") or tc.get("/api/v1/auth/csrf").json()["csrf_token"]
    return {"X-CSRF-Token": csrf}


def _make_multipage_gst_invoice_pdf() -> bytes:
    doc = pymupdf.open()
    p1 = doc.new_page(width=595, height=842)
    text_p1 = (
        "ACME POWER UTILITIES INDIA PVT LTD\n"
        "42 MG Road, Bengaluru, Karnataka 560001\n"
        "Tel: +91 9845012345\n"
        "GSTIN: 29ABCDE1234F1Z5\n"
        "TAX INVOICE\n"
        "Invoice No: INV-2026-8841\n"
        "Invoice Date: 15/11/2026\n"
        "Due Date: 30/11/2026\n"
        "Billing Period: 01/10/2026 - 31/10/2026\n"
        "Electricity Supply Charges   ₹1,000.00\n"
        "Subtotal: ₹1,000.00\n"
        "CGST (9%): ₹90.00\n"
        "SGST (9%): ₹90.00\n"
        "Total Tax: ₹180.00\n"
        "Grand Total: ₹1,180.00\n"
    )
    p1.insert_text((50, 72), text_p1, fontsize=12)
    p2 = doc.new_page(width=595, height=842)
    p2.insert_text((50, 72), "Page 2 Terms: Pay before 30/11/2026 via UPI or NetBanking.", fontsize=11)
    buf = doc.tobytes()
    doc.close()
    return buf


def _make_receipt_png(lines: list[str] | None = None) -> bytes:
    img = Image.new("RGB", (900, 420), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    y = 40
    for line in lines or [
        "BESCOM ELECTRICITY RECEIPT",
        "INVOICE NO: REC-4402",
        "INVOICE DATE: 20/11/2026",
        "GRAND TOTAL: Rs. 850.00",
    ]:
        draw.text((40, y), line, fill=(0, 0, 0))
        y += 65
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def test_document_upload_security_validation_storage_isolation(live_doc_client):
    tc, created_emails = live_doc_client
    headers_a = _register_and_login(tc, created_emails, "docusera")

    # Unauthenticated check
    anon_tc = TestClient(tc.app)
    assert anon_tc.get("/api/v1/documents").status_code == 401

    pdf_bytes = _make_multipage_gst_invoice_pdf()

    # CSRF enforcement check
    no_csrf = tc.post(
        "/api/v1/documents/upload",
        files={"file": ("bill.pdf", pdf_bytes, "application/pdf")},
        data={"document_category": "electricity_bill", "auto_process": "false"},
    )
    assert no_csrf.status_code == 403

    # Invalid extension, spoofed MIME/signature, malformed PDF, and WebP validation
    bad_ext = tc.post(
        "/api/v1/documents/upload",
        headers=headers_a,
        files={"file": ("virus.exe", b"MZ123", "application/octet-stream")},
        data={"document_category": "other"},
    )
    assert bad_ext.status_code == 400

    spoofed_pdf = tc.post(
        "/api/v1/documents/upload",
        headers=headers_a,
        files={"file": ("fake.pdf", b"NOT_A_PDF_SIGNATURE", "application/pdf")},
        data={"document_category": "other"},
    )
    assert spoofed_pdf.status_code == 400

    malformed_pdf = tc.post(
        "/api/v1/documents/upload",
        headers=headers_a,
        files={"file": ("broken.pdf", b"%PDF-1.4 broken xref bytes", "application/pdf")},
        data={"document_category": "other"},
    )
    assert malformed_pdf.status_code == 400

    # Valid multi-page PDF upload
    up1 = tc.post(
        "/api/v1/documents/upload",
        headers=headers_a,
        files={"file": ("../../traversal_bill.pdf", pdf_bytes, "application/pdf")},
        data={"document_category": "electricity_bill", "auto_process": "true"},
    )
    assert up1.status_code == 201, up1.text
    d1 = up1.json()
    assert d1["original_filename"] == "traversal_bill.pdf"
    assert d1["page_count"] == 2
    assert d1["duplicate_flag"] is False
    assert "storage_key" not in d1

    # Duplicate hash detection on identical re-upload
    up_dup = tc.post(
        "/api/v1/documents/upload",
        headers=headers_a,
        files={"file": ("copy_bill.pdf", pdf_bytes, "application/pdf")},
        data={"document_category": "electricity_bill", "auto_process": "false"},
    )
    assert up_dup.status_code == 201
    assert up_dup.json()["duplicate_flag"] is True
    assert up_dup.json()["is_duplicate_of_id"] == d1["id"]

    # Valid PNG + WebP uploads
    png_bytes = _make_receipt_png()
    up_png = tc.post(
        "/api/v1/documents/upload",
        headers=headers_a,
        files={"file": ("receipt.png", png_bytes, "image/png")},
        data={"document_category": "shopping_receipt", "auto_process": "false"},
    )
    assert up_png.status_code == 201

    webp_buf = io.BytesIO()
    Image.new("RGB", (120, 80), color=(240, 240, 240)).save(webp_buf, format="WEBP")
    up_webp = tc.post(
        "/api/v1/documents/upload",
        headers=headers_a,
        files={"file": ("scan.webp", webp_buf.getvalue(), "image/webp")},
        data={"document_category": "other", "auto_process": "false"},
    )
    assert up_webp.status_code == 201

    # Private download + preview work for User A with nosniff headers
    dl = tc.get(f"/api/v1/documents/{d1['id']}/download")
    assert dl.status_code == 200
    assert dl.content == pdf_bytes
    assert dl.headers.get("x-content-type-options") == "nosniff"

    prev = tc.get(f"/api/v1/documents/{d1['id']}/preview?page=2")
    assert prev.status_code == 200
    assert prev.headers.get("x-total-pages") == "2"
    assert prev.content.startswith(b"\x89PNG")

    # Path traversal defense at storage boundary
    with pytest.raises(ValueError):
        PrivateDocumentStorage()._resolve_safe_path("../../etc/passwd")

    # Cross-user access isolation (User B receives 404 on every endpoint)
    tc_b = TestClient(tc.app)
    headers_b = _register_and_login(tc_b, created_emails, "docuserb")
    assert tc_b.get(f"/api/v1/documents/{d1['id']}").status_code == 404
    assert tc_b.get(f"/api/v1/documents/{d1['id']}/download").status_code == 404
    assert tc_b.get(f"/api/v1/documents/{d1['id']}/preview").status_code == 404
    assert tc_b.delete(f"/api/v1/documents/{d1['id']}", headers=headers_b).status_code == 404

    # Delete cleans up DB and private file
    storage = PrivateDocumentStorage()
    db_check = TestingSessionLocal()
    try:
        stored_key = db_check.execute(
            select(FinancialDocument.storage_key).where(FinancialDocument.id == uuid.UUID(d1["id"]))
        ).scalar_one()
        assert storage._resolve_safe_path(stored_key).exists()
    finally:
        db_check.close()

    del_res = tc.delete(f"/api/v1/documents/{d1['id']}", headers=headers_a)
    assert del_res.status_code == 204
    assert not storage._resolve_safe_path(stored_key).exists()


def test_real_ocr_pipeline_gst_extraction_validation_retry_and_human_confirmation(live_doc_client):
    tc, created_emails = live_doc_client
    headers = _register_and_login(tc, created_emails, "ocruser")

    # 1. Real RapidOCR (local CPU PP-OCR ONNX + OpenCV) end-to-end on synthetic PNG image
    png_bytes = _make_receipt_png(
        [
            "RELIANCE RETAIL LTD",
            "TAX INVOICE INV-9912",
            "DATE 18/11/2026",
            "GRAND TOTAL 540.00",
        ]
    )
    ocr_provider = get_ocr_provider()
    real_img_ocr = extract_document_text(png_bytes, "png", provider=ocr_provider)
    assert real_img_ocr.engine_name in {"rapidocr_paddleocr", "paddleocr"}
    assert real_img_ocr.total_pages == 1
    assert len(real_img_ocr.full_text) > 5

    # 2. Scanned PDF (image embedded in PDF with zero selectable text) processed via PyMuPDF + OpenCV + RapidOCR
    scan_pdf = pymupdf.open()
    page = scan_pdf.new_page(width=600, height=300)
    page.insert_image(pymupdf.Rect(10, 10, 590, 290), stream=png_bytes)
    scan_pdf_bytes = scan_pdf.tobytes()
    scan_pdf.close()

    scan_ocr = extract_document_text(scan_pdf_bytes, "pdf", provider=ocr_provider)
    assert scan_ocr.pages[0].used_ocr is True

    # 3. Conflicting invoice totals & missing fields validation test (never coerce missing to ₹0)
    conflict_ocr = OcrDocumentOutput(
        engine_name="pymupdf_text",
        engine_version="test",
        full_text=(
            "TEST TELECOM INDIA\n"
            "GSTIN: 27ABCDE1234F1Z5\n"
            "Invoice No: TEL-552\n"
            "Invoice Date: 31/02/2026\n"
            "Subtotal: ₹500.00\n"
            "CGST: ₹45.00\n"
            "SGST: ₹45.00\n"
            "Grand Total: ₹750.00\n"
        ),
        pages=[
            OcrPageOutput(
                page_number=1,
                text="",
                lines=[
                    OcrLineItem("TEST TELECOM INDIA", 0.95),
                    OcrLineItem("GSTIN: 27ABCDE1234F1Z5", 0.96),
                    OcrLineItem("Invoice No: TEL-552", 0.94),
                    OcrLineItem("Invoice Date: 31/02/2026", 0.92),
                    OcrLineItem("Subtotal: ₹500.00", 0.91),
                    OcrLineItem("CGST: ₹45.00", 0.90),
                    OcrLineItem("SGST: ₹45.00", 0.90),
                    OcrLineItem("Grand Total: ₹750.00", 0.93),
                ],
                used_ocr=False,
                average_confidence=0.93,
            )
        ],
        total_pages=1,
        processed_pages=1,
        warnings=[],
        average_confidence=0.93,
    )
    parsed_conflict = parse_ocr_output(conflict_ocr)
    assert parsed_conflict.igst is None
    assert parsed_conflict.amount_paid is None
    assert len(parsed_conflict.validation_errors) >= 1  # invalid date 31/02/2026
    assert any("differs from Grand Total" in w for w in parsed_conflict.validation_warnings)

    # 3b. Multi-column bounding-box row merging & dot-matrix POS receipt parsing
    from app.services.documents.ocr_engine import merge_ocr_lines_by_row

    pos_boxes = [
        OcrLineItem("Cashier :RAM", 0.98, [[30, 2], [240, 2], [240, 40], [30, 40]]),
        OcrLineItem("Dish", 0.99, [[30, 130], [110, 130], [110, 170], [30, 170]]),
        OcrLineItem("Qty", 0.75, [[460, 128], [530, 128], [530, 170], [460, 170]]),
        OcrLineItem("Amnt", 0.99, [[610, 129], [690, 129], [690, 170], [610, 170]]),
        OcrLineItem("Lahori Murgh Tandoori F", 0.99, [[31, 214], [420, 214], [420, 258], [31, 258]]),
        OcrLineItem("1案", 0.85, [[455, 214], [520, 214], [520, 258], [455, 258]]),
        OcrLineItem("180.00", 0.99, [[570, 212], [680, 212], [680, 254], [570, 254]]),
        OcrLineItem("-Assorted Veg Platter", 0.97, [[5, 343], [370, 343], [370, 385], [5, 385]]),
        OcrLineItem("2.米", 0.89, [[456, 343], [521, 343], [521, 386], [456, 386]]),
        OcrLineItem("500.00.", 0.99, [[571, 343], [695, 343], [695, 385], [571, 385]]),
        OcrLineItem("680.00", 0.99, [[574, 488], [700, 488], [700, 530], [574, 530]]),
        OcrLineItem("Service Charge @10.00 : +", 0.92, [[148, 533], [571, 533], [571, 567], [148, 567]]),
        OcrLineItem("68.00", 0.97, [[588, 530], [701, 530], [701, 567], [588, 567]]),
    ]
    merged_pos = merge_ocr_lines_by_row(pos_boxes)
    parsed_pos = parse_ocr_output(
        OcrDocumentOutput(
            engine_name="rapidocr_paddleocr",
            engine_version="test",
            full_text="\n".join(x.text for x in merged_pos),
            pages=[
                OcrPageOutput(
                    page_number=1,
                    text="\n".join(x.text for x in merged_pos),
                    lines=merged_pos,
                    used_ocr=True,
                    average_confidence=0.94,
                )
            ],
            total_pages=1,
            processed_pages=1,
            warnings=[],
            average_confidence=0.94,
        )
    )
    assert parsed_pos.merchant_name is None
    assert len(parsed_pos.line_items) == 2
    assert parsed_pos.subtotal == Decimal("680.00")
    assert parsed_pos.total_tax == Decimal("68.00")
    assert parsed_pos.grand_total == Decimal("748.00")

    # 4. Full PostgreSQL OCR Job -> Needs Review -> Edit -> Confirm -> Unpaid Bill & Ledger Transaction
    pdf_bytes = _make_multipage_gst_invoice_pdf()
    up = tc.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={"file": ("acme_power.pdf", pdf_bytes, "application/pdf")},
        data={"document_category": "electricity_bill", "auto_process": "true"},
    )
    assert up.status_code == 201
    doc_id = up.json()["id"]

    # Run background job batch deterministically against PostgreSQL
    db = TestingSessionLocal()
    try:
        processed_cnt = document_ocr_worker.process_pending_batch(db, limit=5)
        assert processed_cnt >= 1
    finally:
        db.close()

    detail = tc.get(f"/api/v1/documents/{doc_id}").json()
    assert detail["processing_status"] == "needs_review"
    ext = detail["extraction"]
    assert ext is not None
    assert ext["gstin"] == "29ABCDE1234F1Z5"
    assert Decimal(str(ext["cgst"])) == Decimal("90.00")
    assert Decimal(str(ext["sgst"])) == Decimal("90.00")
    assert Decimal(str(ext["grand_total"])) == Decimal("1180.00")
    assert ext["amount_paid"] is None
    assert ext["igst"] is None

    # Ensure OCR NEVER auto-created bills or transactions
    assert len(tc.get("/api/v1/bills").json()["items"]) == 0
    assert tc.get("/api/v1/finance/transactions").json()["total"] == 0

    # User edits extraction -> preserves immutable raw_text & logs audit diff
    edit_res = tc.patch(
        f"/api/v1/documents/{doc_id}/extraction",
        headers=headers,
        json={
            "merchant_name": "BESCOM Power India",
            "field_decisions": {"grand_total": "accepted"},
            "notes": "Verified supplier trading name",
        },
    )
    assert edit_res.status_code == 200
    edited = edit_res.json()
    assert edited["extraction"]["merchant_name"] == "BESCOM Power India"
    assert "ACME POWER UTILITIES" in edited["extraction"]["raw_text"]
    assert any(ev["action"] == "fields_edited" for ev in edited["review_events"])

    # Human confirms document creating an UNPAID bill
    conf_bill = tc.post(
        f"/api/v1/documents/{doc_id}/confirm",
        headers=headers,
        json={"action": "create_bill", "due_date": "2026-11-30"},
    )
    assert conf_bill.status_code == 200, conf_bill.text
    assert conf_bill.json()["processing_status"] == "confirmed"
    bills = tc.get("/api/v1/bills").json()["items"]
    assert len(bills) == 1
    assert bills[0]["derived_status"] != "paid"

    # Duplicate bill creation blocked on repeat confirm
    dup_bill = tc.post(
        f"/api/v1/documents/{doc_id}/confirm",
        headers=headers,
        json={"action": "create_bill"},
    )
    assert dup_bill.status_code == 400

    # Confirm second document into a real double-entry ledger transaction
    acc_res = tc.post(
        "/api/v1/finance/accounts",
        headers=headers,
        json={"name": "HDFC Savings", "account_type": "savings", "opening_balance": "10000.00"},
    )
    assert acc_res.status_code in (200, 201)
    acc_id = acc_res.json()["id"]

    up2 = tc.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={"file": ("tx_receipt.pdf", pdf_bytes, "application/pdf")},
        data={"document_category": "electricity_bill", "auto_process": "true"},
    )
    doc2_id = up2.json()["id"]
    db2 = TestingSessionLocal()
    try:
        document_ocr_worker.process_pending_batch(db2, limit=5)
    finally:
        db2.close()

    conf_tx = tc.post(
        f"/api/v1/documents/{doc2_id}/confirm",
        headers=headers,
        json={"action": "create_transaction", "financial_account_id": acc_id},
    )
    assert conf_tx.status_code == 200, conf_tx.text
    accs_after = tc.get("/api/v1/finance/accounts").json()
    assert Decimal(str(accs_after[0]["current_balance"])) == Decimal("8820.00")

    # Failure & bounded retry test on missing file on disk
    up3 = tc.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={"file": ("retry_doc.pdf", pdf_bytes, "application/pdf")},
        data={"document_category": "other", "auto_process": "true"},
    )
    doc3_id = up3.json()["id"]
    db3 = TestingSessionLocal()
    try:
        doc3 = db3.execute(
            select(FinancialDocument).where(FinancialDocument.id == uuid.UUID(doc3_id))
        ).scalar_one()
        PrivateDocumentStorage().delete(doc3.storage_key)
        document_ocr_worker.process_pending_batch(db3, limit=5)
        job3 = db3.execute(
            select(DocumentProcessingJob).where(DocumentProcessingJob.document_id == doc3.id)
        ).scalar_one()
        assert job3.attempt_count == 1
        assert job3.status == "queued"
        assert job3.next_retry_at is not None
    finally:
        db3.close()

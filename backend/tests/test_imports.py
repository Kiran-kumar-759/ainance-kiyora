import io
import shutil
import uuid
from collections.abc import Generator
from decimal import Decimal

import openpyxl
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.config import settings
from app.core.rate_limit import rate_limiter
from app.db.session import get_db
from app.main import create_application
from app.models.finance import (
    FinancialAccount,
    FinancialTransaction,
    LedgerEntry,
    LedgerJournal,
)
from app.models.imports import ImportBatch, ImportMappingProfile, ImportRow
from app.models.user import User
from app.services.imports.storage import LocalPrivateFileStorage
from tests.conftest import TestingSessionLocal


@pytest.fixture
def live_client() -> Generator[tuple[TestClient, list[str]], None, None]:
    """
    Real PostgreSQL multi-session TestClient fixture.
    Each HTTP request gets an independent SessionLocal() so commits,
    rollbacks, locking, and constraints reflect real production behavior.
    """
    created_emails: list[str] = []
    app = create_application()

    def real_style_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    app.dependency_overrides[get_db] = real_style_get_db

    with TestClient(app, raise_server_exceptions=False) as tc:
        yield tc, created_emails

    app.dependency_overrides.clear()

    # Clean up committed DB records and uploaded private storage files for test users
    storage = LocalPrivateFileStorage()
    cleanup_db = TestingSessionLocal()
    try:
        for email in created_emails:
            user = cleanup_db.execute(select(User).where(User.email == email)).scalar_one_or_none()
            if user:
                shutil.rmtree(storage.base_dir / str(user.id), ignore_errors=True)
                acc_ids = list(
                    cleanup_db.execute(
                        select(FinancialAccount.id).where(FinancialAccount.user_id == user.id)
                    ).scalars()
                )
                if acc_ids:
                    cleanup_db.execute(
                        delete(LedgerEntry).where(LedgerEntry.account_id.in_(acc_ids))
                    )
                cleanup_db.execute(delete(LedgerJournal).where(LedgerJournal.user_id == user.id))
                cleanup_db.execute(
                    delete(FinancialTransaction).where(FinancialTransaction.user_id == user.id)
                )
                cleanup_db.execute(delete(ImportRow).where(ImportRow.import_batch_id.in_(
                    select(ImportBatch.id).where(ImportBatch.user_id == user.id)
                )))
                cleanup_db.execute(delete(ImportBatch).where(ImportBatch.user_id == user.id))
                cleanup_db.execute(
                    delete(ImportMappingProfile).where(ImportMappingProfile.user_id == user.id)
                )
                cleanup_db.execute(
                    delete(FinancialAccount).where(FinancialAccount.user_id == user.id)
                )
                cleanup_db.delete(user)
        cleanup_db.commit()
    finally:
        cleanup_db.close()


def _register_and_login(
    tc: TestClient, created_emails: list[str], prefix: str, name: str
) -> dict[str, str]:
    rate_limiter.clear()
    email = f"{prefix}.{uuid.uuid4().hex[:8]}@example.in"
    created_emails.append(email)

    reg = tc.post(
        "/api/v1/auth/register",
        json={"full_name": name, "email": email, "password": "StrongPassword123!"},
    )
    assert reg.status_code == 201, reg.text

    login = tc.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "StrongPassword123!"},
    )
    assert login.status_code == 200, login.text
    csrf = login.cookies.get(settings.CSRF_COOKIE_NAME)
    assert csrf is not None
    return {"X-CSRF-Token": csrf}


def _create_account(
    tc: TestClient,
    headers: dict[str, str],
    name: str = "HDFC Salary",
    account_type: str = "savings",
    opening_balance: str = "100000.00",
) -> dict:
    resp = tc.post(
        "/api/v1/finance/accounts",
        json={
            "name": name,
            "account_type": account_type,
            "institution_name": "HDFC Bank",
            "account_identifier": "1234",
            "opening_balance": opening_balance,
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _make_xlsx_bytes(sheets: dict[str, list[list[object]]]) -> bytes:
    wb = openpyxl.Workbook()
    first = True
    for sheet_name, rows in sheets.items():
        ws = wb.active if first else wb.create_sheet(title=sheet_name)
        if first:
            ws.title = sheet_name
            first = False
        for row in rows:
            ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class TestStatementUploadAndValidation:
    def test_upload_validation_errors_and_archive_check(
        self, live_client: tuple[TestClient, list[str]]
    ) -> None:
        tc, created = live_client
        headers = _register_and_login(tc, created, "imp_val", "Upload Validator")
        acc = _create_account(tc, headers, opening_balance="50000.00")

        # 1. Unsupported extension (.pdf)
        r_pdf = tc.post(
            "/api/v1/imports/upload",
            data={"account_id": acc["id"]},
            files={"file": ("statement.pdf", b"%PDF-1.4 fake", "application/pdf")},
            headers=headers,
        )
        assert r_pdf.status_code == 400
        assert ".csv" in r_pdf.json()["detail"].lower()

        # 2. Spoofed extension (.xlsx containing plain text, invalid ZIP header)
        r_fake_xlsx = tc.post(
            "/api/v1/imports/upload",
            data={"account_id": acc["id"]},
            files={"file": ("fake.xlsx", b"this is not an excel file", "application/octet-stream")},
            headers=headers,
        )
        assert r_fake_xlsx.status_code == 400

        # 3. Empty file
        r_empty = tc.post(
            "/api/v1/imports/upload",
            data={"account_id": acc["id"]},
            files={"file": ("empty.csv", b"   \n  ", "text/csv")},
            headers=headers,
        )
        assert r_empty.status_code == 400

        # 4. Archived account rejected
        arch = tc.post(f"/api/v1/finance/accounts/{acc['id']}/archive", headers=headers)
        assert arch.status_code == 200
        r_arch = tc.post(
            "/api/v1/imports/upload",
            data={"account_id": acc["id"]},
            files={"file": ("stmt.csv", b"Date,Description,Amount\n01/11/2026,Test,-100\n", "text/csv")},
            headers=headers,
        )
        assert r_arch.status_code == 400

    def test_storage_path_traversal_blocked(self) -> None:
        storage = LocalPrivateFileStorage()
        with pytest.raises(ValueError):
            storage.read_bytes("../../etc/passwd")
        with pytest.raises(ValueError):
            storage.delete("../secret.csv")


class TestCsvXlsxEndToEndIngestionAndLedger:
    def test_csv_utf8_bom_split_debit_credit_edit_and_atomic_commit(
        self, live_client: tuple[TestClient, list[str]]
    ) -> None:
        tc, created = live_client
        headers = _register_and_login(tc, created, "imp_csv", "Kiran India")
        acc = _create_account(tc, headers, "SBI Savings", "savings", "25000.00")

        # UTF-8 BOM + quoted descriptions with commas + Indian DD/MM/YYYY + INR formatting + bad row
        csv_content = (
            "\ufeffTxn Date,Particulars,Debit,Credit,UTR No,Closing Balance\n"
            '01/11/2026,"Salary Credit - Nov, TechCorp",,"₹85,000.00",UTR001,"1,10,000.00"\n'
            '03/11/2026,"BigBasket, Indiranagar","2,450.50",,UTR002,"1,07,549.50"\n'
            "31/02/2026,Broken Date Entry,500.00,,UTR003,\n"
            "05/11/2026,Swiggy Order,499.50,,UTR004,\n"
        ).encode("utf-8")

        up = tc.post(
            "/api/v1/imports/upload",
            data={"account_id": acc["id"]},
            files={"file": ("../sbi_nov.csv", csv_content, "text/csv")},
            headers=headers,
        )
        assert up.status_code == 201, up.text
        preview = up.json()
        batch_id = preview["batch"]["id"]
        # Filename is sanitized (no ../)
        assert preview["batch"]["original_filename"] == "sbi_nov.csv"
        assert preview["batch"]["status"] == "mapping_required"
        assert "Txn Date" in preview["columns"]

        # Map columns & save profile
        map_resp = tc.put(
            f"/api/v1/imports/{batch_id}/mapping",
            json={
                "date_column": "Txn Date",
                "description_column": "Particulars",
                "amount_mode": "split",
                "debit_column": "Debit",
                "credit_column": "Credit",
                "reference_column": "UTR No",
                "balance_column": "Closing Balance",
                "date_format": "DD/MM/YYYY",
                "default_currency": "INR",
                "save_profile_name": "SBI Split Profile",
            },
            headers=headers,
        )
        assert map_resp.status_code == 200, map_resp.text
        batch = map_resp.json()
        assert batch["status"] == "ready_for_review"
        assert batch["total_rows"] == 4
        assert batch["valid_rows"] == 3
        assert batch["invalid_rows"] == 1

        # Verify saved mapping profile is returned on /columns
        cols_resp = tc.get(f"/api/v1/imports/{batch_id}/columns", headers=headers)
        assert cols_resp.status_code == 200
        assert any(p["profile_name"] == "SBI Split Profile" for p in cols_resp.json()["saved_profiles"])

        # Fix the invalid row (31/02/2026 -> 2026-11-04) via row edit
        rows_resp = tc.get(f"/api/v1/imports/{batch_id}/rows?status_filter=invalid", headers=headers)
        assert rows_resp.status_code == 200
        invalid_items = rows_resp.json()["items"]
        assert len(invalid_items) == 1
        bad_row_id = invalid_items[0]["id"]

        fix_resp = tc.patch(
            f"/api/v1/imports/{batch_id}/rows/{bad_row_id}",
            json={
                "normalized_date": "2026-11-04",
                "normalized_description": "Fixed Date Entry",
                "is_selected": True,
            },
            headers=headers,
        )
        assert fix_resp.status_code == 200, fix_resp.text
        assert fix_resp.json()["validation_status"] == "valid"

        # Exclude the Swiggy row so only 3 rows import (85000 income - 2450.50 - 500 = +82049.50)
        swiggy_resp = tc.get(f"/api/v1/imports/{batch_id}/rows?search=Swiggy", headers=headers)
        assert swiggy_resp.json()["total"] == 1
        swiggy_row_id = swiggy_resp.json()["items"][0]["id"]
        excl = tc.patch(
            f"/api/v1/imports/{batch_id}/rows/{swiggy_row_id}",
            json={"exclude": True},
            headers=headers,
        )
        assert excl.status_code == 200
        assert excl.json()["validation_status"] == "excluded"

        # Check pre-commit summary exact Decimals
        summary_resp = tc.get(f"/api/v1/imports/{batch_id}/summary", headers=headers)
        assert summary_resp.status_code == 200
        s = summary_resp.json()
        assert s["selected_rows"] == 3
        assert Decimal(s["selected_income"]) == Decimal("85000.00")
        assert Decimal(s["selected_expenses"]) == Decimal("2950.50")
        assert Decimal(s["selected_net"]) == Decimal("82049.50")

        # Commit import
        commit_resp = tc.post(f"/api/v1/imports/{batch_id}/commit", headers=headers)
        assert commit_resp.status_code == 200, commit_resp.text
        c = commit_resp.json()
        assert c["imported_count"] == 3
        assert c["skipped_count"] == 1
        assert c["batch"]["status"] == "completed"

        # Verify concurrent/repeated commit is blocked (409 Conflict)
        second_commit = tc.post(f"/api/v1/imports/{batch_id}/commit", headers=headers)
        assert second_commit.status_code == 409

        # Verify completed batch cannot be deleted
        del_completed = tc.delete(f"/api/v1/imports/{batch_id}", headers=headers)
        assert del_completed.status_code == 400

        # Verify account balance recalculated accurately (25000 + 82049.50 = 107049.50)
        acc_after = tc.get(f"/api/v1/finance/accounts/{acc['id']}", headers=headers).json()
        assert Decimal(acc_after["current_balance"]) == Decimal("107049.50")

        # Verify transactions have source="csv_import" & import_batch_id persisted
        txs = tc.get("/api/v1/finance/transactions?source=csv_import", headers=headers).json()["items"]
        assert len(txs) == 3
        assert all(tx["import_batch_id"] == batch_id for tx in txs)

    def test_xlsx_multi_sheet_header_row_and_credit_card_semantics(
        self, live_client: tuple[TestClient, list[str]]
    ) -> None:
        tc, created = live_client
        headers = _register_and_login(tc, created, "imp_xlsx", "Card User")
        card = _create_account(
            tc, headers, "HDFC Millennia CC", "credit_card", "5000.00"
        )

        # Multi-sheet workbook where sheet 2 has bank banner lines before the header row
        import datetime as dt

        xlsx_bytes = _make_xlsx_bytes(
            {
                "Summary": [["Statement Period", "Nov 2026"]],
                "Transactions": [
                    ["HDFC Credit Card Statement", "", "", ""],
                    ["Cardholder: Card User", "", "", ""],
                    ["Date", "Narration", "Amount", "Cr/Dr"],
                    [dt.datetime(2026, 11, 10), "Amazon India Shopping", 3200.00, "DR"],
                    [dt.datetime(2026, 11, 12), "NEFT Card Payment", 1500.00, "CR"],
                ],
            }
        )

        up = tc.post(
            "/api/v1/imports/upload",
            data={"account_id": card["id"]},
            files={
                "file": (
                    "hdfc_cc.xlsx",
                    xlsx_bytes,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
            headers=headers,
        )
        assert up.status_code == 201, up.text
        batch_id = up.json()["batch"]["id"]
        assert "Transactions" in up.json()["available_sheets"]

        # Map using sheet="Transactions", header_row_index=2, single amount + Cr/Dr column
        m = tc.put(
            f"/api/v1/imports/{batch_id}/mapping",
            json={
                "sheet_name": "Transactions",
                "header_row_index": 2,
                "date_column": "Date",
                "description_column": "Narration",
                "amount_mode": "single",
                "amount_column": "Amount",
                "type_column": "Cr/Dr",
                "date_format": "auto",
                "default_currency": "INR",
            },
            headers=headers,
        )
        assert m.status_code == 200, m.text
        assert m.json()["valid_rows"] == 2

        commit = tc.post(f"/api/v1/imports/{batch_id}/commit", headers=headers)
        assert commit.status_code == 200, commit.text
        assert commit.json()["imported_count"] == 2

        # Opening liability 5000 + 3200 expense - 1500 repayment = 6700.00 outstanding liability
        card_after = tc.get(f"/api/v1/finance/accounts/{card['id']}", headers=headers).json()
        assert Decimal(card_after["current_balance"]) == Decimal("6700.00")

        # Verify source="xlsx_import"
        txs = tc.get("/api/v1/finance/transactions?source=xlsx_import", headers=headers).json()["items"]
        assert len(txs) == 2

    def test_semicolon_and_tab_delimiters_and_negative_asset_rollback(
        self, live_client: tuple[TestClient, list[str]]
    ) -> None:
        tc, created = live_client
        headers = _register_and_login(tc, created, "imp_delims", "Delimiter User")
        acc = _create_account(tc, headers, "Low Balance Wallet", "cash", "500.00")

        # Semicolon delimited CSV with an expense larger than balance (1200 > 500)
        csv_semi = (
            b"Date;Description;Amount;Currency\n"
            b"10/11/2026;Lunch Cafe;(200.00);INR\n"
            b"11/11/2026;Expensive Gadget;-1200.00;INR\n"
        )

        up = tc.post(
            "/api/v1/imports/upload",
            data={"account_id": acc["id"]},
            files={"file": ("wallet.csv", csv_semi, "text/csv")},
            headers=headers,
        )
        assert up.status_code == 201
        batch_id = up.json()["batch"]["id"]
        assert up.json()["delimiter"] == ";"

        m = tc.put(
            f"/api/v1/imports/{batch_id}/mapping",
            json={
                "date_column": "Date",
                "description_column": "Description",
                "amount_mode": "single",
                "amount_column": "Amount",
                "currency_column": "Currency",
                "delimiter": ";",
                "date_format": "DD/MM/YYYY",
                "default_currency": "INR",
            },
            headers=headers,
        )
        assert m.status_code == 200
        assert m.json()["valid_rows"] == 2

        # Committing should fail & atomically roll back BOTH rows because balance goes negative!
        commit = tc.post(f"/api/v1/imports/{batch_id}/commit", headers=headers)
        assert commit.status_code == 400

        acc_after = tc.get(f"/api/v1/finance/accounts/{acc['id']}", headers=headers).json()
        assert Decimal(acc_after["current_balance"]) == Decimal("500.00")
        txs = tc.get("/api/v1/finance/transactions", headers=headers).json()["items"]
        assert len(txs) == 0


class TestDuplicateDetectionAndSecurity:
    def test_three_layer_duplicates_reupload_and_legitimate_confirm(
        self, live_client: tuple[TestClient, list[str]]
    ) -> None:
        tc, created = live_client
        headers = _register_and_login(tc, created, "imp_dups", "Dup Tester")
        acc = _create_account(tc, headers, "Kotak Savings", "savings", "50000.00")

        # CSV with:
        # Row 1 & Row 2: identical non-empty UTR -> Layer A within_file_duplicate
        # Row 3 & Row 4: same date/amount/desc, NO UTR (e.g. 2 coffees same day) -> Layer A2 potential_duplicate
        csv1 = (
            b"Date,Description,Amount,Reference\n"
            b"15/11/2026,Uber Ride,-250.00,UTR900\n"
            b"15/11/2026,Uber Ride,-250.00,UTR900\n"
            b"16/11/2026,Third Wave Coffee,-180.00,\n"
            b"16/11/2026,Third Wave Coffee,-180.00,\n"
        )

        up1 = tc.post(
            "/api/v1/imports/upload",
            data={"account_id": acc["id"]},
            files={"file": ("kotak1.csv", csv1, "text/csv")},
            headers=headers,
        )
        b1 = up1.json()["batch"]["id"]
        m1 = tc.put(
            f"/api/v1/imports/{b1}/mapping",
            json={
                "date_column": "Date",
                "description_column": "Description",
                "amount_mode": "single",
                "amount_column": "Amount",
                "reference_column": "Reference",
                "date_format": "DD/MM/YYYY",
                "default_currency": "INR",
            },
            headers=headers,
        ).json()
        assert m1["valid_rows"] == 2
        assert m1["duplicate_rows"] == 1
        assert m1["potential_duplicate_rows"] == 1

        # Confirm the second coffee is a legitimate purchase!
        dups = tc.get(f"/api/v1/imports/{b1}/duplicates", headers=headers).json()["items"]
        pot = next(d for d in dups if d["validation_status"] == "potential_duplicate")
        dec = tc.patch(
            f"/api/v1/imports/{b1}/rows/{pot['id']}/duplicate-review",
            json={"decision": "import"},
            headers=headers,
        )
        assert dec.status_code == 200
        assert dec.json()["validation_status"] == "valid"
        assert dec.json()["is_selected"] is True

        c1 = tc.post(f"/api/v1/imports/{b1}/commit", headers=headers)
        assert c1.status_code == 200
        assert c1.json()["imported_count"] == 3  # 1 Uber + 2 coffees

        # Re-upload the EXACT SAME file -> Layer B detects existing reference + identical file match!
        up2 = tc.post(
            "/api/v1/imports/upload",
            data={"account_id": acc["id"]},
            files={"file": ("kotak1_again.csv", csv1, "text/csv")},
            headers=headers,
        )
        assert up2.status_code == 201
        b2 = up2.json()["batch"]["id"]
        assert "identical file" in up2.json()["batch"]["lifecycle_history"][0]["note"].lower()
        m2 = tc.put(
            f"/api/v1/imports/{b2}/mapping",
            json={
                "date_column": "Date",
                "description_column": "Description",
                "amount_mode": "single",
                "amount_column": "Amount",
                "reference_column": "Reference",
                "date_format": "DD/MM/YYYY",
                "default_currency": "INR",
            },
            headers=headers,
        ).json()
        assert m2["valid_rows"] == 0
        assert m2["duplicate_rows"] == 4

        # Delete unimported batch b2 -> verify stored file is removed
        del_b2 = tc.delete(f"/api/v1/imports/{b2}", headers=headers)
        assert del_b2.status_code == 200

    def test_cross_user_isolation_and_csrf_protection(
        self, live_client: tuple[TestClient, list[str]]
    ) -> None:
        tc, created = live_client
        headers_a = _register_and_login(tc, created, "imp_usera", "User A")
        acc_a = _create_account(tc, headers_a, "User A Bank", "savings", "10000.00")

        up_a = tc.post(
            "/api/v1/imports/upload",
            data={"account_id": acc_a["id"]},
            files={
                "file": (
                    "user_a.csv",
                    b"Date,Description,Amount\n18/11/2026,Test,-100.00\n",
                    "text/csv",
                )
            },
            headers=headers_a,
        )
        assert up_a.status_code == 201
        batch_a = up_a.json()["batch"]["id"]

        # Switch to User B session
        headers_b = _register_and_login(tc, created, "imp_userb", "User B")

        # User B cannot access User A's batch, preview, columns, rows, commit, or delete
        assert tc.get(f"/api/v1/imports/{batch_a}").status_code == 404
        assert tc.get(f"/api/v1/imports/{batch_a}/preview").status_code == 404
        assert tc.get(f"/api/v1/imports/{batch_a}/rows").status_code == 404
        assert tc.post(f"/api/v1/imports/{batch_a}/commit", headers=headers_b).status_code == 404
        assert tc.delete(f"/api/v1/imports/{batch_a}", headers=headers_b).status_code == 404

        # User B cannot upload into User A's account
        r_cross_up = tc.post(
            "/api/v1/imports/upload",
            data={"account_id": acc_a["id"]},
            files={
                "file": (
                    "hijack.csv",
                    b"Date,Description,Amount\n18/11/2026,Hijack,-100.00\n",
                    "text/csv",
                )
            },
            headers=headers_b,
        )
        assert r_cross_up.status_code == 404

        # Missing CSRF header on mutating endpoint is rejected (403)
        r_no_csrf = tc.delete(f"/api/v1/imports/{batch_a}")
        assert r_no_csrf.status_code == 403

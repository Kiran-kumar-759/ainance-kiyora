# Phase 5: Bills, Payments, Recurring Tracking & Reminders

## 1. Purpose & Accounting Integrity

The Phase 5 Bills module tracks recurring and one-time Indian household obligations (`electricity`, `water`, `gas`, `internet`, `mobile_postpaid`, `mobile_recharge`, `rent`, `insurance`, `loan_emi`, `credit_card`, `maintenance`, `other`) without creating a separate ledger system or executing automated banking debits.

- **Manual Payment Recording Only:** Recording a bill payment creates a genuine atomic `FinancialTransaction` (`source="bill_payment"`) and balanced `LedgerJournal`/`LedgerEntry` entries through `TransactionService` (or a `FinancialTransfer` reducing bank balance & credit card liability for linked `credit_card` bills). The application never collects UPI PINs, OTPs, or executes live UPI/bank debits.
- **No Double Counting in Phase 4 Analytics:** Credit card bill settlements recorded against a linked active `credit_card` account post as transfers (`transfer_id IS NOT NULL`), ensuring Phase 4 analytics reports (`Expenses`, `Dashboard`) do not double-count card statement repayments on top of individual card swipes.
- **Linking Existing Transactions:** Users who already imported a payment via CSV/XLSX (`Phase 3`) or manual entry (`Phase 2`) can attach that existing transaction directly via `/api/v1/bills/{bill_id}/payments/link-transaction`, enforced unique per transaction.

## 2. Deterministic Status Engine (`Asia/Kolkata`)

Due dates are evaluated against the user's local calendar date (default `Asia/Kolkata`, configurable via `UserPreference.timezone`), never naively assuming UTC:

- `paid`: `stored_status == 'paid'` (never flips to `overdue`).
- `archived`: `!is_active` or `stored_status == 'archived'`.
- `overdue`: `today > due_date`.
- `due_soon`: `0 <= (due_date - today).days <= BILL_DUE_SOON_DAYS` (`5` by default).
- `upcoming`: `(due_date - today).days > BILL_DUE_SOON_DAYS`.
- **Variable Bills:** Unknown variable amounts preserve `current_amount = NULL` and `remaining_due = NULL` (`is_amount_unknown = True`) rather than coercing unknown obligations to `₹0.00`.

## 3. Recurrence, Scheduler, Email & SMS Architecture

- **Anchor-Day Date Math:** `advance_due_date` preserves original billing `anchor_day` across month lengths and leap years (`Jan 31 -> Feb 28/29 -> Mar 31`), stopping cleanly at `end_date` or schedule pause. Database partial unique index `uq_bills_schedule_due_date` guarantees one active occurrence per `(parent_schedule_id, due_date)`.
- **Durable Background Processing (PostgreSQL `FOR UPDATE SKIP LOCKED`):** `ReminderScheduler` runs as an async loop inside the FastAPI lifespan (`REMINDER_SCHEDULER_ENABLED=true`, disabled automatically when `ENVIRONMENT == "test"`) because Celery/Redis are not present in this repository. Claiming due `bill_reminders` rows uses `FOR UPDATE SKIP LOCKED` plus unique `idempotency_key` (`{bill_id}:{offset_days}:{due_date}`) and `notifications.dedupe_key` (`rem:{idempotency_key}`) so duplicate alerts are prevented across concurrent ticks/workers.
- **Honest Multi-Channel Dispatch:**
  - **In-App:** Persists directly into PostgreSQL `notifications` and surfaces in both the top-header Notification Bell and the Bills -> Notifications tab.
  - **Email (`EmailService.send_bill_reminder_email`):** Uses real SMTP when `SMTP_ENABLED=true`; honestly records `channel_outcomes["email"]["status"] = "unavailable"` when disabled (`SMTP_ENABLED=false`).
  - **SMS (`SmsProviderAdapter` / `WebhookSmsAdapter`):** Validates Indian mobile numbers (`+91XXXXXXXXXX`), requires user opt-in (`notification_preferences.sms_reminders_enabled`), dispatches via configured provider webhook when `SMS_ENABLED=true`, and honestly records `"unavailable"` when `SMS_ENABLED=false`. Failed configured deliveries increment `retry_count` and schedule exponential backoff via `next_retry_at`.

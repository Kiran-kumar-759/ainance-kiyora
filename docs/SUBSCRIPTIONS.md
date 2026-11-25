# Phase 6 Module A — OTT & Subscription Management

## 1. Overview & Data Model

The Subscriptions module (`backend/app/models/subscriptions.py`) tracks OTT streaming, music, cloud storage, SaaS, gaming, fitness, news media, and user-defined recurring memberships in `INR` with `NUMERIC(19, 2)` precision:

- **`subscriptions`**: Stores subscription metadata, `amount` (nullable — missing/trial prices remain `NULL`, never coerced to `0.00`), `billing_frequency` (`weekly`, `monthly`, `quarterly`, `half_yearly`, `yearly`, `custom`), calendar `anchor_day`, trial windows (`trial_start_date`, `trial_end_date`), `cancellation_date`, `status` (`active`, `trial`, `paused`, `cancelled`, `expired`, `archived`), and reminder settings.
- **`subscription_price_history`**: Append-only price change audit trail (`previous_price`, `new_price`, `effective_date`, `reason`). Updating a price preserves all past `subscription_payments` at historical amounts and recalculates future normalized monthly/annual projections cleanly.
- **`subscription_payments`**: Confirmed payments recorded via `/api/v1/subscriptions/{id}/payments` or linked from existing transactions (`/link-transaction`), protected by partial unique index `uq_sub_payments_idempotency` on `(user_id, subscription_id, idempotency_key)`.
- **`subscription_candidate_decisions`**: Persists user review choices (`ignored` or `linked`) for deterministic recurring-payment candidate suggestions.

## 2. Frequency Normalization & Renewal Engine

Implemented in `backend/app/services/subscriptions/subscription_math.py`:
- **Monthly / Annual Equivalents (Python `Decimal`, `ROUND_HALF_UP`):**
  - `weekly`: `annual = amount * 52`, `monthly = (amount * 52) / 12`
  - `monthly`: `monthly = amount`, `annual = amount * 12`
  - `quarterly`: `monthly = amount / 3`, `annual = amount * 4`
  - `half_yearly`: `monthly = amount / 6`, `annual = amount * 2`
  - `yearly`: `monthly = amount / 12`, `annual = amount`
  - `custom`: `monthly = (amount * 30) / custom_interval_days`, `annual = (amount * 365) / custom_interval_days`
- **Calendar Rollover:** Reuses `advance_due_date` preserving `anchor_day` across month lengths (`Jan 31 → Feb 28/29 → Mar 31`) and leap years.
- **No Auto-Posting:** Advancing or scheduling a renewal **never** creates a confirmed financial transaction automatically. Only explicit user payment recording or linking affects the ledger and Phase 4 actual expense analytics.
- **Lifecycle Isolation:** `paused`, `cancelled`, `expired`, and `archived` subscriptions are excluded from active recurring cost totals and stop pending reminders immediately via `ReminderService.sync_reminders_for_subscription`.

## 3. Deterministic Recurring-Payment Candidates

`detect_subscription_candidates` inspects historical unlinked expense transactions (`transfer_id IS NULL`, non-disconnected accounts), skips bill/EMI/utility/insurance keywords via word-boundary regex (`NON_SUBSCRIPTION_PATTERN`), groups normalized merchant tokens with consistent amounts (<=10% variance) and weekly/monthly/quarterly/half-yearly/yearly intervals (>=2 occurrences), and surfaces **review-only** candidates (`Create Subscription` or `Ignore`). No LLM/ML or auto-creation is performed in Phase 6.

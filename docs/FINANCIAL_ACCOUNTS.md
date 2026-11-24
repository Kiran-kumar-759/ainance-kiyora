# Financial Accounts Architecture & Operations

**Project:** AI Personal Finance Manager — India  
**Phase:** Phase 2  
**Target Region:** India (INR, en-IN)

---

## 1. Overview

The Financial Accounts module provides multi-account management for authenticated users in India. Users can establish asset accounts, credit liability accounts, and digital wallets with opening positions and complete transaction histories.

---

## 2. Supported Account Types

| Account Type | Key | Typical Indian Institution / Example | Balance Semantic |
| :--- | :--- | :--- | :--- |
| **Savings Account** | `savings` | HDFC Bank, SBI, ICICI Bank | Asset (Debit Balance) |
| **Current Account** | `current` | Kotak Mahindra, Axis Bank | Asset (Debit Balance) |
| **Cash Account** | `cash` | Cash in Hand / Physical Wallet | Asset (Debit Balance) |
| **Credit Card** | `credit_card` | ICICI Coral, Axis Ace, SBI SimplyCLICK | Liability (Credit Balance / Debt) |
| **Digital Wallet** | `digital_wallet` | Paytm Wallet, PhonePe Wallet, Amazon Pay | Asset (Debit Balance) |
| **Other Account** | `other` | Investment Broker Cash Ledger / Miscellaneous | Asset (Debit Balance) |

---

## 3. Account Schema (`financial_accounts`)

| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | `UUID` | Primary Key |
| `user_id` | `UUID` | Foreign Key (`users.id`, `ON DELETE CASCADE`) |
| `name` | `VARCHAR(100)` | User-defined label (e.g. "Salary HDFC") |
| `account_type` | `VARCHAR(30)` | One of the 6 supported account types |
| `institution_name` | `VARCHAR(100)` | Optional bank name (e.g. "State Bank of India") |
| `account_identifier` | `VARCHAR(50)` | Optional masked reference (e.g. `••4821`) |
| `currency` | `VARCHAR(3)` | Default `INR` |
| `opening_balance` | `NUMERIC(19, 2)` | Initial position at account setup |
| `current_balance` | `NUMERIC(19, 2)` | Authoritatively synchronized ledger balance |
| `status` | `VARCHAR(20)` | `active` or `archived` |
| `source` | `VARCHAR(30)` | `manual` or `demo_bank` |
| `created_at` | `TIMESTAMPTZ` | Record creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | Last metadata or balance update timestamp |

---

## 4. Lifecycle & Safety Operations

### 4.1 Account Creation & Opening Balance
- On creation, user supplies name, type, optional institution and masked number, and opening balance.
- If `opening_balance > 0`, an `opening_balance` journal entry is posted to the double-entry ledger.
- Balances are authoritatively recalculated from the ledger.

### 4.2 Opening Balance Corrections
- If an opening balance was entered incorrectly, users can correct it via `PATCH /api/v1/finance/accounts/{id}/opening-balance`.
- Previous opening balance journal is marked `is_reversed = True`.
- New opening balance journal is posted with the corrected amount.
- Account balance is automatically resynchronized.

### 4.3 Safe Archival (No Physical Deletion)
- Accounts with financial transaction history are never hard-deleted.
- Deleting an account with history would break accounting integrity and historical reporting.
- Users can archive accounts via `POST /api/v1/finance/accounts/{id}/archive`.
- Archived accounts preserve all historical transactions and ledger postings.
- Archived accounts can be restored via `POST /api/v1/finance/accounts/{id}/restore`.

### 4.4 Data Isolation & Ownership
- Every account repository method enforces `WHERE user_id = current_user.id`.
- Any attempt by User A to view, update, archive, or restore User B's account returns HTTP 404.

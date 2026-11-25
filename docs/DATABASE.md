# Database Architecture & Policies — PostgreSQL & Alembic

## 1. Overview & Source of Truth

PostgreSQL is the single source of truth for the AI Personal Finance Manager. SQLite or browser `localStorage` fallbacks are strictly prohibited for application state persistence.

- **PostgreSQL Version:** 18.6
- **Driver:** `psycopg` (Version 3)
- **ORM / Toolkit:** SQLAlchemy 2.x
- **Migration Engine:** Alembic 1.20+
- **Development Database:** `pfm_dev`
- **Testing Database:** `pfm_test`

---

## 2. Core Integrity Rules

1. **Exact Financial Arithmetic:**
   - Float types (`FLOAT`, `DOUBLE PRECISION`) are **strictly prohibited** for monetary amounts.
   - All financial balances, transaction amounts, and EMIs must use PostgreSQL `NUMERIC(18, 4)` and Python `decimal.Decimal`.
2. **Strict Schema Migration:**
   - Any database modification must be tracked through an Alembic migration script.
   - Direct manual DDL changes in production or development environments without corresponding migrations are disallowed.
3. **No Fabricated Records:**
   - Development and demo environments must not populate fabricated balances or phantom transactions.
   - All numbers presented in user views must reflect legitimate persisted entities.
4. **Data Isolation:**
   - Multi-tenant user data will be partitioned by strict user ID ownership starting in Phase 1.
5. **No SQLite Fallback:**
   - The test suite executes directly against a dedicated real PostgreSQL test database (`pfm_test`).

---

## 3. SQLAlchemy Configuration

Configured in `backend/app/db/session.py`:

```python
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,      # Tests connection health before yielding from pool
    pool_size=5,             # Baseline persistent connections
    max_overflow=10,         # Burst connection allowance
    pool_timeout=30,         # Connection timeout seconds
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)
```

Dependency Injection in FastAPI endpoints:
```python
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
```

---

## 4. Alembic Migration Workflow

### Configuration
- `backend/alembic.ini`: Configured with relative paths and log levels.
- `backend/alembic/env.py`: Dynamically reads `settings.DATABASE_URL` from the application configuration and registers `Base.metadata`.

### Common Commands

```bash
# Navigate to backend directory
cd backend

# Create a new migration revision
./venv/bin/alembic revision --autogenerate -m "description_of_change"

# Upgrade development database to latest revision
./venv/bin/alembic upgrade head

# Upgrade test database to latest revision
DATABASE_URL="postgresql+psycopg://tenderpilot:tenderpilot@localhost:5432/pfm_test" ./venv/bin/alembic upgrade head

# Downgrade by one revision
./venv/bin/alembic downgrade -1

# Inspect current revision status
./venv/bin/alembic current
```

---

## 5. Schema Revisions & Entities

### 5.1 System Foundation (`system_settings`) — Phase 0

The Phase 0 schema contains the system foundation metadata entity (`system_settings`) to verify end-to-end ORM, repository, and API workflows:

```sql
CREATE TABLE system_settings (
    id SERIAL PRIMARY KEY,
    key VARCHAR(100) UNIQUE NOT NULL,
    value JSON NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX ix_system_settings_key ON system_settings(key);
```

### 5.2 Identity, Sessions & Preferences — Phase 1 (Revision `987e7368d0c9`)

Phase 1 introduces the complete multi-user authentication, session, and isolation tables:

```sql
-- Core User Account
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(150) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    onboarding_completed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMP WITH TIME ZONE
);
CREATE UNIQUE INDEX ix_users_email ON users(email);

-- Active User Sessions (Server-side opaque token hashes)
CREATE TABLE user_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(64) UNIQUE NOT NULL,
    user_agent VARCHAR(500),
    ip_address VARCHAR(45),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMP WITH TIME ZONE
);
CREATE INDEX ix_user_sessions_user_id ON user_sessions(user_id);
CREATE UNIQUE INDEX ix_user_sessions_token_hash ON user_sessions(token_hash);
CREATE INDEX ix_user_sessions_expires_at ON user_sessions(expires_at);
CREATE INDEX ix_user_sessions_revoked_at ON user_sessions(revoked_at);

-- Email Verification Single-Use Tokens
CREATE TABLE email_verification_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(64) UNIQUE NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    used_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX ix_email_verification_tokens_token_hash ON email_verification_tokens(token_hash);
CREATE INDEX ix_email_verification_tokens_user_id ON email_verification_tokens(user_id);

-- Password Reset Single-Use Tokens
CREATE TABLE password_reset_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(64) UNIQUE NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    used_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX ix_password_reset_tokens_token_hash ON password_reset_tokens(token_hash);
CREATE INDEX ix_password_reset_tokens_user_id ON password_reset_tokens(user_id);

-- Regional & User Preferences (India Defaults)
CREATE TABLE user_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    preferred_currency VARCHAR(10) NOT NULL DEFAULT 'INR',
    locale VARCHAR(20) NOT NULL DEFAULT 'en-IN',
    timezone VARCHAR(50) NOT NULL DEFAULT 'Asia/Kolkata',
    date_format VARCHAR(20) NOT NULL DEFAULT 'DD/MM/YYYY',
    notification_preferences JSON NOT NULL DEFAULT '{}'::json,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX ix_user_preferences_user_id ON user_preferences(user_id);

-- PHASE 2: FINANCIAL ENGINE & BANKING SCHEMA (Migration: d816f0127538)

-- Financial Accounts
CREATE TABLE financial_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    account_type VARCHAR(30) NOT NULL, -- savings, current, cash, credit_card, digital_wallet, other
    institution_name VARCHAR(100),
    account_identifier VARCHAR(50),
    currency VARCHAR(3) NOT NULL DEFAULT 'INR',
    opening_balance NUMERIC(19, 2) NOT NULL DEFAULT 0.00,
    current_balance NUMERIC(19, 2) NOT NULL DEFAULT 0.00,
    status VARCHAR(20) NOT NULL DEFAULT 'active', -- active, archived
    source VARCHAR(30) NOT NULL DEFAULT 'manual', -- manual, demo_bank
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_financial_accounts_user_id ON financial_accounts(user_id);
CREATE INDEX ix_financial_accounts_user_status ON financial_accounts(user_id, status);

-- Financial Categories
CREATE TABLE financial_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE, -- NULL for system categories
    name VARCHAR(100) NOT NULL,
    category_type VARCHAR(20) NOT NULL, -- income, expense
    icon VARCHAR(50),
    color VARCHAR(30),
    is_system BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_financial_categories_user_id ON financial_categories(user_id);
CREATE INDEX ix_financial_categories_user_type ON financial_categories(user_id, category_type);

-- Financial Transfers
CREATE TABLE financial_transfers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source_account_id UUID NOT NULL REFERENCES financial_accounts(id) ON DELETE RESTRICT,
    destination_account_id UUID NOT NULL REFERENCES financial_accounts(id) ON DELETE RESTRICT,
    amount NUMERIC(19, 2) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'INR',
    transfer_date DATE NOT NULL,
    description VARCHAR(255),
    status VARCHAR(20) NOT NULL DEFAULT 'completed', -- completed, reversed
    reversal_reason VARCHAR(255),
    reversed_at TIMESTAMP WITH TIME ZONE,
    source_transaction_id UUID,
    destination_transaction_id UUID,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_financial_transfers_user_id ON financial_transfers(user_id);

-- Financial Transactions
CREATE TABLE financial_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    account_id UUID NOT NULL REFERENCES financial_accounts(id) ON DELETE RESTRICT,
    transaction_type VARCHAR(20) NOT NULL, -- income, expense, transfer
    amount NUMERIC(19, 2) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'INR',
    category_id UUID REFERENCES financial_categories(id) ON DELETE SET NULL,
    description VARCHAR(255) NOT NULL,
    merchant_payee VARCHAR(150),
    transaction_date DATE NOT NULL,
    notes TEXT,
    source VARCHAR(30) NOT NULL DEFAULT 'manual', -- manual, demo_bank
    external_reference VARCHAR(100),
    transfer_id UUID REFERENCES financial_transfers(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_financial_transactions_user_id ON financial_transactions(user_id);
CREATE INDEX ix_financial_transactions_account_id ON financial_transactions(account_id);
CREATE INDEX ix_financial_transactions_category_id ON financial_transactions(category_id);
CREATE INDEX ix_financial_transactions_transaction_date ON financial_transactions(transaction_date);
CREATE INDEX ix_financial_transactions_user_date ON financial_transactions(user_id, transaction_date);
CREATE INDEX ix_financial_transactions_user_account_date ON financial_transactions(user_id, account_id, transaction_date);
CREATE UNIQUE INDEX uq_transactions_user_account_ext_ref ON financial_transactions(user_id, account_id, external_reference) WHERE external_reference IS NOT NULL;

-- Double-Entry Ledger Journals
CREATE TABLE ledger_journals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    transaction_id UUID REFERENCES financial_transactions(id) ON DELETE CASCADE,
    transfer_id UUID REFERENCES financial_transfers(id) ON DELETE CASCADE,
    journal_type VARCHAR(30) NOT NULL, -- opening_balance, income, expense, transfer, reversal
    reference VARCHAR(100),
    description VARCHAR(255) NOT NULL,
    entry_date DATE NOT NULL,
    is_reversed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_ledger_journals_user_id ON ledger_journals(user_id);
CREATE INDEX ix_ledger_journals_transaction_id ON ledger_journals(transaction_id);
CREATE INDEX ix_ledger_journals_transfer_id ON ledger_journals(transfer_id);

-- Double-Entry Ledger Entries (Debits & Credits)
CREATE TABLE ledger_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    journal_id UUID NOT NULL REFERENCES ledger_journals(id) ON DELETE CASCADE,
    account_id UUID REFERENCES financial_accounts(id) ON DELETE RESTRICT, -- NULL for external balancing offsets
    entry_type VARCHAR(10) NOT NULL, -- debit, credit
    amount NUMERIC(19, 2) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'INR',
    description VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_ledger_entries_journal_id ON ledger_entries(journal_id);
CREATE INDEX ix_ledger_entries_account_id ON ledger_entries(account_id);

-- Simulated Banking Connections
CREATE TABLE banking_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider_id VARCHAR(50) NOT NULL, -- demo_national_bank, demo_private_bank, demo_digital_bank
    institution_name VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'connected', -- connected, disconnected, error
    consent_granted_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    consent_scope VARCHAR(100) NOT NULL DEFAULT 'accounts,transactions',
    is_simulated BOOLEAN NOT NULL DEFAULT TRUE,
    last_sync_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_banking_connections_user_id ON banking_connections(user_id);
CREATE INDEX ix_banking_connections_provider_id ON banking_connections(provider_id);

-- Banking Synchronization Audit Runs
CREATE TABLE banking_sync_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connection_id UUID NOT NULL REFERENCES banking_connections(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'success', -- success, failed, partial
    accounts_synced INTEGER NOT NULL DEFAULT 0,
    transactions_synced INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);
CREATE INDEX ix_banking_sync_runs_connection_id ON banking_sync_runs(connection_id);
CREATE INDEX ix_banking_sync_runs_user_id ON banking_sync_runs(user_id);

-- Phase 3: Bank Statement Import Batches
CREATE TABLE import_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    account_id UUID NOT NULL REFERENCES financial_accounts(id) ON DELETE RESTRICT,
    original_filename VARCHAR(255) NOT NULL,
    file_hash VARCHAR(64) NOT NULL,
    file_size INTEGER NOT NULL,
    file_type VARCHAR(10) NOT NULL, -- csv, xlsx
    storage_key VARCHAR(500),
    status VARCHAR(30) NOT NULL DEFAULT 'uploaded',
    sheet_name VARCHAR(100),
    header_row_index INTEGER NOT NULL DEFAULT 0,
    delimiter VARCHAR(5),
    total_rows INTEGER NOT NULL DEFAULT 0,
    valid_rows INTEGER NOT NULL DEFAULT 0,
    invalid_rows INTEGER NOT NULL DEFAULT 0,
    needs_review_rows INTEGER NOT NULL DEFAULT 0,
    duplicate_rows INTEGER NOT NULL DEFAULT 0,
    potential_duplicate_rows INTEGER NOT NULL DEFAULT 0,
    imported_rows INTEGER NOT NULL DEFAULT 0,
    skipped_rows INTEGER NOT NULL DEFAULT 0,
    total_income NUMERIC(19, 2) NOT NULL DEFAULT 0.00,
    total_expenses NUMERIC(19, 2) NOT NULL DEFAULT 0.00,
    mapping_configuration JSON,
    inspection_metadata JSON,
    lifecycle_history JSON NOT NULL DEFAULT '[]',
    failure_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);
CREATE INDEX ix_import_batches_user_created ON import_batches(user_id, created_at);
CREATE INDEX ix_import_batches_user_account_hash ON import_batches(user_id, account_id, file_hash);

-- Phase 3: Normalized Statement Import Rows
CREATE TABLE import_rows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    import_batch_id UUID NOT NULL REFERENCES import_batches(id) ON DELETE CASCADE,
    source_row_number INTEGER NOT NULL,
    raw_row_data JSON NOT NULL,
    normalized_date DATE,
    normalized_description VARCHAR(255),
    normalized_merchant VARCHAR(150),
    normalized_notes TEXT,
    normalized_amount NUMERIC(19, 2),
    normalized_type VARCHAR(20), -- income, expense
    currency VARCHAR(3) NOT NULL DEFAULT 'INR',
    transaction_reference VARCHAR(100),
    running_balance NUMERIC(19, 2),
    row_fingerprint VARCHAR(64),
    validation_status VARCHAR(30) NOT NULL DEFAULT 'valid',
    duplicate_status VARCHAR(40) NOT NULL DEFAULT 'none',
    duplicate_match_transaction_id UUID,
    duplicate_match_row_id UUID,
    validation_errors JSON NOT NULL DEFAULT '[]',
    category_id UUID REFERENCES financial_categories(id) ON DELETE SET NULL,
    is_selected BOOLEAN NOT NULL DEFAULT FALSE,
    review_changes JSON,
    imported_transaction_id UUID REFERENCES financial_transactions(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_import_rows_batch_status ON import_rows(import_batch_id, validation_status);
CREATE INDEX ix_import_rows_batch_row_num ON import_rows(import_batch_id, source_row_number);

-- Phase 3: Saved Per-User Column Mapping Profiles
CREATE TABLE import_mapping_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    profile_name VARCHAR(100) NOT NULL,
    file_format VARCHAR(10) NOT NULL, -- csv, xlsx
    mapping_configuration JSON NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_import_mapping_profiles_user_id ON import_mapping_profiles(user_id);

-- Phase 3 additions to financial_transactions:
-- import_batch_id UUID REFERENCES import_batches(id) ON DELETE SET NULL
-- import_row_id UUID
```

---

## Phase 4 Analytics Query Architecture (No Additional Schema Migration Needed)

Phase 4 runs deterministic SQL aggregations directly against the authoritative tables at Alembic revision **`26be763a8a0a (head)`**, avoiding redundant summary tables or stale balance caches:

- **Composite Time-Range Indexes Utilized:**
  - `ix_financial_transactions_user_date` (`user_id`, `transaction_date`)
  - `ix_financial_transactions_user_account_date` (`user_id`, `account_id`, `transaction_date`)
  - `ix_financial_transactions_category_id` (`category_id`)
  - `ix_ledger_journals_user_id`, `ix_ledger_entries_account_id`, `ix_ledger_entries_journal_id`
- **Accounting Isolation:** Analytics queries filter `transfer_id IS NULL`, `transaction_type IN ('income', 'expense')`, `FinancialAccount.status != 'disconnected'`, and exclude solely-reversed `LedgerJournal` entries directly in PostgreSQL.
- **Historical Balances:** `TrendAnalytics` reconstructs balance curves chronologically from `ledger_entries` joined to unreversed `ledger_journals` (`is_reversed = FALSE`).

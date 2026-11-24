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
```

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

## 5. Phase 0 Schema

The Phase 0 schema contains only the system foundation metadata entity (`system_settings`) to verify end-to-end ORM, repository, and API workflows:

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

# AI Personal Finance Manager — India (Phase 1: Authentication & User Management)

An India-first, multi-user SaaS AI Personal Finance Manager designed for exact financial calculations, strict user data privacy, secure server-side sessions, and a modular monolithic architecture.

---

## 1. Project Overview

This repository includes **Phase 0: Product Foundation + Functional Demo UI** and **Phase 1: Authentication, User Management, Account Isolation & Onboarding**.

### Key Foundation Highlights
- **India-First Regional Configuration:** Native Indian Rupee (`₹` / `INR`), Indian number system (Lakhs and Crores), Indian fiscal year calendar (April 1 to March 31), and Asia/Kolkata timezone handling.
- **Enterprise Identity & Authentication (Phase 1):**
  - Argon2id password hashing (`m=65536, t=3, p=4, keylen=32`).
  - Server-side opaque session tokens stored as SHA-256 hashes in PostgreSQL; zero plaintext tokens in database or client storage.
  - Double-submit CSRF protection on mutating requests (`pfm_csrf` cookie + `X-CSRF-Token` header).
  - Rate limiting (sliding window in-memory limiter).
  - Provider-independent email delivery adapter with responsive HTML templates.
  - Multi-step onboarding wizard with regional preference defaults (INR, en-IN, Asia/Kolkata).
  - Multi-session management (active sessions inspection, single-session revocation, logout-all).
  - Strict row-level multi-tenant account isolation enforced across all database queries.
- **Exact Financial Precision:** Decimal/NUMERIC typing policy preventing floating-point rounding errors.
- **PostgreSQL as Single Source of Truth:** Real database connectivity with connection pooling, Alembic migration management (`987e7368d0c9`), and automated readiness probes.
- **Modular Monolith Architecture:** Explicit boundaries between API routes, domain services, repositories, schemas, and models.
- **Connected Functional UI:** Live React demo interface with complete registration, login, session restoration, onboarding wizard, user profile, preferences, session management, and system diagnostics.

---

## 2. Technology Stack

- **Backend:** Python 3.14+, FastAPI, SQLAlchemy 2.x, Alembic, psycopg3, Pydantic v2, pytest, Ruff.
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, Lucide Icons, Vitest.
- **Database:** PostgreSQL 18.6 with connection pooling and transactional DDL.
- **Background Tasks:** Valkey / Redis 8.0+ (Port 6379, ready for Celery worker integration).

---

## 3. Repository Structure

```text
.
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── routes/          # /health, /api/v1/system
│   │   ├── core/                # Configuration, logging, security
│   │   ├── db/                  # Engine, sessionmaker, declarative base
│   │   ├── models/              # SQLAlchemy 2.x models (SystemSetting)
│   │   ├── repositories/        # Persistence & query abstraction
│   │   ├── schemas/             # Pydantic v2 validation models
│   │   ├── services/            # Domain business logic
│   │   └── main.py              # Application factory & lifespan
│   ├── alembic/                 # Database migrations
│   ├── tests/                   # Pytest test suite (real PostgreSQL)
│   ├── alembic.ini              # Alembic configuration
│   ├── pyproject.toml           # Tooling & dependency specs
│   ├── requirements.txt         # Pinned backend dependencies
│   └── .env.example             # Template environment variables
├── frontend/
│   ├── src/
│   │   ├── app/                 # Root App component
│   │   ├── components/          # Reusable UI components (Badge, Card)
│   │   ├── features/            # Feature views (SystemStatusView)
│   │   ├── layouts/             # AppShell & responsive navigation
│   │   ├── lib/                 # App configuration & constants
│   │   ├── services/            # Typed API client
│   │   ├── types/               # TypeScript interfaces
│   │   ├── test/                # Vitest test suite
│   │   └── main.tsx             # Application entry point
│   ├── package.json             # NPM dependencies & scripts
│   ├── vite.config.ts           # Vite build & test configuration
│   └── .env.example             # Frontend environment template
├── docs/
│   ├── ARCHITECTURE.md          # Architecture blueprint & diagrams
│   ├── DATABASE.md              # Database setup, rules & migrations
│   ├── DEVELOPMENT.md           # Local setup & developer workflow
│   └── PHASE_0_REPORT.md        # Comprehensive completion report
├── .gitignore                   # Ignore rules for secrets, venv, node_modules
├── .env.example                 # Root configuration template
└── README.md                    # Project overview & documentation
```

---

## 4. Quickstart Guide

### 4.1 Prerequisites
- PostgreSQL 18+ running on `localhost:5432`
- Python 3.12+ (Python 3.14 compatible)
- Node.js 20+ (Node v22 compatible)

### 4.2 Database Initialization
```bash
# Create databases
psql -h localhost -U tenderpilot -c "CREATE DATABASE pfm_dev;"
psql -h localhost -U tenderpilot -c "CREATE DATABASE pfm_test;"
```

### 4.3 Backend Setup & Startup
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 4.4 Frontend Setup & Startup
```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```
Open [http://127.0.0.1:5173](http://127.0.0.1:5173) in your browser.

---

## 5. Verification & Testing

### Backend Unit & Integration Tests (PostgreSQL)
```bash
cd backend
./venv/bin/pytest
```

### Frontend Tests
```bash
cd frontend
npm test
```

### Frontend Production Build
```bash
cd frontend
npm run build
```

---

## 6. Phase Documentation Links

- [Authentication Architecture & Security](file:///home/ckirankumar/Finance%20AI/docs/AUTHENTICATION.md)
- [Architecture Blueprint](file:///home/ckirankumar/Finance%20AI/docs/ARCHITECTURE.md)
- [API & External Service Integration Register](file:///home/ckirankumar/Finance%20AI/docs/API_INTEGRATION_REGISTER.md)
- [Database Design & Policies](file:///home/ckirankumar/Finance%20AI/docs/DATABASE.md)
- [Developer Guide](file:///home/ckirankumar/Finance%20AI/docs/DEVELOPMENT.md)
- [Phase 0 Completion Report](file:///home/ckirankumar/Finance%20AI/docs/PHASE_0_REPORT.md)
- [Phase 1 Completion Report](file:///home/ckirankumar/Finance%20AI/docs/PHASE_1_REPORT.md)
- [Phase 11 Integration Audit](file:///home/ckirankumar/Finance%20AI/PHASE_11_INTEGRATION_AUDIT.md)
- [Phase 11 Security Audit](file:///home/ckirankumar/Finance%20AI/PHASE_11_SECURITY_AUDIT.md)
- [Phase 11 Test Report](file:///home/ckirankumar/Finance%20AI/PHASE_11_TEST_REPORT.md)
- [Phase 11 Release Readiness](file:///home/ckirankumar/Finance%20AI/PHASE_11_RELEASE_READINESS.md)

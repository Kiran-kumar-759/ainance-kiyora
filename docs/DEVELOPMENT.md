# Local Development Guide — AI Personal Finance Manager

This guide covers setup, running, testing, and troubleshooting the AI Personal Finance Manager.

---

## 1. Prerequisites

- **Operating System:** Linux / macOS / WSL2
- **Python:** 3.12+ (Tested on Python 3.14.7)
- **Node.js:** 20+ (Tested on Node.js v22.23.3, npm 10.9.9)
- **PostgreSQL:** 16+ (Tested on PostgreSQL 18.6)
- **Valkey / Redis:** 7+ (Active on 127.0.0.1:6379)

---

## 2. Initial Setup

### 2.1 Database Setup
Ensure PostgreSQL is active and provision the development and test databases:

```bash
# Create development and test databases in PostgreSQL
psql -h localhost -U tenderpilot -c "CREATE DATABASE pfm_dev;"
psql -h localhost -U tenderpilot -c "CREATE DATABASE pfm_test;"
```

### 2.2 Backend Setup
```bash
cd backend

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your local PostgreSQL credentials if different

# Run database migrations
alembic upgrade head
```

### 2.3 Frontend Setup
```bash
cd ../frontend

# Install npm dependencies
npm install

# Configure environment variables
cp .env.example .env
```

---

## 3. Running the Development Servers

### Terminal 1: Backend (FastAPI)
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
API Documentation will be accessible at:
- Swagger UI: `http://127.0.0.1:8000/api/docs`
- ReDoc: `http://127.0.0.1:8000/api/redoc`
- Liveness Probe: `http://127.0.0.1:8000/health`
- Readiness Probe: `http://127.0.0.1:8000/health/ready`

### Terminal 2: Frontend (React + Vite)
```bash
cd frontend
npm run dev
```
Open `http://127.0.0.1:5173` in your browser.

---

## 4. Running Tests & Quality Checks

### Backend Tests (pytest)
Runs against real PostgreSQL `pfm_test` database (verifies system health, auth flows, Argon2id hashing, CSRF verification, rate limiting, and multi-user data isolation):
```bash
cd backend
./venv/bin/pytest -v
```

### Inspecting Sent Test Emails
In development and automated testing, emails (verification links, password reset codes) are captured in-memory by `email_service.mailbox`:
```python
from app.services.email_service import email_service
# In pytest fixtures or test assertions:
last_email = email_service.mailbox[-1]
print(last_email["subject"], last_email["html_content"])
```

### Backend Linting & Formatting (Ruff)
```bash
cd backend
./venv/bin/ruff check .
./venv/bin/ruff format .
```

### Frontend Tests (Vitest)
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

## 5. Troubleshooting

- **PostgreSQL Peer Auth Failure:**
  Ensure you connect via TCP host (`127.0.0.1` or `localhost`) rather than default Unix domain socket if using password authentication.
- **CORS Errors:**
  Verify that the frontend origin (`http://localhost:5173` and `http://127.0.0.1:5173`) is listed in `backend/.env` under `CORS_ORIGINS`.
- **Database Degraded (503):**
  If `GET /health/ready` returns 503, verify that the PostgreSQL service is active (`systemctl status postgresql-18`) and credentials in `.env` match.

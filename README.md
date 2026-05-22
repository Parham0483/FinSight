# FinSight

> AI-powered cash flow intelligence for UK import/export SMEs

**Know your cash position in 30 seconds. Understand what's coming in 30 days. In plain English.**

## What it does

FinSight connects to your business bank accounts via TrueLayer open banking, ingests real transaction history, tracks multi-currency FX exposure, runs a statistical forecasting engine, and delivers daily natural-language financial briefings via Claude Sonnet.

Built for UK import/export SMEs managing multi-currency cash flows — no finance background required.

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Django 5 + Django REST Framework |
| Auth | JWT via `djangorestframework-simplejwt` (HttpOnly cookies) |
| Task queue | Celery + Redis |
| Database | PostgreSQL 15 |
| Forecasting | `statsmodels` Holt-Winters + EWMA |
| AI | Claude Sonnet (Anthropic) — structured outputs |
| Open banking | TrueLayer Data API |
| FX rates | ExchangeRate-API + Alpha Vantage |
| Frontend | React 18 + TypeScript + Vite + Recharts |
| Infra | Docker Compose + Nginx |

## Quick start (development)

### Prerequisites
- Docker Desktop
- API keys (see `.env.example`)

### 1. Clone and configure
```bash
git clone <repo>
cd finSight
cp .env.example .env
# Fill in .env with your API keys
```

### 2. Generate required secrets
```bash
# Django secret key
python -c "import secrets; print(secrets.token_hex(50))"

# Fernet encryption key (for bank tokens at rest)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 3. Start the full stack
```bash
docker compose up --build
```

Services:
- Frontend: http://localhost:5173
- Django API: http://localhost:8000
- Django Admin: http://localhost:8000/admin
- API docs: http://localhost:8000/api/v1/

### 4. Load demo data (optional)
```bash
docker compose exec backend python manage.py seed_demo_org
```

## Architecture

```
Frontend (React/Vite)
       │
       │ REST API (JWT cookies)
       ▼
Django REST API ──── PostgreSQL
       │         └── Redis
       │                │
       └────── Celery Worker
                    │
                    └── Celery Beat (cron)

External:
  TrueLayer  → bank data
  Anthropic  → AI briefings
  ExchangeRate-API → live FX
  Alpha Vantage → historical FX
```

## API keys needed

| Service | Free tier | Where to get |
|---|---|---|
| TrueLayer | Unlimited sandbox | console.truelayer.com |
| Anthropic | Pay per use | console.anthropic.com |
| ExchangeRate-API | 1,500 req/month | exchangerate-api.com |
| Alpha Vantage | 25 req/day | alphavantage.co |

## Sprint plan

- **Month 1**: Core infrastructure, TrueLayer banking, transaction management
- **Month 2**: Forecasting engine, FX dashboard, AI insights, customer risk
- **Month 3**: Scenario modelling, alerts, demo mode, production hardening

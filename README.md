# CreditGuard AI — Credit Card Fraud Detection Dashboard

A **working educational full-stack demonstration** with a React dashboard, FastAPI backend, SQLAlchemy database, and scikit-learn fraud classifier.

**IMPORTANT: This is a synthetic demo.** The included ML model is trained on artificially generated, credit-card-like transaction features. Its evaluation metrics measure performance only on synthetic data, **not real credit-card fraud detection**. No real card numbers, payments, bank accounts, or banking connections are used. Do not deploy for real fraud decisions.

## What is included

- Frontend: Dashboard, New Transaction, Transaction History, Fraud Alerts, Customers, Model Analytics.
- Backend: customer APIs, transaction prediction and persistence, fraud alerts, charts, model metadata.
- Database: SQLite by default, optional PostgreSQL via `DATABASE_URL` and Docker Compose.
- ML: reproducible synthetic training script, saved Random Forest model, model metadata.
- Demo seed: four fictional customers and 70 synthetic transactions.

## Quick start (Windows PowerShell, from project root)

### 1. Backend

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd ..
python ml/train.py
python database/seed.py
cd backend
uvicorn app.main:app --reload
```

Backend: http://127.0.0.1:8000/docs

### 2. Frontend (new terminal)

```powershell
cd frontend
npm install
npm run dev
```

Frontend: http://127.0.0.1:5173

### macOS / Linux

Use `source backend/venv/bin/activate` rather than the Windows activation command. Other commands are the same.

### PostgreSQL instead of SQLite (optional)

1. From root run `docker compose up -d`.
2. Set `DATABASE_URL=postgresql+psycopg://creditguard:creditguard@localhost:5432/creditguard` in your terminal environment **before** starting the backend and running `database/seed.py`.
3. Tables are created automatically at startup or during seeding. The default SQLite DB is otherwise used.

## Data contract

The **ML model uses only seven features**: `distance_from_home`, `distance_from_last_transaction`, `ratio_to_median_purchase_price`, `repeat_retailer`, `used_chip`, `used_pin_number`, `online_order`.

`amount`, `merchant`, `category`, `location`, and `hour` are stored and displayed but **do not affect the current model's predictions**. This is intentional to prevent misleading claims about model inputs. The distances and purchase ratio are **manually entered demo features**, not calculated from customer transaction history.

The model outputs a probability, a validation-set-chosen threshold, and a predicted flag. The shown input signals are descriptive checks, **not model explainability/SHAP**.

## API endpoints

- `GET /api/health`
- `GET /api/customers`, `POST /api/customers`, `GET /api/customers/{id}`
- `POST /api/transactions`, `GET /api/transactions`, `GET /api/transactions/{id}`
- `GET /api/alerts`, `PATCH /api/alerts/{id}`
- `GET /api/dashboard/summary`, `GET /api/dashboard/charts`
- `GET /api/model/info`, `GET /api/model/metrics`

Full interactive API docs at `/docs`.

## Project files

```
frontend/     React + Vite frontend
backend/app/  FastAPI, SQLAlchemy models, prediction service
ml/           Synthetic training and serialized model
ml/artifacts/ Model joblib and metadata JSON
 database/    Sample data seed script
```

## Next improvements for a production-like academic project

- Replace synthetic training with a **properly licensed labeled credit-card dataset** with matching seven features (or change UI/model features together).
- Add authentication, roles, migrations (Alembic), audit trails, pagination at UI level, better validation and test coverage.
- Evaluate on real, time-separated data; tune thresholds for false-positive costs; explain the model with validated methods.
- Use real customer history only if consent, security, and privacy requirements are satisfied.

## Important security notes

- Demo uses no login and is **not safe to expose publicly**.
- CORS is restricted to local Vite origins.
- Do not load arbitrary/untrusted `.joblib` files.
- PostgreSQL credentials in Docker Compose are development-only.

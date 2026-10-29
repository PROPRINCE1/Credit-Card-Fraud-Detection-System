# Supabase integration — Credit Card Fraud Detection System

This package modifies the uploaded project in place. React + Vite, FastAPI, SQLAlchemy, the four original tables and the seven Random Forest inputs are retained. No Supabase SDK, API key, plugin or GitHub connection is needed. React talks to FastAPI; FastAPI talks directly to PostgreSQL.

## 1. Create the database and configure the local environment

Create an empty Supabase project. Keep the database password locally. Open **Connect → Session pooler** and copy that project's exact PostgreSQL connection URI (port **5432**). This works with IPv4 connections commonly used by local computers. A direct connection also works when your network supports the address provided by Supabase.

From the extracted project root, in Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
Copy-Item backend/.env.example backend/.env
notepad backend/.env
```
    
If PowerShell blocks activation, use `.\.venv\Scripts\python.exe` in place of `python` in every command. Python 3.11 or newer is supported; this package was tested with Python 3.12.

For macOS/Linux, use `python3 -m venv .venv`, `source .venv/bin/activate` and `cp backend/.env.example backend/.env`, then the same Python commands below.

Replace the placeholder `DATABASE_URL` in `backend/.env` with your actual connection URI. The driver prefix can be `postgresql+psycopg://` or the copied `postgresql://`; both use the installed Psycopg 3 driver. Append `?sslmode=require` if the URI has no query, or `&sslmode=require` if a query already exists.

```dotenv
DATABASE_URL="postgresql+psycopg://postgres.PROJECT_REF:ENCODED_PASSWORD@YOUR_SESSION_POOLER_HOST:5432/postgres?sslmode=require"
```

Use the **database password**, not an anon/publishable/service-role API key. Percent-encode special password characters in the URI, e.g. `@` becomes `%40`, `#` becomes `%23`, `/` becomes `%2F`, `%` becomes `%25`. Do not double-encode a password that is already encoded. Keep the entire value quoted. Do not paste it into chat or put it in frontend files.

The exact hostname and username must come from your project's Connect dialog. Environment variables already set in your terminal override `backend/.env`. `.env` loading works regardless of the terminal's current folder. `.gitignore` excludes secret environment files. No actual credentials are included in this ZIP.

TLS is required by default. `sslmode=require` encrypts the connection; for certificate/hostname verification, use Supabase's certificate and `sslmode=verify-full&sslrootcert=PATH_TO_CERTIFICATE`. The application pool is deliberately small (3 pooled connections, 2 overflow).

## 2. Initialize tables

Run from the project root:

```powershell
python database/init_database.py
python database/verify_database.py
```

The output must say **postgresql** for a Supabase connection. If it says **sqlite**, `DATABASE_URL` was not configured in this process. The empty database verification should show zero rows and `checks_passed: true`.

Alternatively, paste the complete `database/schema.sql` into the Supabase SQL Editor and run it once. Both initialization methods create the same four tables and indexes. Re-running initialization preserves rows. Existing incompatible columns are not migrated automatically; the verification script detects column-name differences. This workflow targets the new empty project, not a migration of old SQLite data.

All timestamps preserve the existing models' `TIMESTAMP WITHOUT TIME ZONE` representation and are interpreted as UTC. Primary keys remain integers; every existing foreign key and one-prediction/one-alert-per-transaction uniqueness constraint is retained. No columns were invented.

Row Level Security is enabled and access for `anon` and `authenticated` roles is revoked. There are no public Data API policies. The local backend uses the owner database login from Connect, which can access its own tables. If you later use a restricted custom database role, configure that role's grants and policies explicitly. Never place this database login in React. FastAPI remains an unauthenticated local academic demo; start it on `127.0.0.1`.

## 3. Generate data, train and seed

```powershell
python database/generate_synthetic.py
python ml/train.py
python database/seed_supabase.py
python database/verify_database.py --expected-customers 200 --expected-transactions 20000
```

Training is intentionally placed **before seeding** so stored predictions use the newly trained model. A model already trained on 50,000 samples is also included. You can omit training if using the included artifact and its pinned scikit-learn version.

Default dataset:

| Item | Value |
| --- | --- |
| Fictional customers | 200 |
| Transactions | 20,000 |
| Transaction dates | 2026-07-31 through 2026-10-28 UTC |
| Data-generation seed | 2026 |
| Training samples | 50,000 |
| Training/validation/test split | 35,000 / 7,500 / 7,500 |
| Training seed | 42 |
| Insert batch size | 1,000 |

`database/generated/` contains `customers.csv`, `transactions.csv` and `manifest.json`. The generated exports are included in this delivery and can be reproduced. Their directory is ignored by Git to avoid accidental large dataset commits. Customer emails use `example.com`. Customer creation precedes their transactions, IDs reference existing customers, timestamps are sorted, transaction hour matches UTC time, and online purchases do not claim chip/PIN usage. Amount is derived from a fictional customer purchase baseline and the purchase ratio. Distances are approximate synthetic behavior features, not reconstructed real travel paths. Currency values follow the existing USD demo UI.

For a different demonstration date, regenerate an exclusive end date explicitly:

```powershell
python database/generate_synthetic.py --end-date 2026-10-30 --seed 2026
```

Keeping the same arguments produces the same CSV data. The dashboard displays the most recent 30 UTC calendar days, including zero-activity days. An old fixed dataset will eventually fall outside that chart window. Regenerate for your presentation date **before seeding a new empty database** when needed.

The `synthetic_fraud_label` column exists only in the transaction CSV. It is a generated teaching label, never a model input or a new database column. Model predictions are separate decisions. The seed script computes them in batches through the same function used by FastAPI; an alert is created for each flagged prediction.

Seeding is one atomic transaction. A failure rolls back inserted rows. All four application tables must be empty; a second import exits without changing data. There is no automatic delete/reset option. PostgreSQL tables are locked during the seed to prevent concurrent writes, and customer/transaction sequences are advanced so later API inserts cannot reuse seeded IDs.

To change batch size:

```powershell
python database/seed_supabase.py --batch-size 500
```

Do not run the old `database/seed.py` before this workflow; it is the original small demo seeder and makes the tables non-empty.

## 4. Start the backend and frontend

Backend terminal, from the project root with the virtual environment active:

```powershell
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Second terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:5173/`. API docs: `http://127.0.0.1:8000/docs`. Health check: `http://127.0.0.1:8000/api/health`; its JSON should identify `postgresql`.

Check the dashboard total of 20,000; open Transaction History and press Next; search a customer's name; switch to flagged-only; open Fraud Alerts and filter status; submit a new transaction. The total should become 20,001 after a successful submission. The expected-count verifier is intended for the initial seed and will report a mismatch after you deliberately add rows.

`frontend/.env.example` still uses the local FastAPI URL. Do not add database credentials to it.

## 5. Retrain after data already exists

Stop FastAPI first (the process caches its model). Run:

```powershell
python ml/train.py --samples 50000 --seed 42
python database/seed_supabase.py --refresh-predictions
python database/verify_database.py
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Refresh updates predictions for **all saved transactions** and adds missing alerts for newly flagged rows. It preserves existing alerts, statuses and review notes, including alerts from an older model that are no longer flagged. Therefore, after a model refresh, total alerts can differ from the current flagged prediction count. This preserves review history and is intentional. Refreshing does not overwrite customers or transactions. Training by itself does not rewrite stored predictions.

## 6. API and query changes

| Endpoint | Behavior |
| --- | --- |
| `GET /api/transactions?skip=0&limit=50` | Existing `{total, items}` response; deterministic descending ID order; limit 1–200 |
| `GET /api/transactions?fraud=true&search=Demo` | Server filters over the entire dataset; merchant/customer text or exact transaction ID |
| `GET /api/alerts?skip=0&limit=50` | Keeps original array shape, now bounded; optional `status` |
| `GET /api/alerts/paged?skip=0&limit=50&status=open` | `{total, items}` for the updated React alert page |
| `GET /api/dashboard/charts?days=30` | SQL aggregates within the date range; supports 1–90 days |
| `GET /api/customers/{id}` | SQL count and sum; does not load every transaction |
| `GET /api/health` | Checks the database connection; returns 503 when unavailable |

React loads seven recent rows on the dashboard and 50 per history/alert page. Search/filter changes reset paging, search is debounced, and stale requests are ignored. Alerts eager-load their associated transaction, customer, prediction and alert state to avoid per-row queries. Existing create/detail/update/model endpoints remain available.

Indexes cover transaction timestamps, customer IDs plus timestamps, prediction flags plus transaction IDs, and alert statuses plus IDs. Primary keys and unique relationships are also indexed by the database. Substring text searches use SQL filters; no claim is made that ordinary B-tree indexes accelerate `%text%` searches. At 20,000 rows this avoids extra extension requirements.

## 7. Model details and measured results

Seven inputs, in the original order:

1. `distance_from_home`
2. `distance_from_last_transaction`
3. `ratio_to_median_purchase_price`
4. `repeat_retailer`
5. `used_chip`
6. `used_pin_number`
7. `online_order`

The Random Forest retains 110 trees, maximum depth 12, minimum leaf size 5 and balanced subsample weights. Its threshold is chosen on the validation split by F1. The held-out test split is used only for final evaluation. Training and history generation use different seeds. `ml/artifacts/metadata.json` includes versions, sample counts, feature order, threshold, metrics, confusion matrix and model SHA-256. The backend rejects a model with a mismatched feature order.

This delivered run: accuracy **83.53%**, precision **0.379**, recall **0.448**, F1 **0.411**, PR-AUC **0.396**, ROC-AUC **0.7797**, threshold **0.575**. These are measured results on deliberately noisy synthetic labels, not evidence of real banking performance. No 95% accuracy claim is made. The 20,000-row seed produced **2,971 model alerts**, while the CSV has **2,596 synthetic fraud labels**; these numbers measure different things.

Scikit-learn is pinned to **1.8.0** to match the supplied joblib artifact. If changing that version, retrain and refresh predictions with the same installed environment; do not load model files from untrusted sources.

## 8. Verification included in this delivery

- Full 20,000-row import into an isolated local SQLite database: 200 customers, 20,000 predictions, 2,971 alerts; relationship and count verification passed.
- Eight Python integration tests passed: deterministic data, seed repeat refusal, pagination/search/filtering, bounded alert queries, aggregation, live transaction scoring, review preservation and transaction rollback.
- PostgreSQL SQL executed twice in PGlite (embedded PostgreSQL): schema, RLS, foreign-key enforcement, sequence advancement and denied anonymous access passed. This does not test Supabase network/TLS or the live Psycopg connection.
- React production build passed. See `VALIDATION.md` for browser checks.
- **No actual Supabase project connection was attempted:** no project or credentials were supplied. The local `verify_database.py` command is the remaining cloud connection check.

Run the automated Python checks without touching your configured cloud database:

```powershell
python -m pip install -r tests/requirements.txt
python -m pytest tests -q
cd frontend
npm run build
```

The test module sets its own temporary SQLite URL before importing the application. The PostgreSQL schema check script is included under `tests/schema_postgres.cjs`; run it with `@electric-sql/pglite` installed separately when desired.

## Troubleshooting

- **Authentication failed:** confirm database password, pooler username and password URI encoding.
- **Host/network failure:** copy the Session pooler hostname directly from Connect; verify the project is available and network access is allowed.
- **Output says SQLite:** check `backend/.env` and whether a pre-existing terminal `DATABASE_URL` overrides it.
- **Tables are not empty:** an earlier seed or manual entry exists. The seeder intentionally stops. Use the already seeded database or another empty project; it does not delete data for you.
- **Missing table/index:** run `python database/init_database.py` and then verify.
- **Model not trained/version mismatch:** install the supplied requirements, run `python ml/train.py`, refresh predictions if needed, and restart FastAPI.
- **No chart activity:** the fixed sample dates may be outside today's last-30-day window. See the generation-date option.
- **Frontend cannot connect:** ensure the backend is running at port 8000 and frontend at port 5173, which matches the preserved CORS origins.

Official connection references checked during implementation:

- https://supabase.com/docs/guides/database/connecting-to-postgres
- https://supabase.com/kb/troubleshooting/using-sqlalchemy-with-supabase-FUqebT
- https://docs.sqlalchemy.org/en/20/dialects/postgresql.html

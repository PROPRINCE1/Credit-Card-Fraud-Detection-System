# Delivery validation — 29 October 2026

Validated against the uploaded repository source, without cloud credentials.

| Check | Result |
| --- | --- |
| Full synthetic generation | 200 customers; 20,000 transactions; 90 UTC days |
| Full local database import | 20,000 predictions; 2,971 model-generated alerts |
| Foreign keys and record counts | Passed with SQLite foreign keys enabled |
| Python integration suite | 8 passed |
| Repeated seed | Refused; existing rows preserved |
| PostgreSQL schema in PGlite | Passed twice; RLS, foreign keys, sequence advancement and anon restriction checked |
| React production build | Passed |
| Live browser with local FastAPI and 20,000-row database | Dashboard, history paging, global customer search and alert paging passed; no JavaScript page errors |
| Model training | 50,000 samples; seven original features |
| Model artifact SHA-256 | Matches metadata.json |
| Actual Supabase/Psycopg cloud connection | Not run; requires the user's new project and local DATABASE_URL |

The Python tests use an isolated temporary SQLite database. PostgreSQL DDL checks use PGlite, an embedded PostgreSQL engine; they do not validate remote transport, credentials or SSL. Browser checks used headless Chromium against the actual Vite app and FastAPI backend.

Non-blocking output: Vite reports an existing bundle over 500 kB; test dependencies emitted deprecation warnings. The architecture and existing frontend dependency versions were preserved.

The packaged CSV label count (2,596) differs from model flags (2,971) by design. Ground-truth synthetic labels and model decisions are separate values. Evaluation metrics are recorded in ml/artifacts/metadata.json and README_SUPABASE.md.

No local test database, secret .env, node_modules, browser binary or screenshot is included in the delivery.

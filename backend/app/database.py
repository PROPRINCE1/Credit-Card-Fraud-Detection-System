"""One connection configuration for FastAPI and all database scripts."""
import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import declarative_base, sessionmaker

ROOT = Path(__file__).resolve().parents[2]
# Existing environment variables take priority; independent of terminal directory.
load_dotenv(ROOT / "backend" / ".env", override=False, interpolate=False)
DEFAULT_DB = "sqlite:///" + (ROOT / "creditguard.db").as_posix()
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DB)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]
url = make_url(DATABASE_URL)
if url.drivername in ("postgresql", "postgresql+psycopg2"):
    url = url.set(drivername="postgresql+psycopg")
options = {"pool_pre_ping": True, "hide_parameters": True}
if url.get_backend_name() == "sqlite":
    options["connect_args"] = {"check_same_thread": False}
elif url.get_backend_name() == "postgresql":
    # Session pooler (5432) or direct connection; TLS required by default.
    options["connect_args"] = {"sslmode": url.query.get("sslmode", "require"),
                               "connect_timeout": 15, "prepare_threshold": None}
    options.update(pool_size=3, max_overflow=2, pool_timeout=30, pool_recycle=1800)
else:
    raise ValueError("Only SQLite and PostgreSQL are supported")
engine = create_engine(url, **options)
if engine.dialect.name == "sqlite":
    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

def get_db():
    with SessionLocal() as db:
        yield db

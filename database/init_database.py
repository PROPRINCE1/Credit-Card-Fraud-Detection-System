"""Initialize missing tables/indexes; never drop tables or delete rows."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from backend.app.database import Base,engine
from backend.app import models

def initialize():
    with engine.begin() as connection:
        if engine.dialect.name == 'postgresql':
            connection.execute(text('SET LOCAL search_path TO public'))
        Base.metadata.create_all(connection)
        # create_all does not add indexes to tables which already exist.
        for table in Base.metadata.sorted_tables:
            for index in table.indexes:
                index.create(connection,checkfirst=True)
        if engine.dialect.name == 'postgresql':
            for table in Base.metadata.sorted_tables:
                connection.execute(text(f'ALTER TABLE public.{table.name} ENABLE ROW LEVEL SECURITY'))
            # No browser Data API access: only local backend uses DB credentials.
            for role in ('anon','authenticated'):
                exists=connection.execute(text('SELECT 1 FROM pg_roles WHERE rolname=:role'),{'role':role}).scalar()
                if exists:
                    for table in Base.metadata.sorted_tables:
                        connection.execute(text(f'REVOKE ALL ON TABLE public.{table.name} FROM {role}'))
    print('Tables and indexes ready ('+engine.dialect.name+'). Existing rows preserved.')
if __name__=='__main__':
    try: initialize()
    except SQLAlchemyError:
        raise SystemExit('Initialization failed. Check backend/.env, database password, network and table permissions. Credentials omitted.') from None

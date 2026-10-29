"""Read-only connection, schema, relationship and optional demo-size checks."""
import argparse
import json
import sys
from pathlib import Path
from sqlalchemy import inspect,text,select,func
from sqlalchemy.exc import SQLAlchemyError
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.app.database import engine,Base
from backend.app.models import Customer,Transaction,Prediction,FraudAlert

def verify(expected_customers=None,expected_transactions=None):
    errors=[]
    with engine.connect() as connection:
        connection.execute(text('SELECT 1'))
        inspector=inspect(connection)
        for table in Base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                errors.append('Missing table: '+table.name);continue
            columns={c['name'] for c in inspector.get_columns(table.name)}
            if columns!=set(table.columns.keys()):errors.append('Column mismatch: '+table.name)
            indexes={i['name'] for i in inspector.get_indexes(table.name)}
            if not {i.name for i in table.indexes}.issubset(indexes): errors.append('Missing indexes: '+table.name)
            foreign_keys=inspector.get_foreign_keys(table.name)
            for fk in table.foreign_keys:
                if not any(fk.parent.name in item['constrained_columns'] and item['referred_table']==fk.column.table.name for item in foreign_keys):
                    errors.append('Missing foreign key: '+str(fk.parent))
        if errors: raise ValueError('; '.join(errors))
        counts={t.name:connection.scalar(select(func.count()).select_from(t)) for t in Base.metadata.sorted_tables}
        checks={
            'orphan_transactions':'SELECT count(*) FROM transactions t LEFT JOIN customers c ON c.id=t.customer_id WHERE c.id IS NULL',
            'orphan_predictions':'SELECT count(*) FROM predictions p LEFT JOIN transactions t ON t.id=p.transaction_id WHERE t.id IS NULL',
            'orphan_alerts':'SELECT count(*) FROM fraud_alerts a LEFT JOIN transactions t ON t.id=a.transaction_id WHERE t.id IS NULL',
            'missing_predictions':'SELECT count(*) FROM transactions t LEFT JOIN predictions p ON p.transaction_id=t.id WHERE p.id IS NULL',
            'missing_flagged_alerts':'SELECT count(*) FROM predictions p LEFT JOIN fraud_alerts a ON a.transaction_id=p.transaction_id WHERE p.predicted_fraud=true AND a.id IS NULL',
            'invalid_timestamps':'SELECT count(*) FROM transactions t JOIN customers c ON c.id=t.customer_id WHERE t.created_at<c.created_at OR t.created_at IS NULL',
            'invalid_probability':'SELECT count(*) FROM predictions WHERE fraud_probability<0 OR fraud_probability>1',
        }
        for name,query in checks.items():
            if connection.scalar(text(query)):errors.append(name)
        for name,expected in [('customers',expected_customers),('transactions',expected_transactions)]:
            if expected is not None and counts[name]!=expected:errors.append(f'{name}: expected {expected}, found {counts[name]}')
        if engine.dialect.name=='postgresql':
            for name in counts:
                enabled=connection.scalar(text("SELECT relrowsecurity FROM pg_class WHERE oid=to_regclass(:name)"),{'name':'public.'+name})
                if not enabled:errors.append('RLS not enabled: '+name)
        period=connection.execute(select(func.min(Transaction.created_at),func.max(Transaction.created_at))).one()
    report={'database':engine.dialect.name,'counts':counts,'first_transaction':str(period[0]),
            'last_transaction':str(period[1]),'checks_passed':not errors,'errors':errors}
    print(json.dumps(report,indent=2))
    if errors:raise ValueError('Verification failed: '+'; '.join(errors))
    return report

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-customers',type=int)
    parser.add_argument('--expected-transactions',type=int)
    args=parser.parse_args()
    try:verify(args.expected_customers,args.expected_transactions)
    except SQLAlchemyError:
        raise SystemExit('Database verification failed. Check backend/.env, network, credentials and initialization. Credentials omitted.') from None
    except ValueError as error:raise SystemExit(str(error)) from None
if __name__=='__main__':main()

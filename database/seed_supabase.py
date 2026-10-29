"""Atomic, batched seed into empty application tables. Re-runs refuse duplicates."""
import argparse
import sys
from datetime import datetime
from pathlib import Path
import pandas as pd
from sqlalchemy import select,func,insert,update,text
from sqlalchemy.exc import SQLAlchemyError
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.app.database import engine,SessionLocal
from backend.app.models import Customer,Transaction,Prediction,FraudAlert
from backend.app.schemas import TransactionCreate
from backend.app.services.prediction import predict_many,load_model
from database.generate_synthetic import DEFAULT_OUTPUT

def chunks(rows,size):
    for start in range(0,len(rows),size): yield rows[start:start+size]

def read_data(folder):
    customers=pd.read_csv(folder/'customers.csv').to_dict('records')
    transactions=pd.read_csv(folder/'transactions.csv').to_dict('records')
    for row in customers+transactions:
        row['created_at']=datetime.fromisoformat(row['created_at'])
    customer_dates={r['id']:r['created_at'] for r in customers}
    if len(customer_dates)!=len(customers) or len({r['id'] for r in transactions})!=len(transactions):
        raise ValueError('Duplicate IDs in input files')
    for row in transactions:
        row.pop('synthetic_fraud_label',None)
        valid=TransactionCreate(**row).model_dump()
        row.update(valid)
        if row['customer_id'] not in customer_dates or row['created_at']<customer_dates[row['customer_id']]:
            raise ValueError('Invalid customer relationship or timestamp')
        if row['hour'] != row['created_at'].hour: raise ValueError('Hour does not match UTC timestamp')
    return customers,transactions

def seed(folder=DEFAULT_OUTPUT,batch_size=1000):
    customers,transactions=read_data(folder)
    load_model()
    alert_count=0
    with SessionLocal.begin() as db:
        if engine.dialect.name=='postgresql':
            db.execute(text('LOCK TABLE customers, transactions, predictions, fraud_alerts IN EXCLUSIVE MODE'))
        for table in (Customer,Transaction,Prediction,FraudAlert):
            if db.scalar(select(func.count()).select_from(table)):
                raise ValueError('Application tables are not empty. Seed cancelled without changes; use a new empty database.')
        for batch in chunks(customers,batch_size): db.execute(insert(Customer),batch)
        for batch in chunks(transactions,batch_size):
            db.execute(insert(Transaction),batch)
            results=predict_many(batch)
            predictions=[];alerts=[]
            for row,result in zip(batch,results):
                predictions.append({'transaction_id':row['id'],**result})
                if result['predicted_fraud']:
                    alerts.append({'transaction_id':row['id'],'status':'open','notes':'Synthetic demo alert',
                                   'created_at':row['created_at']})
            db.execute(insert(Prediction),predictions)
            if alerts: db.execute(insert(FraudAlert),alerts)
            alert_count+=len(alerts)
        if engine.dialect.name=='postgresql':
            # Explicit CSV IDs must not collide with later API-created records.
            for name in ('customers','transactions'):
                db.execute(text(f"SELECT setval(pg_get_serial_sequence('{name}','id'), (SELECT max(id) FROM {name}), true)"))
    print(f'Committed: {len(customers)} customers, {len(transactions)} transactions, {len(transactions)} predictions, {alert_count} alerts.')

def refresh_predictions(batch_size=1000):
    """Explicit refresh after retraining; preserve existing alerts and review notes."""
    load_model()
    with SessionLocal.begin() as db:
        if engine.dialect.name=='postgresql':
            db.execute(text('LOCK TABLE customers, transactions, predictions, fraud_alerts IN EXCLUSIVE MODE'))
        last_id=0;total=0
        while True:
            rows=db.execute(select(Transaction.__table__).where(Transaction.id>last_id).order_by(Transaction.id).limit(batch_size)).mappings().all()
            if not rows: break
            records=[dict(r) for r in rows]; ids=[r['id'] for r in records]
            existing=set(db.scalars(select(Prediction.transaction_id).where(Prediction.transaction_id.in_(ids))))
            alerted=set(db.scalars(select(FraudAlert.transaction_id).where(FraudAlert.transaction_id.in_(ids))))
            for row,result in zip(records,predict_many(records)):
                if row['id'] in existing:
                    db.execute(update(Prediction).where(Prediction.transaction_id==row['id']).values(**result))
                else: db.execute(insert(Prediction).values(transaction_id=row['id'],**result))
                if result['predicted_fraud'] and row['id'] not in alerted:
                    db.execute(insert(FraudAlert).values(transaction_id=row['id'],created_at=row['created_at'],status='open',notes='Synthetic demo alert'))
            last_id=records[-1]['id'];total+=len(records)
    print(f'Rescored {total} transactions. Existing alerts and review history preserved, including older model flags.')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-dir',type=Path,default=DEFAULT_OUTPUT)
    p.add_argument('--batch-size',type=int,default=1000)
    p.add_argument('--refresh-predictions',action='store_true')
    a=p.parse_args()
    if not 1<=a.batch_size<=5000: p.error('batch-size must be between 1 and 5000')
    try:
        if a.refresh_predictions: refresh_predictions(a.batch_size)
        else: seed(a.data_dir,a.batch_size)
    except SQLAlchemyError:
        raise SystemExit('Database operation failed; transaction rolled back. Check configuration and run database/init_database.py. Credentials omitted.') from None
    except (ValueError,FileNotFoundError) as e: raise SystemExit(str(e)) from None
if __name__=='__main__':main()

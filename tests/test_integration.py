"""Runs against an isolated temporary SQLite DB; never reads user DB credentials."""
import os
import sys
import tempfile
from pathlib import Path
from datetime import datetime,timedelta,timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
_temp=tempfile.TemporaryDirectory()
os.environ['DATABASE_URL']='sqlite:///'+str(Path(_temp.name)/'integration.db')
from fastapi.testclient import TestClient
from sqlalchemy import select,func,event,text
from backend.app.database import engine,SessionLocal
from backend.app.main import app
from backend.app.models import Customer,Transaction,Prediction,FraudAlert
from backend.app.services.prediction import predict_many,load_model
from database.init_database import initialize
from database.generate_synthetic import generate
from database.seed_supabase import seed,refresh_predictions
from database.verify_database import verify
import pytest

@pytest.fixture(scope='module')
def client():
    initialize()
    people,rows=generate(12,600,123,'2026-10-29')
    folder=Path(_temp.name)
    people.to_csv(folder/'customers.csv',index=False);rows.to_csv(folder/'transactions.csv',index=False)
    seed(folder,100)
    with TestClient(app) as client:yield client
    engine.dispose()

def test_generator_reproducible():
    a,b=generate(12,600,123,'2026-10-29');c,d=generate(12,600,123,'2026-10-29')
    assert a.equals(c) and b.equals(d)
    assert b.customer_id.nunique()==12
    assert set(b.synthetic_fraud_label)=={0,1}
    assert not (b.online_order & b.used_chip).any()
    assert b.created_at.min()>='2026-07-31' and b.created_at.max()<'2026-10-29'

def test_seed_counts_and_repeat_refusal(client):
    assert verify(12,600)['checks_passed']
    with pytest.raises(ValueError,match='not empty'):seed(Path(_temp.name),100)
    assert verify(12,600)['checks_passed']

def test_paging_search_and_filters(client):
    a=client.get('/api/transactions?limit=13').json()
    b=client.get('/api/transactions?limit=13&skip=13').json()
    assert a['total']==600 and len(a['items'])==13
    assert not ({r['id'] for r in a['items']} & {r['id'] for r in b['items']})
    assert client.get('/api/transactions?skip=99999').json()['items']==[]
    assert client.get('/api/transactions?limit=201').status_code==422
    assert client.get('/api/transactions?skip=-1').status_code==422
    name=a['items'][0]['customer_name']
    filtered=client.get('/api/transactions',params={'search':name}).json()
    assert filtered['total']>0 and all(r['customer_name']==name for r in filtered['items'])
    for flag in ['true','false']:
        data=client.get('/api/transactions',params={'fraud':flag}).json()
        assert all(t['predicted_fraud']==(flag=='true') for t in data['items'])

def test_alert_paging_and_query_count(client):
    count=[]
    def capture(*args):count.append(1)
    event.listen(engine,'before_cursor_execute',capture)
    try: response=client.get('/api/alerts/paged?limit=30')
    finally:event.remove(engine,'before_cursor_execute',capture)
    assert response.status_code==200 and len(count)==2
    data=response.json(); assert data['total']>0
    assert len(client.get('/api/alerts?limit=2').json())==2
    alert=data['items'][0]
    assert client.patch(f"/api/alerts/{alert['id']}",json={'status':'resolved','notes':'Reviewed in test'}).status_code==200
    assert client.get('/api/alerts/paged?status=resolved').json()['total']==1
    assert client.get('/api/alerts/paged?status=invalid').status_code==422

def test_charts_and_summary_use_database(client):
    with SessionLocal.begin() as db:
        stamp=datetime.now(timezone.utc).replace(tzinfo=None)
        db.execute(text('UPDATE transactions SET created_at=:stamp WHERE id<=4'),{'stamp':stamp})
    charts=client.get('/api/dashboard/charts').json()['daily']
    assert len(charts)==30
    with SessionLocal() as db:
        start=datetime.fromisoformat(charts[0]['date']);end=datetime.fromisoformat(charts[-1]['date'])+timedelta(days=1)
        expected=db.scalar(select(func.count(Transaction.id)).where(Transaction.created_at>=start,Transaction.created_at<end))
    assert sum(r['total'] for r in charts)==expected
    assert charts[-1]['total']>=4
    summary=client.get('/api/dashboard/summary').json()
    assert summary['total_transactions']==600
    assert summary['flagged_transactions']==client.get('/api/transactions?fraud=true').json()['total']
    assert client.get('/api/customers/1').json()['transaction_count']>0

def test_create_transaction_and_model_contract(client):
    model,meta=load_model();assert meta['samples']==50000 and model.n_features_in_==7
    new=client.post('/api/customers',json={'name':'Extra Demo','email':'extra@example.com'})
    assert new.status_code==201 and new.json()['id']>12
    payload={'customer_id':new.json()['id'],'amount':1000,'merchant':'Test Store','category':'Other','location':'Online','hour':12,
        'distance_from_home':500,'distance_from_last_transaction':400,'ratio_to_median_purchase_price':15,
        'repeat_retailer':False,'used_chip':False,'used_pin_number':False,'online_order':True}
    created=client.post('/api/transactions',json=payload)
    assert created.status_code==201,created.text
    result=created.json(); assert result['id']>600
    expected=predict_many([payload])[0]
    assert result['fraud_probability']==expected['fraud_probability'] and result['predicted_fraud']
    assert result['alert_status']=='open'
    assert client.get(f"/api/transactions/{result['id']}").json()==result
    assert client.post('/api/transactions',json={**payload,'customer_id':99999}).status_code==404
    assert client.get('/api/health').json()['database']=='sqlite'

def test_refresh_preserves_review_history(client):
    with SessionLocal() as db:
        alert=db.scalar(select(FraudAlert).where(FraudAlert.status=='resolved'))
        ident=alert.id
    refresh_predictions(100)
    with SessionLocal() as db:
        alert=db.get(FraudAlert,ident)
        assert alert.status=='resolved' and alert.notes=='Reviewed in test'
    assert verify(13,601)['checks_passed']

def test_failed_batch_rolls_back():
    # Separate empty database to exercise a late foreign-key failure atomically.
    from sqlalchemy import create_engine,insert
    from sqlalchemy.exc import IntegrityError
    from backend.app.database import Base
    test_engine=create_engine('sqlite://')
    @event.listens_for(test_engine,'connect')
    def fk(conn,_):conn.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(test_engine)
    with pytest.raises(IntegrityError):
        with test_engine.begin() as conn:
            conn.execute(insert(Customer),[{'id':1,'name':'Demo','email':'demo@example.com'}])
            conn.execute(insert(Prediction),[{'transaction_id':999,'fraud_probability':.5,'predicted_fraud':True,'risk_level':'high','model_version':'test'}])
    with test_engine.connect() as conn:assert conn.scalar(select(func.count()).select_from(Customer))==0
    test_engine.dispose()

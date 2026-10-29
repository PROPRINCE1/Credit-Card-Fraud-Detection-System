from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, case, or_, cast, String, text
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timedelta, timezone
from typing import Literal
from .database import Base,engine,get_db
from .models import Customer,Transaction,Prediction,FraudAlert
from .schemas import CustomerCreate,TransactionCreate,AlertUpdate
from .services.prediction import predict,load_model

@asynccontextmanager
async def lifespan(app:FastAPI):
    # PostgreSQL schema/security is initialized explicitly by database/init_database.py.
    if engine.dialect.name == 'sqlite': Base.metadata.create_all(bind=engine)
    yield

app=FastAPI(title='CreditGuard AI — Credit Card Fraud Detection',version='1.0.0',lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=['http://localhost:5173','http://127.0.0.1:5173'],allow_methods=['*'],allow_headers=['*'])

@app.get('/api/health')
def health(db:Session=Depends(get_db)):
    try: db.execute(text('SELECT 1'))
    except SQLAlchemyError: raise HTTPException(503,'Database unavailable') from None
    return {'status':'ok','service':'CreditGuard AI','database':engine.dialect.name}

@app.post('/api/customers',status_code=201)
def create_customer(payload:CustomerCreate,db:Session=Depends(get_db)):
    if db.query(Customer).filter(Customer.email==payload.email).first():raise HTTPException(409,'Email already exists')
    c=Customer(**payload.model_dump());db.add(c);db.commit();db.refresh(c)
    return {'id':c.id,'name':c.name,'email':c.email}

@app.get('/api/customers')
def customers(db:Session=Depends(get_db)):
    return [{'id':c.id,'name':c.name,'email':c.email} for c in db.query(Customer).order_by(Customer.id).all()]

@app.get('/api/customers/{customer_id}')
def customer_detail(customer_id:int,db:Session=Depends(get_db)):
    c=db.get(Customer,customer_id)
    if not c:raise HTTPException(404,'Customer not found')
    count,amount=db.query(func.count(Transaction.id),func.coalesce(func.sum(Transaction.amount),0)).filter(Transaction.customer_id==customer_id).one()
    return {'id':c.id,'name':c.name,'email':c.email,'transaction_count':count,'total_amount':round(float(amount),2)}

def serialize(t):
    p=t.prediction
    return {'id':t.id,'customer_id':t.customer_id,'customer_name':t.customer.name if t.customer else None,'amount':t.amount,'merchant':t.merchant,'category':t.category,'location':t.location,'created_at':t.created_at.isoformat()+'Z','fraud_probability':p.fraud_probability if p else None,'predicted_fraud':p.predicted_fraud if p else None,'risk_level':p.risk_level if p else None,'explanation':p.explanation if p else [],'model_version':p.model_version if p else None,'alert_status':t.alert.status if t.alert else None}

@app.post('/api/transactions',status_code=201)
def create_transaction(payload:TransactionCreate,db:Session=Depends(get_db)):
    if not db.get(Customer,payload.customer_id):raise HTTPException(404,'Customer not found')
    result=predict(payload)
    t=Transaction(**payload.model_dump());db.add(t);db.flush()
    p=Prediction(transaction_id=t.id,**result);db.add(p)
    if result['predicted_fraud']:db.add(FraudAlert(transaction_id=t.id,status='open'))
    db.commit()
    t=db.query(Transaction).options(joinedload(Transaction.customer),joinedload(Transaction.prediction),joinedload(Transaction.alert)).filter(Transaction.id==t.id).one()
    return serialize(t)

@app.get('/api/transactions')
def transactions(skip:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=200),fraud:bool|None=None,search:str=Query('',max_length=180),db:Session=Depends(get_db)):
    q=db.query(Transaction).join(Customer).outerjoin(Prediction).options(joinedload(Transaction.customer),joinedload(Transaction.prediction),joinedload(Transaction.alert))
    if fraud is not None:q=q.filter(Prediction.predicted_fraud==fraud)
    if search:
        pattern='%'+search+'%'
        q=q.filter(or_(Transaction.merchant.ilike(pattern),Customer.name.ilike(pattern),cast(Transaction.id,String)==search))
    total=q.count();rows=q.order_by(Transaction.id.desc()).offset(skip).limit(limit).all()
    return {'total':total,'items':[serialize(t) for t in rows]}

@app.get('/api/transactions/{transaction_id}')
def transaction_detail(transaction_id:int,db:Session=Depends(get_db)):
    t=db.query(Transaction).options(joinedload(Transaction.customer),joinedload(Transaction.prediction),joinedload(Transaction.alert)).filter(Transaction.id==transaction_id).first()
    if not t:raise HTTPException(404,'Transaction not found')
    return serialize(t)

def alert_query(db,status):
    q=db.query(FraudAlert)
    if status is not None: q=q.filter(FraudAlert.status==status)
    return q

def alert_items(q,skip,limit):
    rows=q.options(joinedload(FraudAlert.transaction).joinedload(Transaction.customer),
                   joinedload(FraudAlert.transaction).joinedload(Transaction.prediction),
                   joinedload(FraudAlert.transaction).joinedload(Transaction.alert)).order_by(FraudAlert.id.desc()).offset(skip).limit(limit).all()
    return [{'id':a.id,'status':a.status,'notes':a.notes,'transaction':serialize(a.transaction)} for a in rows]

@app.get('/api/alerts')
def alerts(skip:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=200),
           status:Literal['open','under_review','resolved']|None=None,db:Session=Depends(get_db)):
    # Keep the original array response for existing API consumers.
    return alert_items(alert_query(db,status),skip,limit)

@app.get('/api/alerts/paged')
def paged_alerts(skip:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=200),
                 status:Literal['open','under_review','resolved']|None=None,db:Session=Depends(get_db)):
    q=alert_query(db,status)
    return {'total':q.count(),'items':alert_items(q,skip,limit)}

@app.patch('/api/alerts/{alert_id}')
def update_alert(alert_id:int,payload:AlertUpdate,db:Session=Depends(get_db)):
    a=db.get(FraudAlert,alert_id)
    if not a:raise HTTPException(404,'Alert not found')
    a.status=payload.status;a.notes=payload.notes;db.commit()
    return {'id':a.id,'status':a.status,'notes':a.notes}

@app.get('/api/dashboard/summary')
def summary(db:Session=Depends(get_db)):
    total=db.query(func.count(Transaction.id)).scalar() or 0
    fraud=db.query(func.count(Prediction.id)).filter(Prediction.predicted_fraud.is_(True)).scalar() or 0
    volume=db.query(func.coalesce(func.sum(Transaction.amount),0)).scalar() or 0
    open_alerts=db.query(func.count(FraudAlert.id)).filter(FraudAlert.status!='resolved').scalar() or 0
    return {'total_transactions':total,'flagged_transactions':fraud,'fraud_rate':round(100*fraud/total,2) if total else 0,'total_volume':round(float(volume),2),'open_alerts':open_alerts}

@app.get('/api/dashboard/charts')
def charts(days:int=Query(30,ge=1,le=90),db:Session=Depends(get_db)):
    today=datetime.now(timezone.utc).replace(tzinfo=None,hour=0,minute=0,second=0,microsecond=0)
    start=today-timedelta(days=days-1)
    day=func.date(Transaction.created_at)
    rows=(db.query(day.label('day'),func.count(Transaction.id),
                   func.sum(case((Prediction.predicted_fraud.is_(True),1),else_=0)))
          .outerjoin(Prediction).filter(Transaction.created_at>=start,Transaction.created_at<today+timedelta(days=1))
          .group_by(day).order_by(day).all())
    counts={str(d):(int(total),int(flagged)) for d,total,flagged in rows}
    daily=[]
    for i in range(days):
        date=(start+timedelta(days=i)).date().isoformat()
        total,flagged=counts.get(date,(0,0))
        daily.append({'date':date,'total':total,'flagged':flagged})
    return {'daily':daily}

@app.get('/api/model/info')
def model_info():
    _,meta=load_model();return meta

@app.get('/api/model/metrics')
def model_metrics():
    _,meta=load_model();return meta.get('metrics',{})

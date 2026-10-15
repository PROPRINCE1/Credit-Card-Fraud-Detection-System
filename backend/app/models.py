from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship
from .database import Base

def utcnow(): return datetime.now(timezone.utc).replace(tzinfo=None)

class Customer(Base):
    __tablename__='customers'
    id=Column(Integer, primary_key=True)
    name=Column(String(120), nullable=False)
    email=Column(String(180), unique=True, nullable=False)
    created_at=Column(DateTime, default=utcnow)
    transactions=relationship('Transaction',back_populates='customer')

class Transaction(Base):
    __tablename__='transactions'
    id=Column(Integer,primary_key=True)
    customer_id=Column(Integer,ForeignKey('customers.id'),nullable=False,index=True)
    amount=Column(Float,nullable=False)
    merchant=Column(String(120),nullable=False)
    category=Column(String(80),nullable=False)
    location=Column(String(120),nullable=False)
    hour=Column(Integer,nullable=False)
    distance_from_home=Column(Float,nullable=False)
    distance_from_last_transaction=Column(Float,nullable=False)
    ratio_to_median_purchase_price=Column(Float,nullable=False)
    repeat_retailer=Column(Boolean,nullable=False)
    used_chip=Column(Boolean,nullable=False)
    used_pin_number=Column(Boolean,nullable=False)
    online_order=Column(Boolean,nullable=False)
    created_at=Column(DateTime,default=utcnow)
    customer=relationship('Customer',back_populates='transactions')
    prediction=relationship('Prediction',back_populates='transaction',uselist=False,cascade='all,delete-orphan')
    alert=relationship('FraudAlert',back_populates='transaction',uselist=False,cascade='all,delete-orphan')

class Prediction(Base):
    __tablename__='predictions'
    id=Column(Integer,primary_key=True)
    transaction_id=Column(Integer,ForeignKey('transactions.id'),unique=True,nullable=False)
    fraud_probability=Column(Float,nullable=False)
    predicted_fraud=Column(Boolean,nullable=False)
    risk_level=Column(String(20),nullable=False)
    model_version=Column(String(50),nullable=False)
    explanation=Column(JSON,nullable=False,default=list)
    transaction=relationship('Transaction',back_populates='prediction')

class FraudAlert(Base):
    __tablename__='fraud_alerts'
    id=Column(Integer,primary_key=True)
    transaction_id=Column(Integer,ForeignKey('transactions.id'),unique=True,nullable=False)
    status=Column(String(30),default='open',nullable=False)
    notes=Column(Text,default='')
    created_at=Column(DateTime,default=utcnow)
    transaction=relationship('Transaction',back_populates='alert')

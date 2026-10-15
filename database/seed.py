"""Seed sample customers and synthetic demo transactions using the API's ML model."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.database import Base,engine,SessionLocal
from app.models import Customer,Transaction,Prediction,FraudAlert
from app.schemas import TransactionCreate
from app.services.prediction import predict
import random

Base.metadata.create_all(bind=engine)
r=random.Random(123)
db=SessionLocal()
try:
    for name,email in [('Ayesha Khan','ayesha@example.test'),('Ali Raza','ali@example.test'),('Sara Ahmed','sara@example.test'),('Hassan Malik','hassan@example.test')]:
        if not db.query(Customer).filter_by(email=email).first():db.add(Customer(name=name,email=email))
    db.commit()
    if db.query(Transaction).count():
        print('Transactions already exist; skipping seed.');sys.exit(0)
    customers=db.query(Customer).all()
    for i in range(70):
        unusual=i%9==0
        data=TransactionCreate(customer_id=r.choice(customers).id,amount=round(r.uniform(15,3000),2),merchant=r.choice(['Metro Mart','Book Corner','Tech World','City Pharmacy','Travel Hub']),category=r.choice(['Groceries','Electronics','Travel','Healthcare']),location=r.choice(['Karachi','Lahore','Islamabad']),hour=r.randrange(24),distance_from_home=r.uniform(130,500) if unusual else r.uniform(0,55),distance_from_last_transaction=r.uniform(110,420) if unusual else r.uniform(0,40),ratio_to_median_purchase_price=r.uniform(4,12) if unusual else r.uniform(.2,2.4),repeat_retailer=not unusual,used_chip=not unusual,used_pin_number=not unusual,online_order=unusual)
        result=predict(data);t=Transaction(**data.model_dump());db.add(t);db.flush();db.add(Prediction(transaction_id=t.id,**result))
        if result['predicted_fraud']:db.add(FraudAlert(transaction_id=t.id))
    db.commit();print('Seeded customers and 70 simulated transactions')
finally:db.close()

from pydantic import BaseModel, Field, ConfigDict
from typing import Literal

class CustomerCreate(BaseModel):
    name: str = Field(min_length=2,max_length=120)
    email: str = Field(min_length=5,max_length=180)

class TransactionCreate(BaseModel):
    customer_id: int
    amount: float = Field(gt=0,le=10000000)
    merchant: str = Field(min_length=1,max_length=120)
    category: str = Field(min_length=1,max_length=80)
    location: str = Field(min_length=1,max_length=120)
    hour: int = Field(ge=0,le=23)
    distance_from_home: float = Field(ge=0)
    distance_from_last_transaction: float = Field(ge=0)
    ratio_to_median_purchase_price: float = Field(ge=0)
    repeat_retailer: bool
    used_chip: bool
    used_pin_number: bool
    online_order: bool

class AlertUpdate(BaseModel):
    status: Literal['open','under_review','resolved']
    notes: str = Field(default='',max_length=1000)

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey, Numeric, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
from typing import Optional, List
import enum
import os
from dotenv import load_dotenv

load_dotenv()

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "mysql://telegraminvi:szkTgBhWh6XU@db:3306/telegraminvi")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Enums
class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    PENDING = "pending"

class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"

# Database Models
class Plan(Base):
    __tablename__ = "plans"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True)
    description = Column(String(1000))
    price = Column(Numeric(10, 2))
    currency = Column(String(3), default="USD")
    interval = Column(String(20))  # monthly, yearly
    features = Column(String(2000))  # JSON string of features
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    plan_id = Column(Integer, ForeignKey("plans.id"))
    status = Column(Enum(SubscriptionStatus), default=SubscriptionStatus.PENDING)
    start_date = Column(DateTime, default=datetime.utcnow)
    end_date = Column(DateTime)
    trial_end = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    plan = relationship("Plan")

class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"))
    amount = Column(Numeric(10, 2))
    currency = Column(String(3), default="USD")
    status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING)
    payment_method = Column(String(50))
    payment_id = Column(String(255))  # External payment system ID
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    subscription = relationship("Subscription")

# Pydantic models
class PlanBase(BaseModel):
    name: str
    description: str
    price: float
    currency: str = "USD"
    interval: str
    features: str

class PlanCreate(PlanBase):
    pass

class Plan(PlanBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class SubscriptionBase(BaseModel):
    user_id: int
    plan_id: int
    status: SubscriptionStatus
    start_date: datetime
    end_date: datetime
    trial_end: Optional[datetime] = None

class SubscriptionCreate(SubscriptionBase):
    pass

class Subscription(SubscriptionBase):
    id: int
    created_at: datetime
    updated_at: datetime
    plan: Plan

    class Config:
        from_attributes = True

class PaymentBase(BaseModel):
    subscription_id: int
    amount: float
    currency: str = "USD"
    status: PaymentStatus
    payment_method: str
    payment_id: str

class PaymentCreate(PaymentBase):
    pass

class Payment(PaymentBase):
    id: int
    created_at: datetime
    updated_at: datetime
    subscription: Subscription

    class Config:
        from_attributes = True

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Billing Service",
    description="Subscription and payment management service for Content Factory",
    version="1.0.0"
)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Endpoints
@app.post("/plans/", response_model=Plan)
def create_plan(plan: PlanCreate, db: Session = Depends(get_db)):
    db_plan = Plan(**plan.dict())
    db.add(db_plan)
    db.commit()
    db.refresh(db_plan)
    return db_plan

@app.get("/plans/", response_model=List[Plan])
def get_plans(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    plans = db.query(Plan).filter(Plan.is_active == True).offset(skip).limit(limit).all()
    return plans

@app.post("/subscriptions/", response_model=Subscription)
def create_subscription(subscription: SubscriptionCreate, db: Session = Depends(get_db)):
    db_subscription = Subscription(**subscription.dict())
    db.add(db_subscription)
    db.commit()
    db.refresh(db_subscription)
    return db_subscription

@app.get("/subscriptions/{user_id}", response_model=List[Subscription])
def get_user_subscriptions(user_id: int, db: Session = Depends(get_db)):
    subscriptions = db.query(Subscription).filter(Subscription.user_id == user_id).all()
    return subscriptions

@app.post("/payments/", response_model=Payment)
def create_payment(payment: PaymentCreate, db: Session = Depends(get_db)):
    db_payment = Payment(**payment.dict())
    db.add(db_payment)
    db.commit()
    db.refresh(db_payment)
    return db_payment

@app.get("/payments/{subscription_id}", response_model=List[Payment])
def get_subscription_payments(subscription_id: int, db: Session = Depends(get_db)):
    payments = db.query(Payment).filter(Payment.subscription_id == subscription_id).all()
    return payments

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "billing-service"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 
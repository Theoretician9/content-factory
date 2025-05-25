from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey, Numeric, Enum, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
from typing import Optional, List
import enum
import os
from dotenv import load_dotenv
from prometheus_client import Counter, Histogram, generate_latest
from prometheus_fastapi_instrumentator import Instrumentator
import time
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "mysql://telegraminvi:szkTgBhWh6XU@db:3306/telegraminvi")
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=3600)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Rate limiter setup
limiter = Limiter(key_func=get_remote_address)

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
try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    logger.error(f"Failed to create database tables: {e}")
    raise

app = FastAPI(
    title="Billing Service",
    description="Subscription and payment management service for Content Factory",
    version="1.0.0"
)

# Add rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Prometheus metrics
Instrumentator().instrument(app).expose(app)

# Metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

REQUEST_LATENCY = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency',
    ['method', 'endpoint']
)

DB_OPERATION_LATENCY = Histogram(
    'db_operation_duration_seconds',
    'Database operation latency',
    ['operation']
)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.middleware("http")
async def add_metrics(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()
    
    REQUEST_LATENCY.labels(
        method=request.method,
        endpoint=request.url.path
    ).observe(duration)
    
    return response

# Endpoints
@app.post("/plans/", response_model=Plan)
@limiter.limit("3/minute")
def create_plan(plan: PlanCreate, db: Session = Depends(get_db)):
    start_time = time.time()
    try:
        db_plan = Plan(**plan.dict())
        db.add(db_plan)
        db.commit()
        db.refresh(db_plan)
        return db_plan
    finally:
        duration = time.time() - start_time
        DB_OPERATION_LATENCY.labels(operation="create_plan").observe(duration)

@app.get("/plans/", response_model=List[Plan])
@limiter.limit("10/minute")
def get_plans(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    start_time = time.time()
    try:
        plans = db.query(Plan).filter(Plan.is_active == True).offset(skip).limit(limit).all()
        return plans
    finally:
        duration = time.time() - start_time
        DB_OPERATION_LATENCY.labels(operation="get_plans").observe(duration)

@app.post("/subscriptions/", response_model=Subscription)
@limiter.limit("3/minute")
def create_subscription(subscription: SubscriptionCreate, db: Session = Depends(get_db)):
    start_time = time.time()
    try:
        db_subscription = Subscription(**subscription.dict())
        db.add(db_subscription)
        db.commit()
        db.refresh(db_subscription)
        return db_subscription
    finally:
        duration = time.time() - start_time
        DB_OPERATION_LATENCY.labels(operation="create_subscription").observe(duration)

@app.post("/payments/", response_model=Payment)
@limiter.limit("3/minute")
def create_payment(payment: PaymentCreate, db: Session = Depends(get_db)):
    start_time = time.time()
    try:
        db_payment = Payment(**payment.dict())
        db.add(db_payment)
        db.commit()
        db.refresh(db_payment)
        return db_payment
    finally:
        duration = time.time() - start_time
        DB_OPERATION_LATENCY.labels(operation="create_payment").observe(duration)

@app.get("/payments/{subscription_id}", response_model=List[Payment])
@limiter.limit("10/minute")
def get_subscription_payments(subscription_id: int, db: Session = Depends(get_db)):
    start_time = time.time()
    try:
        payments = db.query(Payment).filter(Payment.subscription_id == subscription_id).all()
        return payments
    finally:
        duration = time.time() - start_time
        DB_OPERATION_LATENCY.labels(operation="get_subscription_payments").observe(duration)

@app.get("/health")
@limiter.limit("5/minute")
async def health_check():
    try:
        # Check database connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "service": "billing-service",
            "database": "connected"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service unhealthy"
        )

@app.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint
    """
    return generate_latest()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 
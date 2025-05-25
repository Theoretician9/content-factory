from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List, Dict
import httpx
import os
from dotenv import load_dotenv
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

load_dotenv()

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "mysql://telegraminvi:szkTgBhWh6XU@db:3306/telegraminvi")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Prometheus metrics
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

# Database Models
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    action = Column(String(255))
    resource_type = Column(String(255))
    resource_id = Column(Integer)
    details = Column(JSON)
    ip_address = Column(String(45))
    created_at = Column(DateTime, default=datetime.utcnow)

class SystemMetric(Base):
    __tablename__ = "system_metrics"

    id = Column(Integer, primary_key=True, index=True)
    service_name = Column(String(255), index=True)
    metric_name = Column(String(255))
    metric_value = Column(String(255))
    timestamp = Column(DateTime, default=datetime.utcnow)

# Pydantic models
class AuditLogBase(BaseModel):
    user_id: int
    action: str
    resource_type: str
    resource_id: int
    details: Dict
    ip_address: str

class AuditLogCreate(AuditLogBase):
    pass

class AuditLog(AuditLogBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class SystemMetricBase(BaseModel):
    service_name: str
    metric_name: str
    metric_value: str

class SystemMetricCreate(SystemMetricBase):
    pass

class SystemMetric(SystemMetricBase):
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Admin Service",
    description="Administrative and monitoring service for Content Factory",
    version="1.0.0"
)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Service URLs
SERVICE_URLS = {
    "user": os.getenv("USER_SERVICE_URL", "http://user-service:8000"),
    "billing": os.getenv("BILLING_SERVICE_URL", "http://billing-service:8000"),
    "scenario": os.getenv("SCENARIO_SERVICE_URL", "http://scenario-service:8000"),
    "content": os.getenv("CONTENT_SERVICE_URL", "http://content-service:8000"),
    "invite": os.getenv("INVITE_SERVICE_URL", "http://invite-service:8000"),
    "parsing": os.getenv("PARSING_SERVICE_URL", "http://parsing-service:8000"),
    "integration": os.getenv("INTEGRATION_SERVICE_URL", "http://integration-service:8000"),
}

# Endpoints
@app.post("/audit-logs/", response_model=AuditLog)
def create_audit_log(log: AuditLogCreate, db: Session = Depends(get_db)):
    db_log = AuditLog(**log.dict())
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log

@app.get("/audit-logs/", response_model=List[AuditLog])
def get_audit_logs(
    skip: int = 0,
    limit: int = 100,
    user_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    query = db.query(AuditLog)
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    logs = query.offset(skip).limit(limit).all()
    return logs

@app.post("/metrics/", response_model=SystemMetric)
def create_system_metric(metric: SystemMetricCreate, db: Session = Depends(get_db)):
    db_metric = SystemMetric(**metric.dict())
    db.add(db_metric)
    db.commit()
    db.refresh(db_metric)
    return db_metric

@app.get("/metrics/", response_model=List[SystemMetric])
def get_system_metrics(
    service_name: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    query = db.query(SystemMetric)
    if service_name:
        query = query.filter(SystemMetric.service_name == service_name)
    metrics = query.offset(skip).limit(limit).all()
    return metrics

@app.get("/services/health")
async def services_health_check():
    health_status = {}
    async with httpx.AsyncClient() as client:
        for service, url in SERVICE_URLS.items():
            try:
                response = await client.get(f"{url}/health")
                health_status[service] = {
                    "status": "healthy" if response.status_code == 200 else "unhealthy",
                    "status_code": response.status_code
                }
            except Exception as e:
                health_status[service] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
    return health_status

@app.get("/metrics/prometheus")
async def prometheus_metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "admin-service"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 
from fastapi import FastAPI, HTTPException, Depends, status, Request, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, JSON, ForeignKey, Text, Enum, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from pydantic import BaseModel, HttpUrl, SecretStr, EmailStr
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
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
from cryptography.fernet import Fernet
import json
import aiohttp
import asyncio
import tweepy
import facebook
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import stripe
from sendgrid import SendGridAPIClient
from twilio.rest import Client
from slack_sdk import WebClient
import discord
from telegram import Bot
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
from playwright.async_api import async_playwright
from config.database import db_settings, encryption_settings, encrypt_data, decrypt_data

load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация базы данных
DATABASE_URL = os.getenv("DATABASE_URL", "mysql://telegraminvi:szkTgBhWh6XU@db:3306/telegraminvi")
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=3600)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Rate limiter setup
limiter = Limiter(key_func=get_remote_address)

# Encryption setup
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", Fernet.generate_key())
cipher_suite = Fernet(ENCRYPTION_KEY)

# Enums
class IntegrationType(str, enum.Enum):
    TELEGRAM = "telegram"
    TWITTER = "twitter"
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    LINKEDIN = "linkedin"
    GOOGLE = "google"
    STRIPE = "stripe"
    SENDGRID = "sendgrid"
    TWILIO = "twilio"
    SLACK = "slack"
    DISCORD = "discord"

class IntegrationStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    PENDING = "pending"

# Database Models
class Integration(Base):
    __tablename__ = "integrations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    name = Column(String(255))
    description = Column(Text, nullable=True)
    integration_type = Column(Enum(IntegrationType))
    _credentials = Column("credentials", JSON)  # Зашифрованные учетные данные
    config = Column(JSON)  # Дополнительная конфигурация
    status = Column(Enum(IntegrationStatus), default=IntegrationStatus.INACTIVE)
    last_sync = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    events = relationship("IntegrationEvent", back_populates="integration")

    @property
    def credentials(self) -> Dict[str, Any]:
        """Получает расшифрованные учетные данные"""
        if not self._credentials:
            return {}
        try:
            return json.loads(decrypt_data(self._credentials))
        except Exception as e:
            logger.error(f"Error decrypting credentials: {e}")
            return {}

    @credentials.setter
    def credentials(self, value: Dict[str, Any]):
        """Шифрует и сохраняет учетные данные"""
        if value:
            self._credentials = encrypt_data(json.dumps(value))
        else:
            self._credentials = None

class IntegrationEvent(Base):
    __tablename__ = "integration_events"

    id = Column(Integer, primary_key=True, index=True)
    integration_id = Column(Integer, ForeignKey("integrations.id"))
    event_type = Column(String(50))  # sync, error, webhook, etc.
    event_data = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

    integration = relationship("Integration", back_populates="events")

# Pydantic models
class IntegrationBase(BaseModel):
    name: str
    description: Optional[str] = None
    integration_type: IntegrationType
    credentials: Dict[str, Any]
    config: Optional[Dict[str, Any]] = None

class IntegrationCreate(IntegrationBase):
    pass

class Integration(IntegrationBase):
    id: int
    user_id: int
    status: IntegrationStatus
    last_sync: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    events: List["IntegrationEvent"]

    class Config:
        from_attributes = True

class IntegrationEventBase(BaseModel):
    event_type: str
    event_data: Dict[str, Any]

class IntegrationEventCreate(IntegrationEventBase):
    pass

class IntegrationEvent(IntegrationEventBase):
    id: int
    integration_id: int
    created_at: datetime

    class Config:
        from_attributes = True

# Create database tables
try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    logger.error(f"Failed to create database tables: {e}")
    raise

app = FastAPI(
    title="Integration Service",
    description="Service for managing external service integrations",
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

INTEGRATION_SYNC_LATENCY = Histogram(
    'integration_sync_duration_seconds',
    'Integration sync latency',
    ['integration_type']
)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Helper functions
def encrypt_credentials(credentials: Dict[str, Any]) -> bytes:
    """Encrypt integration credentials."""
    return cipher_suite.encrypt(json.dumps(credentials).encode())

def decrypt_credentials(encrypted_credentials: bytes) -> Dict[str, Any]:
    """Decrypt integration credentials."""
    return json.loads(cipher_suite.decrypt(encrypted_credentials).decode())

def get_telegram_client(credentials: Dict[str, Any]) -> Bot:
    """Create Telegram bot client."""
    return Bot(token=credentials["token"])

def get_twitter_client(credentials: Dict[str, Any]) -> tweepy.Client:
    """Create Twitter API client."""
    return tweepy.Client(
        consumer_key=credentials["api_key"],
        consumer_secret=credentials["api_secret"],
        access_token=credentials["access_token"],
        access_token_secret=credentials["access_token_secret"]
    )

def get_facebook_client(credentials: Dict[str, Any]) -> facebook.GraphAPI:
    """Create Facebook API client."""
    return facebook.GraphAPI(access_token=credentials["access_token"])

def get_google_client(credentials: Dict[str, Any]) -> Any:
    """Create Google API client."""
    creds = Credentials.from_authorized_user_info(credentials)
    return build('gmail', 'v1', credentials=creds)

def get_stripe_client(credentials: Dict[str, Any]) -> stripe.Client:
    """Create Stripe client."""
    stripe.api_key = credentials["api_key"]
    return stripe

def get_sendgrid_client(credentials: Dict[str, Any]) -> SendGridAPIClient:
    """Create SendGrid client."""
    return SendGridAPIClient(credentials["api_key"])

def get_twilio_client(credentials: Dict[str, Any]) -> Client:
    """Create Twilio client."""
    return Client(credentials["account_sid"], credentials["auth_token"])

def get_slack_client(credentials: Dict[str, Any]) -> WebClient:
    """Create Slack client."""
    return WebClient(token=credentials["bot_token"])

def get_discord_client(credentials: Dict[str, Any]) -> discord.Client:
    """Create Discord client."""
    client = discord.Client()
    client.token = credentials["bot_token"]
    return client

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

async def sync_integration(integration_id: int, db: Session):
    """Sync integration with external service."""
    start_time = time.time()
    try:
        integration = db.query(Integration).filter(Integration.id == integration_id).first()
        if not integration:
            logger.error(f"Integration {integration_id} not found")
            return

        # Decrypt credentials
        credentials = decrypt_credentials(integration.credentials)
        
        # Get appropriate client
        if integration.integration_type == IntegrationType.TELEGRAM:
            client = get_telegram_client(credentials)
            # Implement Telegram sync logic
        elif integration.integration_type == IntegrationType.TWITTER:
            client = get_twitter_client(credentials)
            # Implement Twitter sync logic
        elif integration.integration_type == IntegrationType.FACEBOOK:
            client = get_facebook_client(credentials)
            # Implement Facebook sync logic
        elif integration.integration_type == IntegrationType.GOOGLE:
            client = get_google_client(credentials)
            # Implement Google sync logic
        elif integration.integration_type == IntegrationType.STRIPE:
            client = get_stripe_client(credentials)
            # Implement Stripe sync logic
        elif integration.integration_type == IntegrationType.SENDGRID:
            client = get_sendgrid_client(credentials)
            # Implement SendGrid sync logic
        elif integration.integration_type == IntegrationType.TWILIO:
            client = get_twilio_client(credentials)
            # Implement Twilio sync logic
        elif integration.integration_type == IntegrationType.SLACK:
            client = get_slack_client(credentials)
            # Implement Slack sync logic
        elif integration.integration_type == IntegrationType.DISCORD:
            client = get_discord_client(credentials)
            # Implement Discord sync logic
        else:
            raise ValueError(f"Unsupported integration type: {integration.integration_type}")
        
        # Create success event
        event = IntegrationEvent(
            integration_id=integration_id,
            event_type="sync",
            event_data={"status": "success"}
        )
        db.add(event)
        
        integration.status = IntegrationStatus.ACTIVE
        integration.last_sync = datetime.utcnow()
        db.commit()
        
    except Exception as e:
        logger.error(f"Integration {integration_id} sync failed: {str(e)}")
        
        # Create error event
        event = IntegrationEvent(
            integration_id=integration_id,
            event_type="error",
            event_data={"error": str(e)}
        )
        db.add(event)
        
        integration.status = IntegrationStatus.ERROR
        db.commit()
    finally:
        duration = time.time() - start_time
        INTEGRATION_SYNC_LATENCY.labels(
            integration_type=integration.integration_type
        ).observe(duration)

# Endpoints
@app.post("/integrations/", response_model=Integration)
@limiter.limit("3/minute")
async def create_integration(
    integration: IntegrationCreate,
    user_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    start_time = time.time()
    try:
        # Encrypt credentials before storing
        encrypted_credentials = encrypt_credentials(integration.credentials)
        
        db_integration = Integration(
            **integration.dict(exclude={'credentials'}),
            user_id=user_id,
            credentials=encrypted_credentials
        )
        db.add(db_integration)
        db.commit()
        db.refresh(db_integration)
        
        # Sync integration in background
        background_tasks.add_task(sync_integration, db_integration.id, db)
        
        return db_integration
    finally:
        duration = time.time() - start_time
        DB_OPERATION_LATENCY.labels(operation="create_integration").observe(duration)

@app.get("/integrations/", response_model=List[Integration])
@limiter.limit("10/minute")
def get_integrations(
    user_id: int,
    integration_type: Optional[IntegrationType] = None,
    status: Optional[IntegrationStatus] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    start_time = time.time()
    try:
        query = db.query(Integration).filter(Integration.user_id == user_id)
        if integration_type:
            query = query.filter(Integration.integration_type == integration_type)
        if status:
            query = query.filter(Integration.status == status)
        integrations = query.offset(skip).limit(limit).all()
        return integrations
    finally:
        duration = time.time() - start_time
        DB_OPERATION_LATENCY.labels(operation="get_integrations").observe(duration)

@app.get("/integrations/{integration_id}", response_model=Integration)
@limiter.limit("10/minute")
def get_integration(integration_id: int, db: Session = Depends(get_db)):
    start_time = time.time()
    try:
        integration = db.query(Integration).filter(Integration.id == integration_id).first()
        if not integration:
            raise HTTPException(status_code=404, detail="Integration not found")
        return integration
    finally:
        duration = time.time() - start_time
        DB_OPERATION_LATENCY.labels(operation="get_integration").observe(duration)

@app.post("/integrations/{integration_id}/sync")
@limiter.limit("3/minute")
async def sync_integration_endpoint(
    integration_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    start_time = time.time()
    try:
        integration = db.query(Integration).filter(Integration.id == integration_id).first()
        if not integration:
            raise HTTPException(status_code=404, detail="Integration not found")
        
        background_tasks.add_task(sync_integration, integration_id, db)
        return {"status": "started"}
    finally:
        duration = time.time() - start_time
        DB_OPERATION_LATENCY.labels(operation="sync_integration").observe(duration)

@app.get("/health")
@limiter.limit("5/minute")
async def health_check():
    try:
        # Check database connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "service": "integration-service",
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
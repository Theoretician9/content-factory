from fastapi import FastAPI, HTTPException, Depends, status, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, JSON, ForeignKey, Text, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from pydantic import BaseModel, HttpUrl, SecretStr
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import enum
import os
from dotenv import load_dotenv
import aiohttp
import json
import asyncio
import logging
from telegram import Bot
import tweepy
import facebook
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import stripe
from sendgrid import SendGridAPIClient
from twilio.rest import Client
from slack_sdk import WebClient
import discord

load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация базы данных
DATABASE_URL = os.getenv("DATABASE_URL", "mysql://telegraminvi:szkTgBhWh6XU@db:3306/telegraminvi")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Enums
class IntegrationType(str, enum.Enum):
    TELEGRAM = "telegram"
    TWITTER = "twitter"
    FACEBOOK = "facebook"
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

# Database Models
class Integration(Base):
    __tablename__ = "integrations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    name = Column(String(255))
    description = Column(Text, nullable=True)
    integration_type = Column(Enum(IntegrationType))
    credentials = Column(JSON)  # Зашифрованные учетные данные
    config = Column(JSON)  # Дополнительная конфигурация
    status = Column(Enum(IntegrationStatus), default=IntegrationStatus.INACTIVE)
    last_sync = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    events = relationship("IntegrationEvent", back_populates="integration")

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
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Integration Service",
    description="Service for managing external service integrations",
    version="1.0.0"
)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Helper functions
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

# Background tasks
async def sync_integration(integration_id: int, db: Session):
    """Sync integration data in background."""
    integration = db.query(Integration).filter(Integration.id == integration_id).first()
    if not integration:
        return
    
    try:
        # Get appropriate client based on integration type
        if integration.integration_type == IntegrationType.TELEGRAM:
            client = get_telegram_client(integration.credentials)
            # Implement Telegram sync logic
        elif integration.integration_type == IntegrationType.TWITTER:
            client = get_twitter_client(integration.credentials)
            # Implement Twitter sync logic
        elif integration.integration_type == IntegrationType.FACEBOOK:
            client = get_facebook_client(integration.credentials)
            # Implement Facebook sync logic
        elif integration.integration_type == IntegrationType.GOOGLE:
            client = get_google_client(integration.credentials)
            # Implement Google sync logic
        elif integration.integration_type == IntegrationType.STRIPE:
            client = get_stripe_client(integration.credentials)
            # Implement Stripe sync logic
        elif integration.integration_type == IntegrationType.SENDGRID:
            client = get_sendgrid_client(integration.credentials)
            # Implement SendGrid sync logic
        elif integration.integration_type == IntegrationType.TWILIO:
            client = get_twilio_client(integration.credentials)
            # Implement Twilio sync logic
        elif integration.integration_type == IntegrationType.SLACK:
            client = get_slack_client(integration.credentials)
            # Implement Slack sync logic
        elif integration.integration_type == IntegrationType.DISCORD:
            client = get_discord_client(integration.credentials)
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

# Endpoints
@app.post("/integrations/", response_model=Integration)
async def create_integration(
    integration: IntegrationCreate,
    user_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    db_integration = Integration(**integration.dict(), user_id=user_id)
    db.add(db_integration)
    db.commit()
    db.refresh(db_integration)
    
    # Sync integration in background
    background_tasks.add_task(sync_integration, db_integration.id, db)
    
    return db_integration

@app.get("/integrations/", response_model=List[Integration])
def get_integrations(
    user_id: int,
    integration_type: Optional[IntegrationType] = None,
    status: Optional[IntegrationStatus] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    query = db.query(Integration).filter(Integration.user_id == user_id)
    if integration_type:
        query = query.filter(Integration.integration_type == integration_type)
    if status:
        query = query.filter(Integration.status == status)
    integrations = query.offset(skip).limit(limit).all()
    return integrations

@app.get("/integrations/{integration_id}", response_model=Integration)
def get_integration(integration_id: int, db: Session = Depends(get_db)):
    integration = db.query(Integration).filter(Integration.id == integration_id).first()
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    return integration

@app.get("/integrations/{integration_id}/events", response_model=List[IntegrationEvent])
def get_integration_events(
    integration_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    events = db.query(IntegrationEvent).filter(
        IntegrationEvent.integration_id == integration_id
    ).offset(skip).limit(limit).all()
    return events

@app.post("/integrations/{integration_id}/sync")
async def sync_integration_endpoint(
    integration_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    integration = db.query(Integration).filter(Integration.id == integration_id).first()
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    
    background_tasks.add_task(sync_integration, integration_id, db)
    return {"status": "started"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "integration-service"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 
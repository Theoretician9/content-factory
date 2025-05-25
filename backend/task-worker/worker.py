from celery import Celery
from sqlalchemy import create_engine, Column, Integer, String, DateTime, JSON, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import enum
import os
from dotenv import load_dotenv
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
from prometheus_client import Counter, Histogram
import time
import celeryconfig
from contextlib import contextmanager
from typing import Generator, Dict, Any
import backoff

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Celery configuration
celery_app = Celery('worker')
celery_app.config_from_object(celeryconfig)

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://user:password@mysql:3306/task_worker")
engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Database session context manager
@contextmanager
def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Enums
class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class TaskType(str, enum.Enum):
    SYNC_INTEGRATION = "sync_integration"
    SEND_NOTIFICATION = "send_notification"
    PROCESS_WEBHOOK = "process_webhook"
    CLEANUP_DATA = "cleanup_data"
    CHECK_HEALTH = "check_health"

# Database Models
class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    task_type = Column(Enum(TaskType))
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING)
    payload = Column(JSON)
    result = Column(JSON, nullable=True)
    error = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

# Prometheus metrics
task_counter = Counter('task_total', 'Total number of tasks processed', ['task_type', 'status'])
task_duration = Histogram('task_duration_seconds', 'Task duration in seconds', ['task_type'])
health_check_counter = Counter('health_check_total', 'Total number of health checks', ['integration_type', 'status'])

# Retry decorator with exponential backoff
@backoff.on_exception(
    backoff.expo,
    Exception,
    max_tries=3,
    max_time=300
)
def retry_with_backoff(func):
    return func

# Helper functions with improved error handling and security
def get_telegram_client(credentials: Dict[str, Any]) -> Bot:
    if not credentials.get("token"):
        raise ValueError("Telegram token is required")
    return Bot(token=credentials["token"])

def get_twitter_client(credentials: Dict[str, Any]) -> tweepy.Client:
    required_keys = ["api_key", "api_secret", "access_token", "access_token_secret"]
    if not all(key in credentials for key in required_keys):
        raise ValueError("Missing required Twitter credentials")
    return tweepy.Client(
        consumer_key=credentials["api_key"],
        consumer_secret=credentials["api_secret"],
        access_token=credentials["access_token"],
        access_token_secret=credentials["access_token_secret"]
    )

def get_facebook_client(credentials: dict) -> facebook.GraphAPI:
    return facebook.GraphAPI(access_token=credentials["access_token"])

def get_google_client(credentials: dict):
    creds = Credentials.from_authorized_user_info(credentials)
    return build('gmail', 'v1', credentials=creds)

def get_stripe_client(credentials: dict):
    stripe.api_key = credentials["api_key"]
    return stripe

def get_sendgrid_client(credentials: dict) -> SendGridAPIClient:
    return SendGridAPIClient(credentials["api_key"])

def get_twilio_client(credentials: dict) -> Client:
    return Client(credentials["account_sid"], credentials["auth_token"])

def get_slack_client(credentials: dict) -> WebClient:
    return WebClient(token=credentials["bot_token"])

def get_discord_client(credentials: dict) -> discord.Client:
    client = discord.Client()
    client.token = credentials["bot_token"]
    return client

# Celery tasks with improved error handling and monitoring
@celery_app.task(name="sync_integration", bind=True, max_retries=3)
def sync_integration_task(self, integration_id: int, integration_type: str, credentials: dict, force: bool = False):
    start_time = time.time()
    task_counter.labels(task_type='sync_integration', status='started').inc()
    
    try:
        with get_db() as db:
            task = Task(
                task_type=TaskType.SYNC_INTEGRATION,
                status=TaskStatus.RUNNING,
                payload={"integration_id": integration_id, "integration_type": integration_type},
                started_at=datetime.utcnow()
            )
            db.add(task)
            db.commit()

        # Get appropriate client based on integration type
        client = retry_with_backoff(lambda: get_client_for_integration(integration_type, credentials))
        
        # Record success metrics
        task_counter.labels(task_type='sync_integration', status='success').inc()
        task_duration.labels(task_type='sync_integration').observe(time.time() - start_time)
        
        with get_db() as db:
            task.status = TaskStatus.COMPLETED
            task.result = {"status": "success", "message": f"Successfully synced {integration_type} integration"}
            task.completed_at = datetime.utcnow()
            db.commit()
        
        return task.result
        
    except Exception as e:
        logger.error(f"Integration sync failed: {str(e)}", exc_info=True)
        task_counter.labels(task_type='sync_integration', status='failed').inc()
        
        with get_db() as db:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = datetime.utcnow()
            db.commit()
        
        self.retry(exc=e, countdown=300)

@celery_app.task(name="send_notification", bind=True, max_retries=3)
def send_notification_task(self, notification_type: str, recipient: str, content: dict):
    start_time = time.time()
    task_counter.labels(task_type='send_notification', status='started').inc()
    
    try:
        # Implement notification sending logic based on type
        if notification_type == "email":
            # Send email notification
            pass
        elif notification_type == "sms":
            # Send SMS notification
            pass
        elif notification_type == "push":
            # Send push notification
            pass
        
        task_counter.labels(task_type='send_notification', status='success').inc()
        task_duration.labels(task_type='send_notification').observe(time.time() - start_time)
        
        return {"status": "success", "message": f"Successfully sent {notification_type} notification"}
        
    except Exception as e:
        logger.error(f"Notification sending failed: {str(e)}")
        task_counter.labels(task_type='send_notification', status='failed').inc()
        self.retry(exc=e, countdown=300)

@celery_app.task(name="process_webhook", bind=True, max_retries=3)
def process_webhook_task(self, webhook_type: str, payload: dict):
    start_time = time.time()
    task_counter.labels(task_type='process_webhook', status='started').inc()
    
    try:
        # Process webhook based on type
        if webhook_type == "payment":
            # Process payment webhook
            pass
        elif webhook_type == "integration":
            # Process integration webhook
            pass
        
        task_counter.labels(task_type='process_webhook', status='success').inc()
        task_duration.labels(task_type='process_webhook').observe(time.time() - start_time)
        
        return {"status": "success", "message": f"Successfully processed {webhook_type} webhook"}
        
    except Exception as e:
        logger.error(f"Webhook processing failed: {str(e)}")
        task_counter.labels(task_type='process_webhook', status='failed').inc()
        self.retry(exc=e, countdown=300)

@celery_app.task(name="cleanup_data", bind=True, max_retries=3)
def cleanup_data_task(self, data_type: str, criteria: dict):
    start_time = time.time()
    task_counter.labels(task_type='cleanup_data', status='started').inc()
    
    try:
        # Implement data cleanup logic based on type
        if data_type == "old_logs":
            # Clean up old logs
            pass
        elif data_type == "expired_tokens":
            # Clean up expired tokens
            pass
        
        task_counter.labels(task_type='cleanup_data', status='success').inc()
        task_duration.labels(task_type='cleanup_data').observe(time.time() - start_time)
        
        return {"status": "success", "message": f"Successfully cleaned up {data_type}"}
        
    except Exception as e:
        logger.error(f"Data cleanup failed: {str(e)}")
        task_counter.labels(task_type='cleanup_data', status='failed').inc()
        self.retry(exc=e, countdown=300)

@celery_app.task(name="check_integration_health", bind=True, max_retries=3)
def check_integration_health_task(self):
    start_time = time.time()
    task_counter.labels(task_type='check_health', status='started').inc()
    
    try:
        db = SessionLocal()
        integrations = db.query(Integration).filter(
            Integration.status == IntegrationStatus.ACTIVE
        ).all()
        
        for integration in integrations:
            try:
                # Check integration health based on type
                if integration.integration_type == "telegram":
                    client = get_telegram_client(integration.credentials)
                    client.get_me()
                elif integration.integration_type == "twitter":
                    client = get_twitter_client(integration.credentials)
                    client.get_me()
                # Add checks for other integration types
                
                health_check_counter.labels(
                    integration_type=integration.integration_type,
                    status='success'
                ).inc()
                
            except Exception as e:
                logger.error(f"Health check failed for integration {integration.id}: {str(e)}")
                health_check_counter.labels(
                    integration_type=integration.integration_type,
                    status='failed'
                ).inc()
                
                # Update integration status
                integration.status = IntegrationStatus.ERROR
                db.commit()
        
        task_counter.labels(task_type='check_health', status='success').inc()
        task_duration.labels(task_type='check_health').observe(time.time() - start_time)
        
        return {"status": "success", "message": "Health check completed"}
        
    except Exception as e:
        logger.error(f"Health check task failed: {str(e)}")
        task_counter.labels(task_type='check_health', status='failed').inc()
        self.retry(exc=e, countdown=300)
    finally:
        db.close()

def get_client_for_integration(integration_type: str, credentials: dict):
    client_map = {
        "telegram": get_telegram_client,
        "twitter": get_twitter_client,
        "facebook": get_facebook_client,
        "google": get_google_client,
        "stripe": get_stripe_client,
        "sendgrid": get_sendgrid_client,
        "twilio": get_twilio_client,
        "slack": get_slack_client,
        "discord": get_discord_client
    }
    
    if integration_type not in client_map:
        raise ValueError(f"Unsupported integration type: {integration_type}")
    
    return client_map[integration_type](credentials)

if __name__ == "__main__":
    celery_app.start() 
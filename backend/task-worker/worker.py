from celery import Celery
from sqlalchemy import create_engine, Column, Integer, String, DateTime, JSON, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
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

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Celery configuration
celery_app = Celery(
    'worker',
    broker=os.getenv('REDIS_URL', 'redis://redis:6379/0'),
    backend=os.getenv('REDIS_URL', 'redis://redis:6379/0')
)

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "mysql://telegraminvi:szkTgBhWh6XU@db:3306/telegraminvi")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

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

# Helper functions
def get_telegram_client(credentials: dict) -> Bot:
    return Bot(token=credentials["token"])

def get_twitter_client(credentials: dict) -> tweepy.Client:
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

# Celery tasks
@celery_app.task(name="sync_integration")
def sync_integration_task(integration_id: int, integration_type: str, credentials: dict):
    start_time = time.time()
    task_counter.labels(task_type='sync_integration', status='started').inc()
    
    try:
        # Get appropriate client based on integration type
        if integration_type == "telegram":
            client = get_telegram_client(credentials)
            # Implement Telegram sync logic
        elif integration_type == "twitter":
            client = get_twitter_client(credentials)
            # Implement Twitter sync logic
        elif integration_type == "facebook":
            client = get_facebook_client(credentials)
            # Implement Facebook sync logic
        elif integration_type == "google":
            client = get_google_client(credentials)
            # Implement Google sync logic
        elif integration_type == "stripe":
            client = get_stripe_client(credentials)
            # Implement Stripe sync logic
        elif integration_type == "sendgrid":
            client = get_sendgrid_client(credentials)
            # Implement SendGrid sync logic
        elif integration_type == "twilio":
            client = get_twilio_client(credentials)
            # Implement Twilio sync logic
        elif integration_type == "slack":
            client = get_slack_client(credentials)
            # Implement Slack sync logic
        elif integration_type == "discord":
            client = get_discord_client(credentials)
            # Implement Discord sync logic
        else:
            raise ValueError(f"Unsupported integration type: {integration_type}")
        
        # Record success metrics
        task_counter.labels(task_type='sync_integration', status='success').inc()
        task_duration.labels(task_type='sync_integration').observe(time.time() - start_time)
        
        return {"status": "success", "message": f"Successfully synced {integration_type} integration"}
        
    except Exception as e:
        logger.error(f"Integration sync failed: {str(e)}")
        task_counter.labels(task_type='sync_integration', status='failed').inc()
        raise

@celery_app.task(name="send_notification")
def send_notification_task(notification_type: str, recipient: str, content: dict):
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
        raise

@celery_app.task(name="process_webhook")
def process_webhook_task(webhook_type: str, payload: dict):
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
        raise

@celery_app.task(name="cleanup_data")
def cleanup_data_task(data_type: str, criteria: dict):
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
        raise

if __name__ == "__main__":
    celery_app.start() 
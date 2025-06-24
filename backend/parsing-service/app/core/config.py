"""
Configuration settings for Multi-Platform Parser Service.
"""

import os
from typing import Optional, List
from enum import Enum
from pydantic_settings import BaseSettings


class Platform(str, Enum):
    """Supported social media platforms."""
    TELEGRAM = "telegram"
    INSTAGRAM = "instagram"
    WHATSAPP = "whatsapp"
    FACEBOOK = "facebook"
    TWITTER = "twitter"
    LINKEDIN = "linkedin"
    TIKTOK = "tiktok"
    YOUTUBE = "youtube"


class TaskStatus(str, Enum):
    """Parse task statuses."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    WAITING = "waiting"  # Waiting for available accounts


class TaskPriority(str, Enum):
    """Parse task priorities."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class Settings(BaseSettings):
    """Application settings."""
    
    # App Info
    APP_NAME: str = "Multi-Platform Parser Service"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    
    # Database (PostgreSQL)
    POSTGRES_HOST: str = "parsing-postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "parsing_user"
    POSTGRES_PASSWORD: str = "parsing_password"
    POSTGRES_DATABASE: str = "parsing_db"
    
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DATABASE}"
    
    # Redis
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    
    @property
    def REDIS_URL(self) -> str:
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    # RabbitMQ
    RABBITMQ_HOST: str = "rabbitmq"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_USER: str = "user"
    RABBITMQ_PASSWORD: str = "password"
    RABBITMQ_VHOST: str = "/"
    
    @property
    def RABBITMQ_URL(self) -> str:
        return f"amqp://{self.RABBITMQ_USER}:{self.RABBITMQ_PASSWORD}@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}{self.RABBITMQ_VHOST}"
    
    # Vault Integration
    VAULT_ADDR: str = "http://vault:8201"
    VAULT_TOKEN: Optional[str] = None
    VAULT_ROLE_ID: Optional[str] = None
    VAULT_SECRET_ID: Optional[str] = None
    
    # JWT Authentication (будет загружена из Vault)
    JWT_SECRET_KEY: Optional[str] = None
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 30
    
    # Integration Service
    INTEGRATION_SERVICE_URL: str = "http://integration-service:8000"
    
    # Platform-specific settings
    # Telegram
    TELEGRAM_API_ID: Optional[str] = None
    TELEGRAM_API_HASH: Optional[str] = None
    
    # Instagram (planned)
    INSTAGRAM_APP_ID: Optional[str] = None
    INSTAGRAM_APP_SECRET: Optional[str] = None
    
    # WhatsApp (planned)
    WHATSAPP_BUSINESS_API_TOKEN: Optional[str] = None
    
    # Parsing limits
    DEFAULT_MESSAGE_LIMIT: int = 10000
    MAX_CONCURRENT_TASKS_PER_USER: int = 10
    MAX_ACCOUNTS_PER_PLATFORM_PER_USER: int = 50
    
    # Rate limiting
    API_RATE_LIMIT: str = "100/minute"
    PARSE_RATE_LIMIT_PER_ACCOUNT: int = 100  # messages per second
    
    # Monitoring
    PROMETHEUS_METRICS_ENABLED: bool = False  # Temporarily disabled due to CollectorRegistry conflict
    METRICS_PORT: int = 8003  # Changed from 8001 to avoid conflict with integration-service
    
    # Supported platforms (for validation)
    SUPPORTED_PLATFORMS: List[Platform] = [
        Platform.TELEGRAM,
        # Platform.INSTAGRAM,  # Phase 2
        # Platform.WHATSAPP,   # Phase 3
    ]
    
    def __init__(self, **values):
        super().__init__(**values)
        # Получаем JWT секрет из Vault с lazy import
        try:
            # Lazy import для избежания циклических импортов
            from .vault import get_vault_client
            vault_client = get_vault_client()
            secret_data = vault_client.get_secret("kv/data/jwt")
            if secret_data and 'secret_key' in secret_data:
                self.JWT_SECRET_KEY = secret_data['secret_key']
                print(f"✅ {self.APP_NAME}: JWT секрет получен из Vault")
            else:
                raise Exception("JWT secret not found in Vault")
        except Exception as e:
            # Fallback к environment variable
            self.JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'super-secret-jwt-key-for-parsing-service')
            print(f"⚠️ {self.APP_NAME}: используется JWT секрет из ENV")
            print(f"⚠️ Причина: {type(e).__name__}: {str(e)}")
    
    class Config:
        env_file = ".env"
        case_sensitive = True


def get_settings() -> Settings:
    """Get application settings instance."""
    return Settings()


# Global settings instance
settings = get_settings() 
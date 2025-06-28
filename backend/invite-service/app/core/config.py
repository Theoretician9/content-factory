"""
Конфигурация приложения Invite Service
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Настройки приложения"""
    
    # Основные настройки
    APP_NAME: str = "Invite Service"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    VERSION: str = "1.0.0"
    
    # База данных PostgreSQL
    POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER", "invite-postgres")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "invite_user")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "invite_password")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "invite_db")
    
    @property
    def DATABASE_URL(self) -> str:
        """URL подключения к базе данных"""
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )
    
    # Redis для очередей
    REDIS_HOST: str = os.getenv("REDIS_HOST", "redis")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "5"))
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD")
    
    @property
    def REDIS_URL(self) -> str:
        """URL подключения к Redis"""
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    # Celery настройки
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/5")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/5")
    
    # HashiCorp Vault
    VAULT_ADDR: str = os.getenv("VAULT_ADDR", "http://vault:8200")
    VAULT_TOKEN: Optional[str] = os.getenv("VAULT_TOKEN")
    VAULT_ROLE_ID: Optional[str] = os.getenv("VAULT_ROLE_ID")
    VAULT_SECRET_ID: Optional[str] = os.getenv("VAULT_SECRET_ID")
    
    # JWT настройки
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your-secret-key")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 30
    
    # Integration Service
    INTEGRATION_SERVICE_URL: str = os.getenv("INTEGRATION_SERVICE_URL", "http://integration-service:8000")
    
    # Ограничения для задач приглашений
    MAX_INVITES_PER_TASK: int = int(os.getenv("MAX_INVITES_PER_TASK", "1000"))
    MAX_CONCURRENT_TASKS: int = int(os.getenv("MAX_CONCURRENT_TASKS", "5"))
    INVITE_DELAY_SECONDS: int = int(os.getenv("INVITE_DELAY_SECONDS", "60"))  # Задержка между приглашениями
    
    # Telegram настройки
    TELEGRAM_API_ID: Optional[int] = int(os.getenv("TELEGRAM_API_ID", "0")) if os.getenv("TELEGRAM_API_ID") else None
    TELEGRAM_API_HASH: Optional[str] = os.getenv("TELEGRAM_API_HASH")
    
    # Prometheus метрики
    PROMETHEUS_PORT: int = int(os.getenv("PROMETHEUS_PORT", "9090"))
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Создание экземпляра настроек
settings = Settings() 
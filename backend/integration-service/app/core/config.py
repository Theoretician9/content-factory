from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache
from .vault import IntegrationVaultClient

class Settings(BaseSettings):
    # Базовые настройки
    APP_NAME: str = "Integration Service"
    DEBUG: bool = False
    VERSION: str = "1.0.0"
    
    # Vault настройки
    VAULT_ADDR: str = "http://vault:8201"
    VAULT_TOKEN: str = "root"  # В продакшене должен быть заменен на реальный токен
    
    # PostgreSQL база данных
    POSTGRES_HOST: str
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DATABASE: str
    
    # Redis
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    
    # RabbitMQ
    RABBITMQ_HOST: str = "rabbitmq"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_USER: str = "user"
    RABBITMQ_PASSWORD: str = "password"
    
    # JWT секреты
    JWT_SECRET_KEY: str = "super-secret-jwt-key-for-content-factory-2024"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_DELTA: int = 3600  # 1 час
    
    # Rate limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_PERIOD: int = 60  # секунды
    
    # Telegram API
    TELEGRAM_API_ID: Optional[str] = None
    TELEGRAM_API_HASH: Optional[str] = None
    
    # Логирование
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    
    # Мониторинг
    PROMETHEUS_ENABLED: bool = True
    HEALTH_CHECK_ENABLED: bool = True
    
    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DATABASE}"
    
    @property
    def database_url_sync(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DATABASE}"
    
    @property
    def redis_url(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    @property
    def rabbitmq_url(self) -> str:
        return f"amqp://{self.RABBITMQ_USER}:{self.RABBITMQ_PASSWORD}@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}//"
    
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings() -> Settings:
    return Settings()

@lru_cache()
def get_vault_client() -> IntegrationVaultClient:
    settings = get_settings()
    return IntegrationVaultClient() 
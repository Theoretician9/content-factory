from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache
from .vault import IntegrationVaultClient

class Settings(BaseSettings):
    # Базовые настройки
    APP_NAME: str = "Integration Service"
    DEBUG: bool = False
    
    # Vault настройки
    VAULT_ADDR: str = "http://vault:8200"
    VAULT_TOKEN: str = "root"  # В продакшене должен быть заменен на реальный токен
    
    # База данных
    MYSQL_HOST: str
    MYSQL_PORT: int
    MYSQL_USER: str
    MYSQL_PASSWORD: str
    MYSQL_DATABASE: str
    
    # Redis
    REDIS_HOST: str
    REDIS_PORT: int
    
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings() -> Settings:
    return Settings()

@lru_cache()
def get_vault_client() -> IntegrationVaultClient:
    settings = get_settings()
    return IntegrationVaultClient() 
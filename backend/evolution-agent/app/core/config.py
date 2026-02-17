import os
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings

from .vault import get_vault_client


class Settings(BaseSettings):
    """Конфигурация evolution-agent."""

    APP_NAME: str = "Evolution Agent Service"
    VERSION: str = "0.1.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # JWT
    JWT_SECRET_KEY: Optional[str] = None
    JWT_ALGORITHM: str = "HS256"

    # БД evolution_db (PostgreSQL, async)
    DATABASE_URL: Optional[str] = None

    # LLM API keys (из Vault: openai, evolution-agent/gemini, evolution-agent/groq, evolution-agent/openrouter)
    OPENAI_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None

    # OpenRouter (OpenAI-совместимый провайдер, например DeepSeek через OpenRouter)
    OPENROUTER_API_KEY: Optional[str] = None

    # Конфигурация провайдера для Content Agent
    # content_provider: "openai" (по умолчанию) или "openrouter"
    LLM_CONTENT_PROVIDER: str = os.getenv("LLM_CONTENT_PROVIDER", "openai")
    # Явная модель для Content Agent; если не задана, используются дефолты в llm.py
    LLM_CONTENT_MODEL: Optional[str] = os.getenv("LLM_CONTENT_MODEL")
    # Конфигурация модели для Research Agent (Gemini); по умолчанию берётся из llm.MODEL_RESEARCH
    LLM_RESEARCH_MODEL: Optional[str] = os.getenv("LLM_RESEARCH_MODEL")

    class Config:
        env_file = ".env"
        case_sensitive = True

    def __init__(self, **values):
        super().__init__(**values)

        # 1. Загружаем JWT секрет из Vault
        try:
            vault_client = get_vault_client()
            jwt_data = vault_client.get_secret("jwt")
            self.JWT_SECRET_KEY = jwt_data.get("secret_key")
            print("✅ evolution-agent: JWT секрет получен из Vault")
        except Exception as e:
            # Fallback на переменные окружения
            self.JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "evolution-agent-fallback-secret")
            print(f"⚠ evolution-agent: используем JWT секрет из ENV: {e}")

        # 2. Загружаем строку подключения к БД из Vault
        if not self.DATABASE_URL:
            try:
                vault_client = get_vault_client()
                db_data = vault_client.get_secret("evolution-agent/db")
                db_url = db_data.get("database_url")
                if db_url:
                    self.DATABASE_URL = db_url
                    print("✅ evolution-agent: DATABASE_URL получен из Vault")
            except Exception as e:
                # Fallback на дефолтную строку (локальная разработка)
                if not self.DATABASE_URL:
                    self.DATABASE_URL = (
                        "postgresql+asyncpg://evolution_user:evolution_password"
                        "@evolution-postgres:5432/evolution_db"
                    )
                    print(
                        f"⚠ evolution-agent: используем дефолтный DATABASE_URL для локальной разработки: {e}"
                    )

        # 3. Загружаем ключи LLM из Vault
        try:
            vault_client = get_vault_client()
            # OpenAI (GPT-4o-mini для Content Agent)
            try:
                openai_data = vault_client.get_secret("openai")
                self.OPENAI_API_KEY = openai_data.get("api_key")
            except Exception:
                self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
            # Gemini (Research Agent)
            try:
                gemini_data = vault_client.get_secret("evolution-agent/gemini")
                self.GEMINI_API_KEY = gemini_data.get("api_key")
            except Exception:
                self.GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
            # Groq (Llama 3.1 8B для Persona/Strategy)
            try:
                groq_data = vault_client.get_secret("evolution-agent/groq")
                self.GROQ_API_KEY = groq_data.get("api_key")
            except Exception:
                self.GROQ_API_KEY = os.getenv("GROQ_API_KEY")
            # OpenRouter (альтернатива OpenAI для Content Agent)
            try:
                openrouter_data = vault_client.get_secret("evolution-agent/openrouter")
                self.OPENROUTER_API_KEY = openrouter_data.get("api_key")
            except Exception:
                self.OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
        except Exception as e:
            print(f"⚠ evolution-agent: LLM keys from ENV fallback: {e}")


@lru_cache()
def get_settings() -> Settings:
    return Settings()


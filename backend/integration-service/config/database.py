from pydantic_settings import BaseSettings
from cryptography.fernet import Fernet
import os
from dotenv import load_dotenv

load_dotenv()

class DatabaseSettings(BaseSettings):
    # PostgreSQL для Integration Service
    host: str = os.getenv("POSTGRES_HOST", "integration-postgres")
    port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    user: str = os.getenv("POSTGRES_USER", "integration_user")
    password: str = os.getenv("POSTGRES_PASSWORD", "integration_password")
    database: str = os.getenv("POSTGRES_DATABASE", "integration_db")

    @property
    def url(self) -> str:
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
    
    @property
    def sync_url(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

class EncryptionSettings(BaseSettings):
    # Ключ шифрования для чувствительных данных
    encryption_key: str = os.getenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    
    def get_fernet(self) -> Fernet:
        return Fernet(self.encryption_key.encode())

db_settings = DatabaseSettings()
encryption_settings = EncryptionSettings()
cipher_suite = encryption_settings.get_fernet()

def encrypt_data(data: str) -> str:
    """Шифрует данные"""
    return cipher_suite.encrypt(data.encode()).decode()

def decrypt_data(encrypted_data: str) -> str:
    """Расшифровывает данные"""
    return cipher_suite.decrypt(encrypted_data.encode()).decode() 
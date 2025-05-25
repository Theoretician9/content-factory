from cryptography.fernet import Fernet
from pydantic_settings import BaseSettings
import os
from dotenv import load_dotenv

load_dotenv()

class DatabaseSettings(BaseSettings):
    DB_HOST: str = os.getenv("DB_HOST", "db")
    DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
    DB_NAME: str = os.getenv("DB_NAME", "telegraminvi")
    DB_USER: str = os.getenv("DB_USER", "telegraminvi")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    
    @property
    def DATABASE_URL(self) -> str:
        return f"mysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

class EncryptionSettings(BaseSettings):
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.ENCRYPTION_KEY:
            self.ENCRYPTION_KEY = Fernet.generate_key().decode()
    
    @property
    def fernet(self) -> Fernet:
        return Fernet(self.ENCRYPTION_KEY.encode())

# Создаем экземпляры настроек
db_settings = DatabaseSettings()
encryption_settings = EncryptionSettings()

def encrypt_data(data: str) -> str:
    """Шифрует строку данных"""
    return encryption_settings.fernet.encrypt(data.encode()).decode()

def decrypt_data(encrypted_data: str) -> str:
    """Расшифровывает строку данных"""
    return encryption_settings.fernet.decrypt(encrypted_data.encode()).decode() 
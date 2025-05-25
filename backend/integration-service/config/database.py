from pydantic_settings import BaseSettings
from cryptography.fernet import Fernet
import os
from dotenv import load_dotenv

load_dotenv()

class DatabaseSettings(BaseSettings):
    host: str = os.getenv("MYSQL_HOST", "mysql")
    port: int = int(os.getenv("MYSQL_PORT", "3306"))
    user: str = os.getenv("MYSQL_USER", "user")
    password: str = os.getenv("MYSQL_PASSWORD", "password")
    database: str = os.getenv("MYSQL_DATABASE", "integration_service")

    @property
    def url(self) -> str:
        return f"mysql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

class EncryptionSettings(BaseSettings):
    key: str = os.getenv("ENCRYPTION_KEY", Fernet.generate_key().decode())

db_settings = DatabaseSettings()
encryption_settings = EncryptionSettings()
cipher_suite = Fernet(encryption_settings.key.encode())

def encrypt_data(data: str) -> str:
    """Шифрует данные"""
    return cipher_suite.encrypt(data.encode()).decode()

def decrypt_data(encrypted_data: str) -> str:
    """Расшифровывает данные"""
    return cipher_suite.decrypt(encrypted_data.encode()).decode() 
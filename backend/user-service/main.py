from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
from typing import Optional
from passlib.context import CryptContext
from jose import JWTError, jwt
import os
from dotenv import load_dotenv
from prometheus_client import Counter, Histogram, generate_latest
from prometheus_fastapi_instrumentator import Instrumentator
import time
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import logging
from common.vault_client import VaultClient
import secrets
import redis

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://telegraminvi:szkTgBhWh6XU@mysql:3306/user_service")
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=3600)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Redis configuration
try:
    redis_client = redis.Redis(
        host=os.getenv("REDIS_HOST", "redis"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        db=int(os.getenv("REDIS_DB", 0)),
        decode_responses=True
    )
    # Проверяем подключение
    redis_client.ping()
    logger.info("✅ User Service: подключение к Redis успешно")
except Exception as e:
    logger.error(f"❌ User Service: не удалось подключиться к Redis: {e}")
    redis_client = None

# Security configuration
# SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")

# Получаем JWT секрет из Vault
vault_client = VaultClient()
try:
    SECRET_KEY = vault_client.get_secret("kv/data/jwt")['secret_key']
except Exception as e:
    raise RuntimeError(f"Не удалось получить JWT секрет из Vault: {e}")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 30

# Используем bcrypt_sha256 (решает ограничение 72 байт у bcrypt) с fallback на bcrypt для совместимости
pwd_context = CryptContext(
    schemes=["bcrypt_sha256", "bcrypt"],
    deprecated="auto"
)
# Database Models
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True)
    username = Column(String(255), unique=True, index=True)
    hashed_password = Column(String(255))
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Pydantic models
class UserBase(BaseModel):
    email: EmailStr
    username: str

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str
    refresh_token: Optional[str] = None

class TokenData(BaseModel):
    username: Optional[str] = None

# Create database tables
try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    logger.error(f"Failed to create database tables: {e}")
    raise

app = FastAPI(
    title="User Service",
    description="User management service for Content Factory",
    version="1.0.0"
)

# Add rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Prometheus metrics
Instrumentator().instrument(app).expose(app)

# Metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

REQUEST_LATENCY = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency',
    ['method', 'endpoint']
)

DB_OPERATION_LATENCY = Histogram(
    'db_operation_duration_seconds',
    'Database operation latency',
    ['operation']
)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Helper functions
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(user_id: int) -> str:
    """Создает refresh токен и сохраняет его в Redis"""
    refresh_token = secrets.token_urlsafe(32)
    
    if redis_client:
        try:
            # Сохраняем в Redis с TTL в секундах
            ttl_seconds = REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
            redis_client.setex(f"refresh_token:{refresh_token}", ttl_seconds, str(user_id))
            logger.info(f"🔑 Refresh токен создан для пользователя {user_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка при сохранении refresh токена в Redis: {e}")
    else:
        logger.warning("⚠️ Redis недоступен, refresh токен не сохранен")
    
    return refresh_token

@app.middleware("http")
async def add_metrics(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()
    
    REQUEST_LATENCY.labels(
        method=request.method,
        endpoint=request.url.path
    ).observe(duration)
    
    return response

# Helper function for getting current user
async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Проверяем blacklist токенов только если Redis доступен
        if redis_client:
            try:
                if redis_client.exists(f"blacklist:{token}"):
                    logger.warning("⚠️ Токен находится в blacklist")
                    raise credentials_exception
            except Exception as e:
                logger.warning(f"⚠️ Ошибка при проверке blacklist в Redis: {e}")
            
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        # Теперь ищем по email, потому что JWT содержит email
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception
    return user

# Endpoints
@app.post("/token", response_model=Token)
@limiter.limit("5/minute")
async def login_for_access_token(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    start_time = time.time()
    try:
        logger.info(f"🔐 User Service: попытка логина для пользователя '{form_data.username}'")
        
        # Проверяем подключение к базе данных
        try:
            db.execute(text("SELECT 1"))
            logger.info(f"✅ User Service: подключение к базе данных работает")
        except Exception as e:
            logger.error(f"❌ User Service: ошибка подключения к базе данных: {e}")
            raise HTTPException(status_code=500, detail="Database connection error")
        
        # Показываем всех пользователей для отладки
        try:
            total_users = db.query(User).count()
            logger.info(f"📊 User Service: всего пользователей в базе: {total_users}")
            
            all_users = db.query(User).all()
            for u in all_users:
                logger.info(f"👤 User Service: пользователь id={u.id}, email='{u.email}', username='{u.username}'")
        except Exception as e:
            logger.error(f"❌ User Service: ошибка при запросе пользователей: {e}")
        
        # Ищем пользователя по username
        user = db.query(User).filter(User.username == form_data.username).first()
        logger.info(f"🔍 User Service: поиск пользователя по username='{form_data.username}', найден: {user is not None}")
        
        if not user:
            logger.warning(f"⚠️ User Service: пользователь с username '{form_data.username}' не найден")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Проверяем пароль
        password_valid = verify_password(form_data.password, user.hashed_password)
        logger.info(f"🔒 User Service: проверка пароля для пользователя '{user.username}': {password_valid}")
        
        if not password_valid:
            logger.warning(f"⚠️ User Service: неверный пароль для пользователя '{form_data.username}'")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        logger.info(f"✅ User Service: успешная аутентификация для пользователя '{user.username}'")
        
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.email}, expires_delta=access_token_expires
        )
        
        # Создаем refresh токен
        refresh_token = create_refresh_token(user.id)
        
        return {
            "access_token": access_token, 
            "token_type": "bearer",
            "refresh_token": refresh_token
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ User Service: неожиданная ошибка при логине: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        duration = time.time() - start_time
        DB_OPERATION_LATENCY.labels(operation="login").observe(duration)

@app.post("/users/", response_model=UserResponse)
@limiter.limit("3/minute")
def create_user(request: Request, user: UserCreate, db: Session = Depends(get_db)):
    start_time = time.time()
    try:
        db_user = db.query(User).filter(User.email == user.email).first()
        if db_user:
            raise HTTPException(status_code=400, detail="Email already registered")
        db_user = db.query(User).filter(User.username == user.username).first()
        if db_user:
            raise HTTPException(status_code=400, detail="Username already taken")
        
        hashed_password = get_password_hash(user.password)
        db_user = User(
            email=user.email,
            username=user.username,
            hashed_password=hashed_password
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user
    finally:
        duration = time.time() - start_time
        DB_OPERATION_LATENCY.labels(operation="create_user").observe(duration)

@app.get("/users/me", response_model=UserResponse)
@limiter.limit("10/minute")
async def read_users_me(request: Request, current_user: User = Depends(get_current_user)):
    return current_user

@app.post("/auth/logout")
@limiter.limit("10/minute")
async def logout(request: Request):
    """
    Logout endpoint - инвалидирует refresh токен
    """
    try:
        logger.info("🚪 User Service: logout request received")
        logger.info(f"🚪 User Service: headers = {dict(request.headers)}")
        logger.info(f"🚪 User Service: cookies = {dict(request.cookies)}")
        
        # Получаем refresh токен из cookies
        refresh_token = request.cookies.get("refresh_token")
        
        if refresh_token and redis_client:
            try:
                # Проверяем существование токена в Redis
                user_id = redis_client.get(f"refresh_token:{refresh_token}")
                if user_id:
                    # Удаляем refresh токен из Redis
                    redis_client.delete(f"refresh_token:{refresh_token}")
                    logger.info(f"🔑 Refresh токен удален для пользователя {user_id}")
                else:
                    logger.warning("⚠️ Refresh токен не найден в Redis")
            except Exception as e:
                logger.error(f"❌ Ошибка при работе с refresh токеном в Redis: {e}")
        elif refresh_token and not redis_client:
            logger.warning("⚠️ Redis недоступен, refresh токен не может быть удален")
        else:
            logger.warning("⚠️ Refresh токен отсутствует в cookies")
        
        # Получаем JWT токен из Authorization header
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            try:
                # Декодируем токен для получения информации
                payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
                user_email = payload.get("sub")
                
                # Добавляем токен в blacklist (сохраняем в Redis до истечения)
                if redis_client:
                    try:
                        token_exp = payload.get("exp")
                        if token_exp:
                            current_time = datetime.utcnow().timestamp()
                            ttl = int(token_exp - current_time)
                            if ttl > 0:
                                redis_client.setex(f"blacklist:{token}", ttl, user_email)
                                logger.info(f"🚫 JWT токен добавлен в blacklist для {user_email}")
                    except Exception as e:
                        logger.error(f"❌ Ошибка при добавлении токена в blacklist: {e}")
                else:
                    logger.warning("⚠️ Redis недоступен, JWT токен не добавлен в blacklist")
                
            except jwt.ExpiredSignatureError:
                logger.info("⏰ JWT токен уже истек")
            except jwt.InvalidTokenError:
                logger.warning("⚠️ Невалидный JWT токен")
        else:
            logger.warning("⚠️ Authorization header отсутствует или неверный формат")
        
        return {"message": "Successfully logged out"}
    except Exception as e:
        logger.error(f"Logout error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )

@app.get("/health")
@limiter.limit("5/minute")
async def health_check(request: Request):
    try:
        # Check database connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "service": "user-service",
            "database": "connected"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service unhealthy"
        )

@app.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint
    """
    return generate_latest()

@app.get("/internal/users/by-email")
def get_user_by_email(email: str, db: Session = Depends(get_db)):
    # Логируем email на входе
    logger.info(f"🔍 User Service: получен запрос на поиск пользователя по email: '{email}'")
    
    # Проверяем подключение к базе данных
    try:
        db.execute(text("SELECT 1"))
        logger.info(f"✅ User Service: подключение к базе данных работает")
    except Exception as e:
        logger.error(f"❌ User Service: ошибка подключения к базе данных: {e}")
        raise HTTPException(status_code=500, detail="Database connection error")
    
    # Нормализуем email (убираем пробелы и приводим к нижнему регистру)
    email = email.strip().lower()
    logger.info(f"🔍 User Service: нормализованный email: '{email}'")
    
    # Проверяем сколько пользователей всего в базе
    try:
        total_users = db.query(User).count()
        logger.info(f"📊 User Service: всего пользователей в базе: {total_users}")
        
        # Выводим всех пользователей для отладки
        all_users = db.query(User).all()
        for u in all_users:
            logger.info(f"👤 User Service: найден пользователь id={u.id}, email='{u.email}', username='{u.username}'")
            
    except Exception as e:
        logger.error(f"❌ User Service: ошибка при запросе пользователей: {e}")
    
    # Ищем пользователя по email
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            logger.warning(f"⚠️ User Service: пользователь с email '{email}' не найден")
            raise HTTPException(status_code=404, detail="User not found")
        logger.info(f"✅ User Service: пользователь найден, id={user.id}, email={user.email}")
        return {"id": user.id, "email": user.email}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ User Service: ошибка при поиске пользователя: {e}")
        raise HTTPException(status_code=500, detail="Database query error")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 
"""
Invite Service - Микросервис для массовых рассылок и приглашений в мессенджеры
"""

import logging
from fastapi import FastAPI, HTTPException, Depends, status, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, JSON, ForeignKey, Text, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import enum
import os
from dotenv import load_dotenv
import qrcode
from io import BytesIO
import base64
import jinja2
import aiohttp
import json
import secrets

load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "mysql://telegraminvi:szkTgBhWh6XU@db:3306/telegraminvi")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Enums
class InviteStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"

class InviteType(str, enum.Enum):
    EMAIL = "email"
    LINK = "link"
    QR = "qr"

# Database Models
class Invite(Base):
    __tablename__ = "invites"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    invite_type = Column(Enum(InviteType))
    status = Column(Enum(InviteStatus), default=InviteStatus.PENDING)
    email = Column(String(255), nullable=True)
    token = Column(String(255), unique=True, index=True)
    expires_at = Column(DateTime)
    metadata = Column(JSON)  # Additional data like roles, permissions, etc.
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    events = relationship("InviteEvent", back_populates="invite")

class InviteEvent(Base):
    __tablename__ = "invite_events"

    id = Column(Integer, primary_key=True, index=True)
    invite_id = Column(Integer, ForeignKey("invites.id"))
    event_type = Column(String(50))  # sent, opened, clicked, etc.
    event_data = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

    invite = relationship("Invite", back_populates="events")

class InviteTemplate(Base):
    __tablename__ = "invite_templates"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    name = Column(String(255))
    description = Column(Text)
    template_type = Column(Enum(InviteType))
    subject = Column(String(255))
    body = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Pydantic models
class InviteBase(BaseModel):
    invite_type: InviteType
    email: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class InviteCreate(InviteBase):
    expires_in_days: int = 7

class Invite(InviteBase):
    id: int
    user_id: int
    status: InviteStatus
    token: str
    expires_at: datetime
    created_at: datetime
    updated_at: datetime
    events: List["InviteEvent"]

    class Config:
        from_attributes = True

class InviteEventBase(BaseModel):
    event_type: str
    event_data: Optional[Dict[str, Any]] = None

class InviteEventCreate(InviteEventBase):
    pass

class InviteEvent(InviteEventBase):
    id: int
    invite_id: int
    created_at: datetime

    class Config:
        from_attributes = True

class InviteTemplateBase(BaseModel):
    name: str
    description: Optional[str] = None
    template_type: InviteType
    subject: str
    body: str

class InviteTemplateCreate(InviteTemplateBase):
    pass

class InviteTemplate(InviteTemplateBase):
    id: int
    user_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Create database tables
Base.metadata.create_all(bind=engine)

# Создание FastAPI приложения
app = FastAPI(
    title="Invite Service API",
    description="Микросервис для массовых рассылок и приглашений в мессенджеры",
    version="1.0.0"
)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Helper functions
def generate_token() -> str:
    """Generate a secure random token."""
    return secrets.token_urlsafe(32)

def generate_qr_code(data: str) -> str:
    """Generate QR code and return as base64 string."""
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

def render_template(template_str: str, data: Dict[str, Any]) -> str:
    """Render template with given data."""
    template = jinja2.Template(template_str)
    return template.render(**data)

async def send_email(email: str, subject: str, body: str):
    """Send email using external service."""
    # Implementation depends on email service provider
    pass

# Background tasks
async def process_invite(invite_id: int, db: Session):
    """Process invite in background."""
    invite = db.query(Invite).filter(Invite.id == invite_id).first()
    if not invite:
        return
    
    try:
        if invite.invite_type == InviteType.EMAIL:
            template = db.query(InviteTemplate).filter(
                InviteTemplate.template_type == InviteType.EMAIL,
                InviteTemplate.is_active == True
            ).first()
            
            if template:
                body = render_template(template.body, {
                    "invite": invite,
                    "token": invite.token
                })
                await send_email(invite.email, template.subject, body)
        
        # Create event
        event = InviteEvent(
            invite_id=invite_id,
            event_type="sent",
            event_data={"status": "success"}
        )
        db.add(event)
        db.commit()
    
    except Exception as e:
        event = InviteEvent(
            invite_id=invite_id,
            event_type="error",
            event_data={"error": str(e)}
        )
        db.add(event)
        db.commit()

# Endpoints
@app.post("/invites/", response_model=Invite)
async def create_invite(
    invite: InviteCreate,
    user_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    # Generate token and expiration
    token = generate_token()
    expires_at = datetime.utcnow() + timedelta(days=invite.expires_in_days)
    
    # Create invite
    db_invite = Invite(
        **invite.dict(),
        user_id=user_id,
        token=token,
        expires_at=expires_at
    )
    db.add(db_invite)
    db.commit()
    db.refresh(db_invite)
    
    # Process invite in background
    background_tasks.add_task(process_invite, db_invite.id, db)
    
    return db_invite

@app.get("/invites/", response_model=List[Invite])
def get_invites(
    user_id: int,
    status: Optional[InviteStatus] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    query = db.query(Invite).filter(Invite.user_id == user_id)
    if status:
        query = query.filter(Invite.status == status)
    invites = query.offset(skip).limit(limit).all()
    return invites

@app.get("/invites/{token}", response_model=Invite)
def get_invite_by_token(token: str, db: Session = Depends(get_db)):
    invite = db.query(Invite).filter(Invite.token == token).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    
    if invite.status != InviteStatus.PENDING:
        raise HTTPException(status_code=400, detail="Invite is no longer valid")
    
    if invite.expires_at < datetime.utcnow():
        invite.status = InviteStatus.EXPIRED
        db.commit()
        raise HTTPException(status_code=400, detail="Invite has expired")
    
    return invite

@app.post("/invites/{token}/accept")
def accept_invite(token: str, db: Session = Depends(get_db)):
    invite = db.query(Invite).filter(Invite.token == token).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    
    if invite.status != InviteStatus.PENDING:
        raise HTTPException(status_code=400, detail="Invite is no longer valid")
    
    if invite.expires_at < datetime.utcnow():
        invite.status = InviteStatus.EXPIRED
        db.commit()
        raise HTTPException(status_code=400, detail="Invite has expired")
    
    invite.status = InviteStatus.ACCEPTED
    event = InviteEvent(
        invite_id=invite.id,
        event_type="accepted"
    )
    db.add(event)
    db.commit()
    
    return {"status": "success"}

@app.post("/invites/{token}/reject")
def reject_invite(token: str, db: Session = Depends(get_db)):
    invite = db.query(Invite).filter(Invite.token == token).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    
    if invite.status != InviteStatus.PENDING:
        raise HTTPException(status_code=400, detail="Invite is no longer valid")
    
    invite.status = InviteStatus.REJECTED
    event = InviteEvent(
        invite_id=invite.id,
        event_type="rejected"
    )
    db.add(event)
    db.commit()
    
    return {"status": "success"}

@app.post("/templates/", response_model=InviteTemplate)
def create_template(template: InviteTemplateCreate, user_id: int, db: Session = Depends(get_db)):
    db_template = InviteTemplate(**template.dict(), user_id=user_id)
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    return db_template

@app.get("/templates/", response_model=List[InviteTemplate])
def get_templates(
    user_id: int,
    template_type: Optional[InviteType] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    query = db.query(InviteTemplate).filter(InviteTemplate.user_id == user_id)
    if template_type:
        query = query.filter(InviteTemplate.template_type == template_type)
    templates = query.offset(skip).limit(limit).all()
    return templates

@app.get("/invites/{token}/qr")
def get_invite_qr(token: str, db: Session = Depends(get_db)):
    invite = db.query(Invite).filter(Invite.token == token).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    
    # Generate QR code with invite URL
    invite_url = f"{os.getenv('FRONTEND_URL', 'http://localhost:3000')}/invite/{token}"
    qr_code = generate_qr_code(invite_url)
    
    return {"qr_code": qr_code}

@app.get("/health")
async def health_check():
    """Базовый health check"""
    return {"status": "healthy", "service": "invite-service"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 
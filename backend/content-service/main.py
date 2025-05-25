from fastapi import FastAPI, HTTPException, Depends, status, UploadFile, File
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, JSON, ForeignKey, Text, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List, Dict, Any
import enum
import os
from dotenv import load_dotenv
import openai
from langchain.llms import OpenAI
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
import json

load_dotenv()

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "mysql://telegraminvi:szkTgBhWh6XU@db:3306/telegraminvi")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# OpenAI configuration
openai.api_key = os.getenv("OPENAI_API_KEY")
llm = OpenAI(temperature=0.7)

# Enums
class ContentType(str, enum.Enum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    PRESENTATION = "presentation"

class ContentStatus(str, enum.Enum):
    DRAFT = "draft"
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"

class GenerationType(str, enum.Enum):
    AI = "ai"
    TEMPLATE = "template"
    MANUAL = "manual"

# Database Models
class Content(Base):
    __tablename__ = "contents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    scenario_id = Column(Integer, ForeignKey("scenarios.id"), nullable=True)
    name = Column(String(255))
    description = Column(Text)
    content_type = Column(Enum(ContentType))
    status = Column(Enum(ContentStatus), default=ContentStatus.DRAFT)
    generation_type = Column(Enum(GenerationType))
    content_data = Column(JSON)  # Stores the actual content or references
    metadata = Column(JSON)  # Additional metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    versions = relationship("ContentVersion", back_populates="content")

class ContentVersion(Base):
    __tablename__ = "content_versions"

    id = Column(Integer, primary_key=True, index=True)
    content_id = Column(Integer, ForeignKey("contents.id"))
    version_number = Column(Integer)
    content_data = Column(JSON)
    metadata = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer)  # user_id

    content = relationship("Content", back_populates="versions")

class Template(Base):
    __tablename__ = "templates"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    name = Column(String(255))
    description = Column(Text)
    content_type = Column(Enum(ContentType))
    template_data = Column(JSON)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Pydantic models
class ContentBase(BaseModel):
    name: str
    description: Optional[str] = None
    content_type: ContentType
    generation_type: GenerationType
    content_data: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None

class ContentCreate(ContentBase):
    scenario_id: Optional[int] = None

class Content(ContentBase):
    id: int
    user_id: int
    scenario_id: Optional[int]
    status: ContentStatus
    created_at: datetime
    updated_at: datetime
    versions: List["ContentVersion"]

    class Config:
        from_attributes = True

class ContentVersionBase(BaseModel):
    version_number: int
    content_data: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None

class ContentVersionCreate(ContentVersionBase):
    pass

class ContentVersion(ContentVersionBase):
    id: int
    content_id: int
    created_at: datetime
    created_by: int

    class Config:
        from_attributes = True

class TemplateBase(BaseModel):
    name: str
    description: Optional[str] = None
    content_type: ContentType
    template_data: Dict[str, Any]

class TemplateCreate(TemplateBase):
    pass

class Template(TemplateBase):
    id: int
    user_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Content Service",
    description="Content generation and management service for Content Factory",
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
def generate_text_content(prompt: str, parameters: Dict[str, Any]) -> str:
    """Generate text content using OpenAI."""
    template = PromptTemplate(
        input_variables=["prompt"],
        template="{prompt}"
    )
    chain = LLMChain(llm=llm, prompt=template)
    return chain.run(prompt=prompt)

def process_template(template_data: Dict[str, Any], parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Process a template with given parameters."""
    # Implementation depends on template type and structure
    return template_data

# Endpoints
@app.post("/contents/", response_model=Content)
def create_content(content: ContentCreate, user_id: int, db: Session = Depends(get_db)):
    db_content = Content(**content.dict(), user_id=user_id)
    db.add(db_content)
    db.commit()
    db.refresh(db_content)
    return db_content

@app.get("/contents/", response_model=List[Content])
def get_contents(
    user_id: int,
    content_type: Optional[ContentType] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    query = db.query(Content).filter(Content.user_id == user_id)
    if content_type:
        query = query.filter(Content.content_type == content_type)
    contents = query.offset(skip).limit(limit).all()
    return contents

@app.get("/contents/{content_id}", response_model=Content)
def get_content(content_id: int, db: Session = Depends(get_db)):
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    return content

@app.post("/contents/{content_id}/generate")
async def generate_content(
    content_id: int,
    parameters: Dict[str, Any],
    db: Session = Depends(get_db)
):
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    
    try:
        content.status = ContentStatus.GENERATING
        db.commit()
        
        if content.generation_type == GenerationType.AI:
            if content.content_type == ContentType.TEXT:
                generated_content = generate_text_content(
                    parameters.get("prompt", ""),
                    parameters
                )
                content.content_data = {"text": generated_content}
            # Add other content type generations here
        
        elif content.generation_type == GenerationType.TEMPLATE:
            template = db.query(Template).filter(
                Template.id == parameters.get("template_id")
            ).first()
            if not template:
                raise HTTPException(status_code=404, detail="Template not found")
            
            content.content_data = process_template(template.template_data, parameters)
        
        content.status = ContentStatus.READY
        db.commit()
        
        return {"status": "success", "content": content.content_data}
    
    except Exception as e:
        content.status = ContentStatus.FAILED
        db.commit()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/contents/{content_id}/versions/", response_model=ContentVersion)
def create_content_version(
    content_id: int,
    version: ContentVersionCreate,
    user_id: int,
    db: Session = Depends(get_db)
):
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    
    db_version = ContentVersion(
        **version.dict(),
        content_id=content_id,
        created_by=user_id
    )
    db.add(db_version)
    db.commit()
    db.refresh(db_version)
    return db_version

@app.post("/templates/", response_model=Template)
def create_template(template: TemplateCreate, user_id: int, db: Session = Depends(get_db)):
    db_template = Template(**template.dict(), user_id=user_id)
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    return db_template

@app.get("/templates/", response_model=List[Template])
def get_templates(
    user_id: int,
    content_type: Optional[ContentType] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    query = db.query(Template).filter(Template.user_id == user_id)
    if content_type:
        query = query.filter(Template.content_type == content_type)
    templates = query.offset(skip).limit(limit).all()
    return templates

@app.post("/upload/")
async def upload_file(
    file: UploadFile = File(...),
    content_type: ContentType = None,
    user_id: int = None
):
    # Implementation for file upload and processing
    return {"filename": file.filename}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "content-service"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 
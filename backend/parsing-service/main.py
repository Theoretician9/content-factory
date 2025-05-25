from fastapi import FastAPI, HTTPException, Depends, status, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, JSON, ForeignKey, Text, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from pydantic import BaseModel, HttpUrl
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import enum
import os
from dotenv import load_dotenv
import aiohttp
import json
import asyncio
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
from playwright.async_api import async_playwright
import logging

load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация базы данных
DATABASE_URL = os.getenv("DATABASE_URL", "mysql://telegraminvi:szkTgBhWh6XU@db:3306/telegraminvi")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Enums
class ParserType(str, enum.Enum):
    WEB = "web"
    API = "api"
    FILE = "file"
    DATABASE = "database"

class ParserStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class DataFormat(str, enum.Enum):
    JSON = "json"
    CSV = "csv"
    XML = "xml"
    HTML = "html"
    TEXT = "text"

# Database Models
class Parser(Base):
    __tablename__ = "parsers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    name = Column(String(255))
    description = Column(Text, nullable=True)
    parser_type = Column(Enum(ParserType))
    source_url = Column(String(2048), nullable=True)
    config = Column(JSON)  # Параметры парсера
    status = Column(Enum(ParserStatus), default=ParserStatus.PENDING)
    last_run = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    results = relationship("ParserResult", back_populates="parser")

class ParserResult(Base):
    __tablename__ = "parser_results"

    id = Column(Integer, primary_key=True, index=True)
    parser_id = Column(Integer, ForeignKey("parsers.id"))
    data = Column(JSON)  # Результаты парсинга
    format = Column(Enum(DataFormat))
    metadata = Column(JSON)  # Дополнительная информация
    created_at = Column(DateTime, default=datetime.utcnow)

    parser = relationship("Parser", back_populates="results")

# Pydantic models
class ParserBase(BaseModel):
    name: str
    description: Optional[str] = None
    parser_type: ParserType
    source_url: Optional[str] = None
    config: Dict[str, Any]

class ParserCreate(ParserBase):
    pass

class Parser(ParserBase):
    id: int
    user_id: int
    status: ParserStatus
    last_run: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    results: List["ParserResult"]

    class Config:
        from_attributes = True

class ParserResultBase(BaseModel):
    data: Dict[str, Any]
    format: DataFormat
    metadata: Optional[Dict[str, Any]] = None

class ParserResultCreate(ParserResultBase):
    pass

class ParserResult(ParserResultBase):
    id: int
    parser_id: int
    created_at: datetime

    class Config:
        from_attributes = True

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Parsing Service",
    description="Service for data parsing and collection",
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
async def parse_web_page(url: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Parse web page using Playwright."""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        try:
            await page.goto(url)
            await page.wait_for_load_state("networkidle")
            
            # Extract data based on config
            data = {}
            for selector, field in config.get("selectors", {}).items():
                element = await page.query_selector(selector)
                if element:
                    data[field] = await element.text_content()
            
            return data
        
        finally:
            await browser.close()

async def parse_api(url: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Parse data from API."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=config.get("headers", {})) as response:
            if response.status != 200:
                raise HTTPException(status_code=response.status, detail="API request failed")
            
            data = await response.json()
            return data

def parse_file(file_path: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Parse data from file."""
    if file_path.endswith('.csv'):
        df = pd.read_csv(file_path)
    elif file_path.endswith('.json'):
        with open(file_path, 'r') as f:
            data = json.load(f)
        return data
    else:
        raise ValueError("Unsupported file format")
    
    return df.to_dict(orient='records')

# Background tasks
async def run_parser(parser_id: int, db: Session):
    """Run parser in background."""
    parser = db.query(Parser).filter(Parser.id == parser_id).first()
    if not parser:
        return
    
    try:
        parser.status = ParserStatus.RUNNING
        db.commit()
        
        # Run parser based on type
        if parser.parser_type == ParserType.WEB:
            data = await parse_web_page(parser.source_url, parser.config)
        elif parser.parser_type == ParserType.API:
            data = await parse_api(parser.source_url, parser.config)
        elif parser.parser_type == ParserType.FILE:
            data = parse_file(parser.config.get("file_path"), parser.config)
        else:
            raise ValueError(f"Unsupported parser type: {parser.parser_type}")
        
        # Save results
        result = ParserResult(
            parser_id=parser_id,
            data=data,
            format=DataFormat.JSON,
            metadata={"status": "success"}
        )
        db.add(result)
        
        parser.status = ParserStatus.COMPLETED
        parser.last_run = datetime.utcnow()
        db.commit()
        
    except Exception as e:
        logger.error(f"Parser {parser_id} failed: {str(e)}")
        parser.status = ParserStatus.FAILED
        db.commit()
        
        # Save error result
        result = ParserResult(
            parser_id=parser_id,
            data={"error": str(e)},
            format=DataFormat.JSON,
            metadata={"status": "error"}
        )
        db.add(result)
        db.commit()

# Endpoints
@app.post("/parsers/", response_model=Parser)
async def create_parser(
    parser: ParserCreate,
    user_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    db_parser = Parser(**parser.dict(), user_id=user_id)
    db.add(db_parser)
    db.commit()
    db.refresh(db_parser)
    
    # Run parser in background
    background_tasks.add_task(run_parser, db_parser.id, db)
    
    return db_parser

@app.get("/parsers/", response_model=List[Parser])
def get_parsers(
    user_id: int,
    status: Optional[ParserStatus] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    query = db.query(Parser).filter(Parser.user_id == user_id)
    if status:
        query = query.filter(Parser.status == status)
    parsers = query.offset(skip).limit(limit).all()
    return parsers

@app.get("/parsers/{parser_id}", response_model=Parser)
def get_parser(parser_id: int, db: Session = Depends(get_db)):
    parser = db.query(Parser).filter(Parser.id == parser_id).first()
    if not parser:
        raise HTTPException(status_code=404, detail="Parser not found")
    return parser

@app.get("/parsers/{parser_id}/results", response_model=List[ParserResult])
def get_parser_results(
    parser_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    results = db.query(ParserResult).filter(
        ParserResult.parser_id == parser_id
    ).offset(skip).limit(limit).all()
    return results

@app.post("/parsers/{parser_id}/run")
async def run_parser_endpoint(
    parser_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    parser = db.query(Parser).filter(Parser.id == parser_id).first()
    if not parser:
        raise HTTPException(status_code=404, detail="Parser not found")
    
    if parser.status == ParserStatus.RUNNING:
        raise HTTPException(status_code=400, detail="Parser is already running")
    
    background_tasks.add_task(run_parser, parser_id, db)
    return {"status": "started"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "parsing-service"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 
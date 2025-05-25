from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, JSON, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List, Dict, Any
import enum
import os
from dotenv import load_dotenv
import networkx as nx
import json

load_dotenv()

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "mysql://telegraminvi:szkTgBhWh6XU@db:3306/telegraminvi")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Enums
class ScenarioStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"

class NodeType(str, enum.Enum):
    START = "start"
    MESSAGE = "message"
    CONDITION = "condition"
    DELAY = "delay"
    ACTION = "action"
    END = "end"

# Database Models
class Funnel(Base):
    __tablename__ = "funnels"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    name = Column(String(255))
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    scenarios = relationship("Scenario", back_populates="funnel")

class Scenario(Base):
    __tablename__ = "scenarios"

    id = Column(Integer, primary_key=True, index=True)
    funnel_id = Column(Integer, ForeignKey("funnels.id"))
    name = Column(String(255))
    description = Column(Text)
    status = Column(String(20), default=ScenarioStatus.DRAFT)
    graph_data = Column(JSON)  # Stores the graph structure
    settings = Column(JSON)  # Additional settings
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    funnel = relationship("Funnel", back_populates="scenarios")
    nodes = relationship("Node", back_populates="scenario")
    edges = relationship("Edge", back_populates="scenario")

class Node(Base):
    __tablename__ = "nodes"

    id = Column(Integer, primary_key=True, index=True)
    scenario_id = Column(Integer, ForeignKey("scenarios.id"))
    node_type = Column(String(20))
    name = Column(String(255))
    config = Column(JSON)  # Node-specific configuration
    position_x = Column(Integer)
    position_y = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    scenario = relationship("Scenario", back_populates="nodes")
    outgoing_edges = relationship("Edge", back_populates="source_node", foreign_keys="Edge.source_node_id")
    incoming_edges = relationship("Edge", back_populates="target_node", foreign_keys="Edge.target_node_id")

class Edge(Base):
    __tablename__ = "edges"

    id = Column(Integer, primary_key=True, index=True)
    scenario_id = Column(Integer, ForeignKey("scenarios.id"))
    source_node_id = Column(Integer, ForeignKey("nodes.id"))
    target_node_id = Column(Integer, ForeignKey("nodes.id"))
    condition = Column(JSON, nullable=True)  # Condition for conditional edges
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    scenario = relationship("Scenario", back_populates="edges")
    source_node = relationship("Node", foreign_keys=[source_node_id], back_populates="outgoing_edges")
    target_node = relationship("Node", foreign_keys=[target_node_id], back_populates="incoming_edges")

# Pydantic models
class FunnelBase(BaseModel):
    name: str
    description: Optional[str] = None

class FunnelCreate(FunnelBase):
    pass

class Funnel(FunnelBase):
    id: int
    user_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class NodeBase(BaseModel):
    node_type: NodeType
    name: str
    config: Dict[str, Any]
    position_x: int
    position_y: int

class NodeCreate(NodeBase):
    pass

class Node(NodeBase):
    id: int
    scenario_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class EdgeBase(BaseModel):
    source_node_id: int
    target_node_id: int
    condition: Optional[Dict[str, Any]] = None

class EdgeCreate(EdgeBase):
    pass

class Edge(EdgeBase):
    id: int
    scenario_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ScenarioBase(BaseModel):
    name: str
    description: Optional[str] = None
    status: ScenarioStatus
    settings: Optional[Dict[str, Any]] = None

class ScenarioCreate(ScenarioBase):
    funnel_id: int

class Scenario(ScenarioBase):
    id: int
    funnel_id: int
    graph_data: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    nodes: List[Node]
    edges: List[Edge]

    class Config:
        from_attributes = True

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Scenario Service",
    description="Funnel and scenario management service for Content Factory",
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
def validate_graph(nodes: List[Node], edges: List[Edge]) -> bool:
    """Validate the scenario graph structure."""
    G = nx.DiGraph()
    
    # Add nodes
    for node in nodes:
        G.add_node(node.id)
    
    # Add edges
    for edge in edges:
        G.add_edge(edge.source_node_id, edge.target_node_id)
    
    # Check for cycles
    if not nx.is_directed_acyclic_graph(G):
        return False
    
    # Check for isolated nodes
    if not nx.is_weakly_connected(G):
        return False
    
    return True

# Endpoints
@app.post("/funnels/", response_model=Funnel)
def create_funnel(funnel: FunnelCreate, user_id: int, db: Session = Depends(get_db)):
    db_funnel = Funnel(**funnel.dict(), user_id=user_id)
    db.add(db_funnel)
    db.commit()
    db.refresh(db_funnel)
    return db_funnel

@app.get("/funnels/", response_model=List[Funnel])
def get_funnels(user_id: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    funnels = db.query(Funnel).filter(Funnel.user_id == user_id).offset(skip).limit(limit).all()
    return funnels

@app.post("/scenarios/", response_model=Scenario)
def create_scenario(scenario: ScenarioCreate, db: Session = Depends(get_db)):
    db_scenario = Scenario(**scenario.dict())
    db.add(db_scenario)
    db.commit()
    db.refresh(db_scenario)
    return db_scenario

@app.get("/scenarios/{scenario_id}", response_model=Scenario)
def get_scenario(scenario_id: int, db: Session = Depends(get_db)):
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return scenario

@app.post("/scenarios/{scenario_id}/nodes/", response_model=Node)
def create_node(scenario_id: int, node: NodeCreate, db: Session = Depends(get_db)):
    db_node = Node(**node.dict(), scenario_id=scenario_id)
    db.add(db_node)
    db.commit()
    db.refresh(db_node)
    return db_node

@app.post("/scenarios/{scenario_id}/edges/", response_model=Edge)
def create_edge(scenario_id: int, edge: EdgeCreate, db: Session = Depends(get_db)):
    # Validate that both nodes exist and belong to the scenario
    source_node = db.query(Node).filter(Node.id == edge.source_node_id, Node.scenario_id == scenario_id).first()
    target_node = db.query(Node).filter(Node.id == edge.target_node_id, Node.scenario_id == scenario_id).first()
    
    if not source_node or not target_node:
        raise HTTPException(status_code=400, detail="Invalid node IDs")
    
    # Create the edge
    db_edge = Edge(**edge.dict(), scenario_id=scenario_id)
    db.add(db_edge)
    
    # Validate the graph
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not validate_graph(scenario.nodes, scenario.edges + [db_edge]):
        db.rollback()
        raise HTTPException(status_code=400, detail="Invalid graph structure")
    
    db.commit()
    db.refresh(db_edge)
    return db_edge

@app.put("/scenarios/{scenario_id}/status/")
def update_scenario_status(scenario_id: int, status: ScenarioStatus, db: Session = Depends(get_db)):
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    
    scenario.status = status
    db.commit()
    return {"status": "success"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "scenario-service"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 
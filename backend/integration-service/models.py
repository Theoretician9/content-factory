from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
from .main import IntegrationType, IntegrationStatus

class IntegrationBase(BaseModel):
    name: str
    description: Optional[str] = None
    integration_type: IntegrationType
    credentials: Dict[str, Any]
    config: Optional[Dict[str, Any]] = None

    model_config = {
        "arbitrary_types_allowed": True,
        "from_attributes": True
    }

class IntegrationCreate(IntegrationBase):
    pass

class IntegrationResponse(IntegrationBase):
    id: int
    user_id: int
    status: IntegrationStatus
    last_sync: Optional[datetime]
    created_at: datetime
    updated_at: datetime

class IntegrationEventBase(BaseModel):
    event_type: str
    event_data: Dict[str, Any]

    model_config = {
        "arbitrary_types_allowed": True,
        "from_attributes": True
    }

class IntegrationEventCreate(IntegrationEventBase):
    pass

class IntegrationEventResponse(IntegrationEventBase):
    id: int
    integration_id: int
    created_at: datetime 
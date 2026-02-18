from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from uuid import UUID
from typing import Optional, List
from app.utils.validators import sanitize_string


class ProjectBase(BaseModel):
    """Base schema for Project."""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    
    @field_validator('name', 'description')
    @classmethod
    def sanitize_fields(cls, v):
        if v is not None and isinstance(v, str):
            return sanitize_string(v)
        return v


class ProjectCreate(ProjectBase):
    """Schema for creating a new project."""
    pass


class ProjectUpdate(BaseModel):
    """Schema for updating project information."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    
    @field_validator('name', 'description')
    @classmethod
    def sanitize_fields(cls, v):
        if v is not None and isinstance(v, str):
            return sanitize_string(v)
        return v


class ProjectResponse(ProjectBase):
    """Schema for project response."""
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}


from app.schemas.patent import PatentResponse

class ProjectWithPatents(ProjectResponse):
    """Schema for project response with related patents."""
    patents: List[PatentResponse] = []

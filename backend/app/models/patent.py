from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
from uuid import uuid4
from app.database import Base

# Try to import pgvector's Vector type; fall back to Text if not available
try:
    from pgvector.sqlalchemy import Vector
    _VECTOR_TYPE = Vector(384)
    PGVECTOR_AVAILABLE = True
except Exception:
    # pgvector not installed or extension unavailable — store embeddings as JSON text
    _VECTOR_TYPE = Text
    PGVECTOR_AVAILABLE = False


class Patent(Base):
    """Patent model for storing patent information and embeddings."""

    __tablename__ = "patents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4, index=True)
    patent_number = Column(String, unique=True, index=True, nullable=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    content = Column(Text, nullable=False)
    filing_date = Column(DateTime, nullable=True)

    # Vector embedding for similarity search.
    # Uses VECTOR(384) when pgvector is available, falls back to Text otherwise.
    embedding = Column(_VECTOR_TYPE, nullable=True)

    # Foreign Keys
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    project = relationship("Project", back_populates="patents")

    def __repr__(self):
        return f"<Patent {self.patent_number or self.title}>"

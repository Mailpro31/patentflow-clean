"""Pydantic schemas pour la génération IA de documents de brevet."""

from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, List
from uuid import UUID
from app.models.generation_mode import GenerationMode


class PatentGenerationRequest(BaseModel):
    """Requête de génération de document de brevet."""
    idea_description: str = Field(
        ...,
        min_length=50,
        max_length=5000,
        description="Description de l'idée d'invention"
    )
    technical_details: Optional[str] = Field(
        None,
        max_length=10000,
        description="Détails techniques supplémentaires"
    )
    mode: GenerationMode = Field(
        default=GenerationMode.TECHNIQUE,
        description="Mode de génération"
    )
    language: str = Field(
        default="fr",
        pattern="^(fr|en)$",
        description="Langue du document (fr ou en)"
    )
    include_diagrams: bool = Field(
        default=False,
        description="Inclure des suggestions de diagrammes"
    )
    project_id: Optional[UUID] = Field(
        None,
        description="ID du projet auquel rattacher le document"
    )
    auto_lint: bool = Field(
        default=True,
        description="Appliquer post-traitement automatique"
    )


class ValidationIssue(BaseModel):
    """Issue de validation détectée."""
    section: str
    severity: str  # "error", "warning", "info"
    message: str
    suggestion: Optional[str] = None


class QualityScoreResponse(BaseModel):
    """Score de qualité du document."""
    overall_score: int = Field(..., ge=0, le=100)
    keyword_score: int = Field(..., ge=0, le=100)
    language_score: int = Field(..., ge=0, le=100)
    structure_score: int = Field(..., ge=0, le=100)
    technical_clarity_score: int = Field(..., ge=0, le=100)
    details: Dict


class PatentGenerationResponse(BaseModel):
    """Réponse de génération de document de brevet."""
    document_id: Optional[UUID] = None
    title: str
    abstract: str
    description: str
    claims: str
    quality_score: Optional[QualityScoreResponse] = None
    validation_warnings: List[ValidationIssue] = []
    modifications_applied: List[str] = []
    mode_used: str
    generation_time_ms: Optional[int] = None
    
    model_config = {"from_attributes": True}


class DocumentRefinementRequest(BaseModel):
    """Requête de raffinement de document existant."""
    document_id: UUID
    refinement_instructions: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Instructions de raffinement"
    )


class SectionGenerationRequest(BaseModel):
    """Requête de génération d'une section spécifique."""
    section_type: str = Field(
        ...,
        pattern="^(description|claims|abstract)$",
        description="Type de section à générer"
    )
    context: str = Field(
        ...,
        min_length=20,
        max_length=5000,
        description="Contexte pour la génération"
    )
    mode: GenerationMode = Field(
        default=GenerationMode.TECHNIQUE,
        description="Mode de génération"
    )


class DocumentValidationRequest(BaseModel):
    """Requête de validation de document."""
    title: str
    abstract: str
    description: str
    claims: str


class ModeInfo(BaseModel):
    """Information sur un mode de génération."""
    mode: str
    name: str
    description: str
    temperature: float
    use_cases: List[str]


class ModesListResponse(BaseModel):
    """Liste des modes disponibles."""
    modes: List[ModeInfo]

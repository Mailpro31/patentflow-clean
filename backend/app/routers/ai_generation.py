"""API endpoints pour la génération IA de documents de brevet."""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
import time
import logging
from typing import Dict
from uuid import UUID

from app.database import get_db
from app.schemas.ai_generation import (
    PatentGenerationRequest,
    PatentGenerationResponse,
    DocumentValidationRequest,
    DocumentRefinementRequest,
    SectionGenerationRequest,
    ModesListResponse,
    ModeInfo,
    QualityScoreResponse,
    ValidationIssue
)
from app.services.ai_writer_service import ai_writer
from app.services.text_linter import patent_linter, PatentSection
from app.models.generation_mode import GenerationMode
from app.services.prompts.patent_engineer_prompts import MODE_CONFIGS
from app.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai", tags=["AI Generation"])


@router.post("/generate", response_model=PatentGenerationResponse)
async def generate_patent_document(
    request: PatentGenerationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Génère un document de brevet complet à partir d'une idée.
    
    **Mode LARGE**: Protection juridique maximale avec revendications larges
    **Mode TECHNIQUE**: Documentation technique complète et détaillée  
    **Mode INPI_COMPLIANCE**: Conformité stricte au format INPI français
    """
    try:
        start_time = time.time()
        
        logger.info(
            f"User {current_user['id']} generating patent in {request.mode.value} mode"
        )
        
        # Générer le document
        result = await ai_writer.generate_patent_document(
            idea_description=request.idea_description,
            technical_details=request.technical_details,
            mode=request.mode,
            language=request.language,
            auto_lint=request.auto_lint
        )
        
        generation_time = int((time.time() - start_time) * 1000)
        
        # Convertir validations en warnings
        warnings = []
        if request.auto_lint and result.get('validations'):
            for section_name, validation in result['validations'].items():
                if hasattr(validation, 'issues'):
                    for issue in validation.issues:
                        warnings.append(ValidationIssue(
                            section=section_name,
                            severity="warning",
                            message=issue,
                            suggestion=None
                        ))
        
        # Convertir quality_score
        quality_score_response = None
        if result.get('quality_score'):
            qs = result['quality_score']
            quality_score_response = QualityScoreResponse(
                overall_score=qs.overall_score,
                keyword_score=qs.keyword_score,
                language_score=qs.language_score,
                structure_score=qs.structure_score,
                technical_clarity_score=qs.technical_clarity_score,
                details=qs.details
            )
        
        return PatentGenerationResponse(
            title=result['title'],
            abstract=result['abstract'],
            description=result['description'],
            claims=result['claims'],
            quality_score=quality_score_response,
            validation_warnings=warnings,
            modifications_applied=result.get('modifications', []),
            mode_used=result['mode_used'],
            generation_time_ms=generation_time
        )
        
    except Exception as e:
        logger.error(f"Error generating patent: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate", response_model=Dict)
async def validate_patent_document(
    request: DocumentValidationRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Valide un document de brevet sans le modifier.
    Retourne score de qualité, mots-clés manquants, et suggestions.
    """
    try:
        # Exécuter linter sans auto-fix
        lint_result = patent_linter.lint_document(
            title=request.title,
            abstract=request.abstract,
            description=request.description,
            claims=request.claims,
            auto_fix=False
        )
        
        # Extraire issues et suggestions
        all_issues = []
        all_suggestions = []
        
        for section_name, validation in lint_result['validations'].items():
            if hasattr(validation, 'issues'):
                all_issues.extend([
                    {
                        'section': section_name,
                        'message': issue
                    }
                    for issue in validation.issues
                ])
            if hasattr(validation, 'suggestions'):
                all_suggestions.extend([
                    {
                        'section': section_name,
                        'suggestion': sug
                    }
                    for sug in validation.suggestions
                ])
        
        # Trouver adjectifs non-techniques
        full_text = f"{request.title} {request.abstract} {request.description} {request.claims}"
        non_tech_adjs = patent_linter.find_non_technical_adjectives(full_text)
        
        qs = lint_result['quality_score']
        
        return {
            'quality_score': {
                'overall_score': qs.overall_score,
                'keyword_score': qs.keyword_score,
                'language_score': qs.language_score,
                'structure_score': qs.structure_score,
                'technical_clarity_score': qs.technical_clarity_score,
                'details': qs.details
            },
            'issues': all_issues,
            'suggestions': all_suggestions,
            'non_technical_adjectives': [
                {'word': adj, 'position': pos}
                for adj, pos in non_tech_adjs
            ],
            'is_valid': len(all_issues) == 0
        }
        
    except Exception as e:
        logger.error(f"Error validating document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refine")
async def refine_patent_document(
    request: DocumentRefinementRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Raffine un document de brevet existant selon des instructions.
    Applique le linter après raffinement.
    """
    try:
        # TODO: Récupérer le document depuis la DB
        # Pour l'instant, on suppose qu'il est fourni dans la requête
        
        raise HTTPException(
            status_code=501,
            detail="Document refinement not yet implemented. Provide document in request."
        )
        
    except Exception as e:
        logger.error(f"Error refining document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate/section")
async def generate_section(
    request: SectionGenerationRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Génère une section spécifique du brevet (description, claims, abstract).
    Utile pour régénérer une partie sans refaire tout le document.
    """
    try:
        section_text = await ai_writer.generate_section(
            section_type=request.section_type,
            context=request.context,
            mode=request.mode
        )
        
        return {
            'section_type': request.section_type,
            'content': section_text,
            'mode_used': request.mode.value
        }
        
    except Exception as e:
        logger.error(f"Error generating section: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/modes", response_model=ModesListResponse)
async def list_generation_modes():
    """
    Liste tous les modes de génération disponibles avec leurs descriptions.
    """
    modes = []
    
    for mode, config in MODE_CONFIGS.items():
        use_cases = []
        
        if mode == GenerationMode.LARGE:
            use_cases = [
                "Protection juridique maximale",
                "Couvrir toutes les variantes possibles",
                "Revendications larges et génériques",
                "Dépôt initial avec scope maximum"
            ]
        elif mode == GenerationMode.TECHNIQUE:
            use_cases = [
                "Documentation technique complète",
                "Détails d'implémentation précis",
                "Description reproductible",
                "Paramètres et algorithmes détaillés"
            ]
        elif mode == GenerationMode.INPI_COMPLIANCE:
            use_cases = [
                "Dépôt INPI français",
                "Format strictement conforme",
                "Numérotation [0001]...",
                "Prêt pour soumission officielle"
            ]
        
        modes.append(ModeInfo(
            mode=mode.value,
            name=mode.value.replace('_', ' ').title(),
            description=config['description'],
            temperature=config['temperature'],
            use_cases=use_cases
        ))
    
    return ModesListResponse(modes=modes)


@router.get("/health")
async def health_check():
    """Vérifie que le service de génération IA est opérationnel."""
    try:
        # Vérifier que Gemini est configuré
        if not ai_writer.api_key:
            return {
                'status': 'warning',
                'message': 'Gemini API key not configured',
                'gemini_configured': False
            }
        
        return {
            'status': 'ok',
            'message': 'AI generation service ready',
            'gemini_configured': True,
            'available_modes': list(MODE_CONFIGS.keys())
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            'status': 'error',
            'message': str(e),
            'gemini_configured': False
        }

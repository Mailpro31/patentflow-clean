"""
Endpoints API pour génération de schémas techniques.
SDXL + ControlNet → Potrace → SAM2 → Annotation.
"""

import logging
import base64
import io
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.image_processing import (
    DiagramGenerationRequest,
    DiagramGenerationResponse,
    VectorizationRequest,
    VectorizationResponse,
    AnnotationRequest,
    AnnotationResponse,
    DiagramTypesResponse,
    DiagramTypeInfo
)
from app.services.diagram_pipeline_service import diagram_pipeline
from app.services.image_generator_service import TECHNICAL_DIAGRAM_PROMPTS
from app.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/diagrams",
    tags=["Diagram Generation"]
)


@router.post(
    "/generate",
    response_model=DiagramGenerationResponse,
    status_code=status.HTTP_200_OK
)
async def generate_diagram(
    request: DiagramGenerationRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Génère un schéma technique annoté depuis un croquis.
    
    Pipeline complet:
    1. SDXL + ControlNet Line Art (sketch → technical diagram)
    2. Potrace vectorization (PNG → SVG)
    3. SAM2 component detection
    4. Automatic numeric labeling (10, 20, 30...)
    
    **Supports:**
    - Replicate API (SDXL)
    - Stability AI API
    - Automatic component detection (SAM2 or OpenCV fallback)
    - Leader lines between labels and components
    """
    try:
        logger.info(
            f"Generate diagram request from user {current_user.get('id')} "
            f"type={request.diagram_type}"
        )
        
        # Decode base64 sketch image
        try:
            sketch_bytes = base64.b64decode(request.sketch_image)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid base64 image: {str(e)}"
            )
        
        # Process through pipeline
        result = await diagram_pipeline.process_sketch(
            sketch_bytes=sketch_bytes,
            diagram_type=request.diagram_type,
            auto_annotate=request.auto_annotate,
            start_number=request.start_number,
            number_increment=request.number_increment,
            controlnet_strength=request.controlnet_strength,
            add_leader_lines=request.add_leader_lines,
            custom_prompt=request.custom_prompt
        )
        
        # Encode diagram image to base64 for response
        diagram_b64 = base64.b64encode(result['diagram_image']).decode('utf-8')
        diagram_url = f"data:image/png;base64,{diagram_b64}"
        
        # TODO: Save to database and file storage
        # For now, return inline
        
        response = DiagramGenerationResponse(
            diagram_id=None,  # TODO: Generate and save
            svg_content=result['svg_content'],
            diagram_image_url=diagram_url,
            components=result['components'],
            labels=result['labels'],
            processing_time_ms=result['processing_time_ms'],
            auto_annotated=result['auto_annotated'],
            quality_metrics=result.get('quality_metrics', {})
        )
        
        logger.info(
            f"Diagram generated successfully: "
            f"{len(result['components'])} components, "
            f"{len(result['labels'])} labels"
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating diagram: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Diagram generation failed: {str(e)}"
        )


@router.post(
    "/vectorize",
    response_model=VectorizationResponse,
    status_code=status.HTTP_200_OK
)
async def vectorize_image(
    request: VectorizationRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Convertit une image bitmap en SVG vectorisé.
    
    Utilise Potrace pour tracer les contours et générer des paths SVG.
    Pas de génération SDXL ni d'annotation.
    """
    try:
        logger.info("Vectorization request")
        
        # Decode base64 image
        try:
            image_bytes = base64.b64decode(request.image)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid base64 image: {str(e)}"
            )
        
        # Vectorize
        svg_content = await diagram_pipeline.vectorize_only(
            image_bytes=image_bytes,
            threshold=request.threshold,
            optimize=request.optimize
        )
        
        return VectorizationResponse(
            svg_content=svg_content,
            optimization_applied=request.optimize
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error vectorizing image: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Vectorization failed: {str(e)}"
        )


@router.post(
    "/annotate",
    response_model=AnnotationResponse,
    status_code=status.HTTP_200_OK
)
async def annotate_svg(
    request: AnnotationRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Ajoute annotations automatiques à un SVG existant.
    
    Utilise une image de référence pour détecter les composants (SAM2),
    puis place des labels numérotés sur le SVG.
    """
    try:
        logger.info("Annotation request")
        
        # Decode reference image
        try:
            reference_bytes = base64.b64decode(request.reference_image)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid base64 reference image: {str(e)}"
            )
        
        # Annotate
        result = await diagram_pipeline.annotate_existing_svg(
            svg_content=request.svg_content,
            reference_image=reference_bytes,
            start_number=request.start_number,
            number_increment=request.number_increment,
            add_leader_lines=request.add_leader_lines
        )
        
        return AnnotationResponse(
            svg_content=result['svg_content'],
            labels=result['labels'],
            num_components=result['num_components']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error annotating SVG: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Annotation failed: {str(e)}"
        )


@router.post(
    "/upload",
    status_code=status.HTTP_200_OK
)
async def upload_sketch(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Upload un fichier image (alternative à base64).
    Retourne l'image encodée en base64 pour utiliser avec /generate.
    """
    try:
        # Validate file type
        if not file.content_type.startswith('image/'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be an image"
            )
        
        # Read file
        contents = await file.read()
        
        # Encode to base64
        b64_image = base64.b64encode(contents).decode('utf-8')
        
        return {
            "filename": file.filename,
            "content_type": file.content_type,
            "size_bytes": len(contents),
            "base64_image": b64_image
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}"
        )


@router.get(
    "/types",
    response_model=DiagramTypesResponse,
    status_code=status.HTTP_200_OK
)
async def get_diagram_types():
    """
    Liste tous les types de schémas disponibles.
    Retourne les prompts optimisés pour chaque type.
    """
    types = []
    
    type_descriptions = {
        "mechanical": {
            "name": "Mechanical",
            "description": "Schémas mécaniques (machines, mécanismes, pièces)",
            "use_cases": [
                "Machines et mécanismes",
                "Pièces mécaniques",
                "Assemblages",
                "Systèmes de transmission"
            ]
        },
        "electrical": {
            "name": "Electrical",
            "description": "Circuits et schémas électriques/électroniques",
            "use_cases": [
                "Circuits électroniques",
                "Schémas de câblage",
                "Diagrammes de circuits",
                "Systèmes électriques"
            ]
        },
        "chemical": {
            "name": "Chemical",
            "description": "Procédés chimiques et industriels",
            "use_cases": [
                "Procédés chimiques",
                "Diagrammes de flux",
                "Équipements industriels",
                "Systèmes de traitement"
            ]
        },
        "software": {
            "name": "Software",
            "description": "Architectures logicielles et systèmes",
            "use_cases": [
                "Architectures logicielles",
                "Diagrammes UML",
                "Systèmes informatiques",
                "Flux de données"
            ]
        },
        "generic": {
            "name": "Generic",
            "description": "Schéma technique générique",
            "use_cases": [
                "Schémas techniques généraux",
                "Illustrations de brevets",
                "Diagrammes personnalisés"
            ]
        }
    }
    
    for diagram_type, prompt in TECHNICAL_DIAGRAM_PROMPTS.items():
        info = type_descriptions.get(diagram_type, {})
        
        types.append(DiagramTypeInfo(
            type=diagram_type,
            name=info.get("name", diagram_type.capitalize()),
            description=info.get("description", ""),
            optimal_use_cases=info.get("use_cases", []),
            example_prompt=prompt
        ))
    
    return DiagramTypesResponse(types=types)


@router.get(
    "/health",
    status_code=status.HTTP_200_OK
)
async def health_check():
    """
    Vérifie l'état du service de génération de schémas.
    """
    from app.config import settings
    
    return {
        "status": "ok",
        "message": "Diagram generation service ready",
        "provider": settings.SD_API_PROVIDER,
        "replicate_configured": bool(settings.REPLICATE_API_KEY),
        "stability_ai_configured": bool(settings.STABILITY_AI_API_KEY),
        "available_types": list(TECHNICAL_DIAGRAM_PROMPTS.keys())
    }

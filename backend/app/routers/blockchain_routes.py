"""
Routes API pour blockchain et preuves d'antériorité.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.transactional import (
    AnchorRequest,
    AnchorResponse,
    AnchorVerificationResponse
)
from app.services.blockchain_service import blockchain_service
from app.models.project import Project
from sqlalchemy import select

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/blockchain",
    tags=["Blockchain"]
)


@router.post(
    "/anchor",
    response_model=AnchorResponse,
    status_code=status.HTTP_200_OK
)
async def anchor_document(
    request: AnchorRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Ancre un document sur la blockchain Bitcoin.
    
    **Requires**: Le projet doit être payé.
    """
    # Verify project exists and is paid
    result = await db.execute(
        select(Project).where(Project.id == request.project_id)
    )
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if project.payment_status != 'paid':
        raise HTTPException(
            status_code=403,
            detail="Payment required to anchor document"
        )
    
    try:
        anchor_result = await blockchain_service.anchor_document(
            project_id=request.project_id,
            document_content=request.document_content,
            db=db
        )
        
        return AnchorResponse(**anchor_result)
        
    except Exception as e:
        logger.error(f"Error anchoring document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/verify/{anchor_id}",
    response_model=AnchorVerificationResponse,
    status_code=status.HTTP_200_OK
)
async def verify_anchor(
    anchor_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Vérifie le statut d'un ancrage blockchain.
    
    Retourne le statut, transaction Bitcoin, et lien de preuve.
    """
    try:
        verification = await blockchain_service.verify_anchor(
            anchor_id=anchor_id,
            db=db
        )
        
        return AnchorVerificationResponse(**verification)
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error verifying anchor: {e}")
        raise HTTPException(status_code=500, detail="Verification failed")


@router.get(
    "/certificate/{anchor_id}",
    status_code=status.HTTP_200_OK
)
async def download_certificate(
    anchor_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Télécharge le certificat PDF de preuve d'antériorité.
    
    **Requires**: L'ancrage doit être confirmé sur la blockchain.
    """
    try:
        pdf = await blockchain_service.generate_proof_certificate(
            anchor_id=anchor_id,
            db=db
        )
        
        return Response(
            content=pdf,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=proof_{anchor_id}.pdf"
            }
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating certificate: {e}")
        raise HTTPException(status_code=500, detail="Certificate generation failed")


@router.post(
    "/calculate-hash",
    status_code=status.HTTP_200_OK
)
async def calculate_hash(
    content: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Calcule le hash SHA-256 d'un contenu.
    
    Utile pour vérifier l'intégrité d'un document.
    """
    doc_hash = blockchain_service.calculate_hash(content)
    
    return {
        "hash": doc_hash,
        "algorithm": "SHA-256"
    }


@router.post(
    "/verify-hash",
    status_code=status.HTTP_200_OK
)
async def verify_hash(
    content: str,
    expected_hash: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Vérifie qu'un contenu correspond à un hash.
    """
    is_valid = blockchain_service.verify_hash(content, expected_hash)
    
    return {
        "valid": is_valid,
        "expected_hash": expected_hash,
        "actual_hash": blockchain_service.calculate_hash(content)
    }


@router.get(
    "/health",
    status_code=status.HTTP_200_OK
)
async def health_check():
    """
    Vérifie la santé du service blockchain.
    """
    from app.config import settings
    
    return {
        "status": "ok",
        "message": "Blockchain service ready",
        "woleet_configured": bool(settings.WOLEET_API_KEY),
        "api_url": settings.WOLEET_API_URL
    }

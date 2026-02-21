"""
Routes API pour paiements Stripe.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.transactional import (
    CheckoutRequest,
    CheckoutResponse,
    PaymentStatusResponse,
    PricingResponse
)
from app.services.stripe_service import stripe_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/payments",
    tags=["Payments"]
)


@router.post(
    "/create-checkout",
    response_model=CheckoutResponse,
    status_code=status.HTTP_200_OK
)
async def create_checkout_session(
    request: CheckoutRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Crée une session Stripe Checkout.
    
    Retourne l'URL de paiement Stripe avec Stripe Tax automatique.
    """
    try:
        session = await stripe_service.create_checkout_session(
            project_id=request.project_id,
            user_id=current_user['id'],
            user_email=current_user['email'],
            patent_type=request.patent_type,
            success_url=request.success_url,
            cancel_url=request.cancel_url
        )
        
        return CheckoutResponse(**session)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating checkout session: {e}")
        raise HTTPException(status_code=500, detail="Failed to create checkout session")


@router.post(
    "/webhook",
    status_code=status.HTTP_200_OK,
    include_in_schema=False  # Hide from docs (no auth)
)
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Webhook Stripe pour traiter les événements de paiement.
    
    **Important**: Endpoint public (pas d'authentification).
    Sécurité assurée par vérification de signature Stripe.
    """
    payload = await request.body()
    signature = request.headers.get('stripe-signature')
    
    if not signature:
        raise HTTPException(status_code=400, detail="Missing signature")
    
    try:
        result = await stripe_service.handle_webhook(
            payload=payload,
            signature=signature,
            db=db
        )
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")


@router.get(
    "/status/{project_id}",
    response_model=PaymentStatusResponse,
    status_code=status.HTTP_200_OK
)
async def get_payment_status(
    project_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Récupère le statut de paiement d'un projet.
    """
    payment_status = await stripe_service.get_payment_status(
        project_id=project_id,
        db=db
    )
    
    if not payment_status:
        return PaymentStatusResponse(status='unpaid')
    
    return PaymentStatusResponse(**payment_status)


@router.get(
    "/pricing",
    response_model=PricingResponse,
    status_code=status.HTTP_200_OK
)
async def get_pricing():
    """
    Retourne les informations de tarification.
    """
    pricing = stripe_service.get_pricing_info()
    return PricingResponse(**pricing)


@router.get(
    "/health",
    status_code=status.HTTP_200_OK
)
async def health_check():
    """
    Vérifie la santé du service de paiement.
    """
    from app.config import settings
    
    return {
        "status": "ok",
        "message": "Payment service ready",
        "stripe_configured": bool(settings.STRIPE_API_KEY),
        "tax_enabled": settings.STRIPE_TAX_ENABLED
    }

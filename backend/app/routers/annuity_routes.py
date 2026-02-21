"""
Routes API pour annuités INPI.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.transactional import (
    AnnuityScheduleResponse,
    AnnuityCostsResponse,
    UpcomingPaymentsResponse,
    AnnuityRatesResponse,
    AnnuityRate
)
from app.services.inpi_calculator_service import inpi_calculator
from app.models.project import Project
from sqlalchemy import select

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/annuities",
    tags=["INPI Annuities"]
)


@router.get(
    "/schedule/{project_id}",
    response_model=AnnuityScheduleResponse,
    status_code=status.HTTP_200_OK
)
async def get_annuity_schedule(
    project_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retourne le calendrier complet des annuités INPI (20 ans).
    """
    # Get project
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if not project.filing_date:
        raise HTTPException(
            status_code=400,
            detail="Project must have a filing date"
        )
    
    schedule = inpi_calculator.calculate_annuity_schedule(
        filing_date=project.filing_date,
        include_late_fees=False
    )
    
    return AnnuityScheduleResponse(
        project_id=project_id,
        filing_date=project.filing_date,
        schedule=schedule
    )


@router.get(
    "/costs",
    response_model=AnnuityCostsResponse,
    status_code=status.HTTP_200_OK
)
async def get_total_costs(
    years: int = Query(default=20, ge=1, le=20, description="Number of years")
):
    """
    Calcule le coût total des annuités sur N années.
    
    Inclut:
    - Coût nominal total
    - Valeur actuelle nette (NPV)
    - Coûts cumulatifs par année
    """
    try:
        costs = inpi_calculator.calculate_total_costs(years=years)
        return AnnuityCostsResponse(**costs)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/upcoming/{project_id}",
    response_model=UpcomingPaymentsResponse,
    status_code=status.HTTP_200_OK
)
async def get_upcoming_payments(
    project_id: UUID,
    months_ahead: int = Query(default=6, ge=1, le=24, description="Months ahead"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retourne les paiements d'annuités à venir.
    
    Utilisé pour les rappels et notifications.
    """
    upcoming = await inpi_calculator.get_upcoming_payments(
        project_id=project_id,
        months_ahead=months_ahead,
        db=db
    )
    
    return UpcomingPaymentsResponse(upcoming_payments=upcoming)


@router.get(
    "/rates",
    response_model=AnnuityRatesResponse,
    status_code=status.HTTP_200_OK
)
async def get_rates_table():
    """
    Retourne le tableau complet des tarifs INPI officiels 2024.
    """
    rates = inpi_calculator.get_rates_table()
    
    return AnnuityRatesResponse(
        rates=[AnnuityRate(**rate) for rate in rates]
    )


@router.get(
    "/payment/{project_id}/{year}",
    status_code=status.HTTP_200_OK
)
async def get_payment_for_year(
    project_id: UUID,
    year: int = Query(..., ge=1, le=20, description="Year (1-20)"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retourne les détails d'un paiement pour une année spécifique.
    """
    # Get project
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    
    if not project or not project.filing_date:
        raise HTTPException(status_code=404, detail="Project not found")
    
    try:
        payment = inpi_calculator.get_payment_for_year(
            filing_date=project.filing_date,
            year=year
        )
        return payment
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/health",
    status_code=status.HTTP_200_OK
)
async def health_check():
    """
    Vérifie la santé du service d'annuités.
    """
    return {
        "status": "ok",
        "message": "INPI annuity service ready",
        "total_20_years": 11605,  # Official total
        "currency": "EUR"
    }

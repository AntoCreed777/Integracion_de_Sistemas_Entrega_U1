from fastapi import APIRouter, HTTPException, Depends, status, Query, Path
from datetime import datetime, timezone
from typing import List, Union
from sqlalchemy.orm import Session

from app.database import get_db
from app.bd_models import Client, Rental

from app.models import (
    RentalRequest,
    RentalResponse,
    BadRequestError,
    NotAuthorizedError,
    ForbiddenError,
    ConflictError,
    NotFoundError,
    ServiceUnavailableError,
    GatewayTimeoutError,
)

router = APIRouter(prefix='/v1/rentals', tags=['Rentals'])

@router.post(
    '',
    response_model=RentalResponse,
    status_code=201,
    responses={
        '400': {'model': BadRequestError},
        '401': {'model': NotAuthorizedError},
        '403': {'model': ForbiddenError},
        '404': {'model': NotFoundError},
        '409': {'model': ConflictError},
        '503': {'model': ServiceUnavailableError},
        '504': {'model': GatewayTimeoutError},
    }
)
def create_rental(rental_in: RentalRequest, db: Session = Depends(get_db)) -> RentalResponse:
    # 1. Verificar que el cliente exista
    client = db.query(Client).filter(Client.id == rental_in.clientId).first()
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "CLIENT_NOT_FOUND", "message": f"El cliente {rental_in.clientId} no existe."}
        )

    # 2. TODO (gRPC): Integración con el sistema de Equipos
    # - Llamar a Equipos para verificar stock de `rental_in.equipmentId`.
    # - Si no hay stock -> raise HTTPException(409, detail=...)
    # - Si gRPC falla -> raise HTTPException(503, detail=...) o 504.
    # - Si hay éxito, el servicio gRPC debe descontar/reservar la unidad.

    # 3. Guardar en la base de datos local
    db_rental = Rental(
        client_id=rental_in.clientId,
        equipment_id=rental_in.equipmentId,
        start_date=rental_in.startDate,
        end_date=rental_in.endDate,
        status="ACTIVE"
    )
    
    db.add(db_rental)
    db.commit()
    db.refresh(db_rental)
    
    return build_rental_response(db_rental)


@router.get(
    '',
    response_model=List[RentalResponse],
    responses={
        '400': {'model': BadRequestError},
        '401': {'model': NotAuthorizedError},
        '403': {'model': ForbiddenError},
    }
)
def get_all_rentals(
    limit: int = Query(20, ge=1, le=100, description="Límite de resultados"),
    offset: int = Query(0, ge=0, description="Desplazamiento para paginación"),
    db: Session = Depends(get_db)
) -> List[RentalResponse]:
    rentals = db.query(Rental).offset(offset).limit(limit).all()
    return [build_rental_response(r) for r in rentals]


@router.get(
    '/{rentalId}',
    response_model=RentalResponse,
    responses={
        '400': {'model': BadRequestError},
        '401': {'model': NotAuthorizedError},
        '403': {'model': ForbiddenError},
        '404': {'model': NotFoundError},
    }
)
def get_rental_by_id(
    rentalId: int = Path(..., ge=1, description="ID del arriendo"),
    db: Session = Depends(get_db)
) -> RentalResponse:
    rental = db.query(Rental).filter(Rental.id == rentalId).first()
    if not rental:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RENTAL_NOT_FOUND", "message": f"Arriendo {rentalId} no encontrado."}
        )
    return build_rental_response(rental)


@router.post(
    '/{rentalId}/cancel',
    response_model=RentalResponse,
    responses={
        '400': {'model': BadRequestError},
        '401': {'model': NotAuthorizedError},
        '403': {'model': ForbiddenError},
        '404': {'model': NotFoundError},
        '409': {'model': ConflictError},
        '503': {'model': ServiceUnavailableError},
        '504': {'model': GatewayTimeoutError},
    },
    tags=['Rentals'],
)
def cancel_rental(
    rentalId: int = Path(..., ge=1),
    db: Session = Depends(get_db)
) -> RentalResponse:
    rental = db.query(Rental).filter(Rental.id == rentalId).first()
    if not rental:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RENTAL_NOT_FOUND", "message": f"Arriendo {rentalId} no encontrado."}
        )
        
    if rental.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "INVALID_STATE_TRANSITION", "message": f"No se puede cancelar un arriendo que está en estado {rental.status}."}
        )

    # TODO (gRPC): Integración con el sistema de Equipos
    # - Llamar a gRPC para liberar la unidad que había sido reservada.

    rental.status = "CANCELLED"
    db.commit()
    db.refresh(rental)
    return build_rental_response(rental)


@router.post(
    '/{rentalId}/return',
    response_model=RentalResponse,
    responses={
        '400': {'model': BadRequestError},
        '401': {'model': NotAuthorizedError},
        '403': {'model': ForbiddenError},
        '404': {'model': NotFoundError},
        '409': {'model': ConflictError},
        '503': {'model': ServiceUnavailableError},
        '504': {'model': GatewayTimeoutError},
    },
    tags=['Rentals'],
)
def return_rental(
    rentalId: int = Path(..., ge=1),
    db: Session = Depends(get_db)
) -> RentalResponse:
    rental = db.query(Rental).filter(Rental.id == rentalId).first()
    if not rental:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RENTAL_NOT_FOUND", "message": f"Arriendo {rentalId} no encontrado."}
        )
        
    if rental.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "INVALID_STATE_TRANSITION", "message": f"No se puede retornar un arriendo que está en estado {rental.status}."}
        )

    # TODO (gRPC): Integración con el sistema de Equipos
    # - Llamar a gRPC para informar que la unidad ha sido devuelta físicamente.

    rental.status = "COMPLETED"
    db.commit()
    db.refresh(rental)
    return build_rental_response(rental)

def build_rental_response(rental: Rental) -> RentalResponse:
    return RentalResponse(
        id=rental.id,
        clientId=rental.client_id,
        equipmentId=rental.equipment_id,
        startDate=rental.start_date,
        endDate=rental.end_date,
        status=rental.status
    )
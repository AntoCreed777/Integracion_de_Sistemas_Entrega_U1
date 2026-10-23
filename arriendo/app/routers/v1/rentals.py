import json
from fastapi import APIRouter, HTTPException, Depends, status, Query, Path, Response
from datetime import datetime, timezone
from typing import List, Union
from sqlalchemy.orm import Session
from sqlalchemy import update

from app.database import get_db
from app.bd_models import Client, Rental
from app.grpc_client import reservar_unidad, liberar_unidad
from app.auth import client_validation, admin_validation

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

from app.redis import ACTIVATE_REDIS

if ACTIVATE_REDIS:
    from app.redis import redis_client

router = APIRouter(prefix='/v1/rentals', tags=['Rentals'])
CACHE_HEADER = "CACHE_STATUS"   # Solo se usa si ACTIVATE_REDIS es True

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
def create_rental(
    rental_in: RentalRequest,
    db: Session = Depends(get_db),
    admin_auth: dict = Depends(admin_validation)
) -> RentalResponse:
    # 1. Validar fechas
    if rental_in.endDate <= rental_in.startDate:    #QUESTION: Esta bien que sea <= o deberia ser < ?
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "BAD_REQUEST", "message": "endDate debe ser posterior a startDate."},
        )

    # 2. Verificar que el cliente exista
    client = db.query(Client).filter(Client.id == rental_in.clientId).first()
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "CLIENT_NOT_FOUND", "message": f"El cliente {rental_in.clientId} no existe."}
        )

    reservar_unidad(rental_in.equipmentId)

    # 3. Guardar en la base de datos local
    db_rental = Rental(
        client_id=rental_in.clientId,
        equipment_id=rental_in.equipmentId,
        start_date=rental_in.startDate,
        end_date=rental_in.endDate,
        status="ACTIVE"
    )
    
    db.add(db_rental)
    try:
        db.commit()
    except Exception:
        db.rollback()
        try:
            liberar_unidad(rental_in.equipmentId)
        except HTTPException:
            # Si la compensación también falla, queda una unidad reservada
            # sin arriendo asociado. Es un costo aceptado que se documenta
            # en el ADR de resiliencia (D4): no hay forma de garantizar
            # atomicidad entre dos servicios sin una transacción
            # distribuida, que está fuera del alcance de este encargo.
            pass
        raise
    db.refresh(db_rental)

    if ACTIVATE_REDIS:
        for key in redis_client.scan_iter("rentals:list:*"):
            redis_client.delete(key)
    
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
    response: Response,
    limit: int = Query(20, ge=1, le=100, description="Límite de resultados"),
    offset: int = Query(0, ge=0, description="Desplazamiento para paginación"),
    db: Session = Depends(get_db),
    client_auth: dict = Depends(client_validation)
) -> List[RentalResponse]:
    if ACTIVATE_REDIS:
        cache_key = f"rentals:list:{limit}:{offset}"
        cached = redis_client.get(cache_key)
        if cached:
            results = [RentalResponse.model_validate(r) for r in json.loads(cached)]
            response.headers[CACHE_HEADER] = "HIT"
            return results

    rentals = db.query(Rental).order_by(Rental.id).offset(offset).limit(limit).all()
    results = [build_rental_response(r) for r in rentals]

    if ACTIVATE_REDIS:
        redis_client.setex(
            cache_key,
            60,
            json.dumps([r.model_dump(mode="json") for r in results])
        )
        response.headers[CACHE_HEADER] = "MISS"
    
    return results

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
    response: Response,
    rentalId: int = Path(..., ge=1, description="ID del arriendo"),
    db: Session = Depends(get_db),
    client_auth: dict = Depends(client_validation)
) -> RentalResponse:
    if ACTIVATE_REDIS:
        cache_key = f"rental:{rentalId}"
        cached = redis_client.get(cache_key)
        if cached:
            result = RentalResponse.model_validate(json.loads(cached))
            response.headers[CACHE_HEADER] = "HIT"
            return result

    rental = db.query(Rental).filter(Rental.id == rentalId).first()
    if not rental:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RENTAL_NOT_FOUND", "message": f"Arriendo {rentalId} no encontrado."}
        )

    result = build_rental_response(rental)

    if ACTIVATE_REDIS:
        redis_client.setex(
            cache_key,
            60,
            json.dumps(result.model_dump(mode="json"))
        )
        response.headers[CACHE_HEADER] = "MISS"

    return result

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
    db: Session = Depends(get_db),
    admin_auth: dict = Depends(admin_validation),
) -> RentalResponse:
    rental = db.execute(
        update(Rental)
        .where(Rental.id == rentalId, Rental.status == "ACTIVE")
        .values(status="CANCELLED")
        .returning(Rental)
    ).scalar_one_or_none()

    if rental is None:
        db.rollback()

        # EN un caso limite esto podria dar un codigo incorrecto si rental cambia de estado entre la consulta y el update, pero es un caso muy raro y no se considera crítico para este encargo.
        # El worst case scenario es un codigo incorrecto pero el update se mantiene atomico
        current = db.get(Rental, rentalId)

        if current is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "RENTAL_NOT_FOUND",
                    "message": f"Arriendo {rentalId} no encontrado.",
                },
            )

        raise HTTPException(
            status_code=409,
            detail={
                "code": "INVALID_STATE_TRANSITION",
                "message": (
                    f"No se puede cancelar un arriendo "
                    f"que está en estado {current.status}."
                ),
            },
        )

    response = build_rental_response(rental)

    try:
        liberar_unidad(rental.equipment_id)
        db.commit()
    except Exception:
        db.rollback()
        raise

    if ACTIVATE_REDIS:
        redis_client.delete(f"rental:{rentalId}")
        for key in redis_client.scan_iter("rentals:list:*"):
            redis_client.delete(key)

    return response


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
    db: Session = Depends(get_db),
    admin_auth: dict = Depends(admin_validation),
) -> RentalResponse:
    rental = db.execute(
        update(Rental)
        .where(Rental.id == rentalId, Rental.status == "ACTIVE")
        .values(status="COMPLETED")
        .returning(Rental)
    ).scalar_one_or_none()

    if rental is None:
        db.rollback()
        current = db.get(Rental, rentalId)

        if current is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "RENTAL_NOT_FOUND",
                    "message": f"Arriendo {rentalId} no encontrado.",
                },
            )

        raise HTTPException(
            status_code=409,
            detail={
                "code": "INVALID_STATE_TRANSITION",
                "message": (
                    f"No se puede retornar un arriendo "
                    f"que está en estado {current.status}."
                ),
            },
        )

    response = build_rental_response(rental)

    try:
        liberar_unidad(rental.equipment_id)
        db.commit()
    except Exception:
        db.rollback()
        raise

    if ACTIVATE_REDIS:
        redis_client.delete(f"rental:{rentalId}")
        for key in redis_client.scan_iter("rentals:list:*"):
            redis_client.delete(key)

    return response

def build_rental_response(rental: Rental) -> RentalResponse:
    start_date = (
        rental.start_date.replace(tzinfo=timezone.utc)
        if rental.start_date.tzinfo is None
        else rental.start_date
    )
    end_date = (
        rental.end_date.replace(tzinfo=timezone.utc)
        if rental.end_date.tzinfo is None
        else rental.end_date
    )
    return RentalResponse(
        id=rental.id,
        clientId=rental.client_id,
        equipmentId=rental.equipment_id,
        startDate=start_date,
        endDate=end_date,
        status=rental.status
    )
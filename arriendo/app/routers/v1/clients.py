from fastapi import APIRouter, HTTPException, Depends, status, Query, Path
from datetime import datetime, timezone
from typing import List
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.bd_models import Client

from app.models import (
    ClientRequest,
    ClientResponse,
    RentalHistory,
    BadRequestError,
    NotAuthorizedError,
    ForbiddenError,
    ConflictError,
    NotFoundError,
)

router = APIRouter(prefix='/v1/clients', tags=['Clients'])

@router.post(
    '',
    response_model=ClientResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": BadRequestError, "description": "Datos de entrada inválidos"},
        401: {"model": NotAuthorizedError, "description": "No autenticado"},
        403: {"model": ForbiddenError, "description": "Permisos insuficientes"},
        409: {"model": ConflictError, "description": "El email ya está registrado"},
    },
    tags=['Clients'],
)
def create_client(client_in: ClientRequest, db: Session = Depends(get_db)) -> ClientResponse:
    db_client = Client(name=client_in.name, email=client_in.email)
    db.add(db_client)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "EMAIL_ALREADY_EXISTS",
                "message": f"El correo '{client_in.email}' ya está registrado.",
            },
        )
    db.refresh(db_client)
    return build_client_response(db_client)


@router.get(
    '',
    response_model=List[ClientResponse],
    responses={
        '400': {'model': BadRequestError},
        '401': {'model': NotAuthorizedError},
        '403': {'model': ForbiddenError},
    },
    tags=['Clients'],
)
def get_all_clients(limit: int = 20, offset: int = 0, db: Session = Depends(get_db)) -> List[ClientResponse]:
    clients = db.query(Client).options(joinedload(Client.rentals)).order_by(Client.id).offset(offset).limit(limit).all()
    return [build_client_response(c) for c in clients]


@router.get(
    '/{clientId}',
    response_model=ClientResponse,
    responses={
        '400': {'model': BadRequestError},
        '401': {'model': NotAuthorizedError},
        '403': {'model': ForbiddenError},
        '404': {'model': NotFoundError},
    },
    tags=['Clients'],
)
def get_client_by_id(clientId: int, db: Session = Depends(get_db)) -> ClientResponse:
    client = db.query(Client).filter(Client.id == clientId).first()
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "CLIENT_NOT_FOUND", "message": f"Cliente con ID {clientId} no encontrado."}
        )
    return build_client_response(client)


def build_client_response(client: Client) -> ClientResponse:
    active = [r.id for r in client.rentals if r.status == "ACTIVE"]
    completed = [r.id for r in client.rentals if r.status == "COMPLETED"]
    cancelled = [r.id for r in client.rentals if r.status == "CANCELLED"]
    
    return ClientResponse(
        id=client.id,
        name=client.name,
        email=client.email,
        createdAt=(
            client.created_at.replace(tzinfo=timezone.utc)
            if client.created_at.tzinfo is None
            else client.created_at
        ),
        rentalHistory=RentalHistory(active=active, completed=completed, cancelled=cancelled)
    )
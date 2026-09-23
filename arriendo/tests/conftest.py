import os
from datetime import datetime, timezone

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_arriendo.db")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.bd_models import Client, Rental
from app.database import Base, get_db
from app.main import app


database_url = os.environ["DATABASE_URL"]
connect_args = (
    {"check_same_thread": False}
    if database_url.startswith("sqlite")
    else {}
)
engine = create_engine(database_url, connect_args=connect_args)
TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


@pytest.fixture()
def db_session():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        test_client.headers.update({"API-Key": "apikey_admin"})
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def grpc_equipment_service(monkeypatch):
    from app.routers.v1.rentals import rentals_without_redis

    monkeypatch.setattr(
        rentals_without_redis,
        "reservar_unidad",
        lambda equipment_id: None,
    )
    monkeypatch.setattr(
        rentals_without_redis,
        "liberar_unidad",
        lambda equipment_id: None,
    )


@pytest.fixture()
def crear_cliente(db_session):
    def _crear_cliente(
        nombre="Cliente de prueba",
        email="cliente@example.com",
    ):
        client = Client(name=nombre, email=email)
        db_session.add(client)
        db_session.commit()
        db_session.refresh(client)
        return client

    return _crear_cliente


@pytest.fixture()
def crear_arriendo(db_session, crear_cliente):
    def _crear_arriendo(
        client_id=None,
        equipment_id=50,
        status="ACTIVE",
    ):
        client_id = client_id or crear_cliente().id
        rental = Rental(
            client_id=client_id,
            equipment_id=equipment_id,
            start_date=datetime(2026, 9, 20, 10, tzinfo=timezone.utc),
            end_date=datetime(2026, 9, 25, 18, tzinfo=timezone.utc),
            status=status,
        )
        db_session.add(rental)
        db_session.commit()
        db_session.refresh(rental)
        return rental

    return _crear_arriendo

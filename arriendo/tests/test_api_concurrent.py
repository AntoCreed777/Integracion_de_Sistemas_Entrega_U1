from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock
from types import SimpleNamespace

import grpc
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app import grpc_client
from app.bd_models import Rental
from app.database import get_db
from app.main import app
from app.routers.v1 import rentals


@pytest.mark.parametrize(
    "operations, expected_states",
    [
        (["cancel"] * 5, {"CANCELLED"}),
        (["cancel", "return"], {"CANCELLED", "COMPLETED"}),
    ],
)
def test_solo_una_transicion_libera_la_unidad(
    db_session, crear_arriendo, monkeypatch, operations, expected_states
):
    rental_id = crear_arriendo().id
    db_session.rollback()  # Cierra la lectura abierta por el fixture.

    SessionLocal = sessionmaker(bind=db_session.get_bind())
    start = Barrier(len(operations))
    lock = Lock()
    releases = []

    def fake_liberar(equipment_id):
        with lock:
            releases.append(equipment_id)

    # Reemplaza el mock vacío del conftest por uno que cuenta liberaciones.
    monkeypatch.setattr(rentals, "liberar_unidad", fake_liberar)

    def execute(operation):
        # Cada solicitud usa su propia sesión: Session no se comparte entre hilos.
        with SessionLocal() as session:
            start.wait(timeout=30)

            endpoint = (
                rentals.cancel_rental
                if operation == "cancel"
                else rentals.return_rental
            )

            try:
                endpoint(rentalId=rental_id, db=session, admin_auth={})
                return 200, None
            except HTTPException as error:
                return error.status_code, error.detail["code"]

    with ThreadPoolExecutor(max_workers=len(operations)) as pool:
        results = list(pool.map(execute, operations))

    assert [code for code, _ in results].count(200) == 1
    assert [code for code, _ in results].count(409) == len(operations) - 1
    assert all(
        reason == "INVALID_STATE_TRANSITION"
        for code, reason in results
        if code == 409
    )
    assert releases == [50]  # ID de equipo predeterminado en crear_arriendo.

    db_session.rollback()
    assert db_session.get(Rental, rental_id).status in expected_states


def test_reservas_concurrentes_ultima_unidad_devuelven_409(
    db_session, crear_cliente, monkeypatch
):
    client_id = crear_cliente().id
    db_session.rollback()

    SessionLocal = sessionmaker(bind=db_session.get_bind())
    start = Barrier(2)
    both_checked_stock = Barrier(2)
    lock = Lock()
    stock = {"available": 1, "consultations": 0}

    class FailedPrecondition(grpc.RpcError):
        def code(self):
            return grpc.StatusCode.FAILED_PRECONDITION

    class FakeChannel:
        def close(self):
            pass

    class FakeEquipmentStub:
        def ConsultarDisponibilidadEquipo(self, request, timeout):
            with lock:
                stock["consultations"] += 1
            both_checked_stock.wait(timeout=30)
            return SimpleNamespace(unidades_disponibles=1)

        def ReservarEquipo(self, request, timeout):
            with lock:
                if stock["available"] == 0:
                    raise FailedPrecondition()
                stock["available"] -= 1

    stub = FakeEquipmentStub()
    monkeypatch.setattr(grpc_client, "get_grpc_stub", lambda: (stub, FakeChannel()))
    # El fixture general simula la reserva; aquí se ejercita el cliente gRPC real.
    monkeypatch.setattr(rentals, "reservar_unidad", grpc_client.reservar_unidad)

    def independent_db():
        with SessionLocal() as session:
            yield session

    def create_rental():
        start.wait(timeout=30)
        with TestClient(app) as client:
            return client.post(
                "/v1/rentals",
                headers={"API-Key": "apikey_admin"},
                json={
                    "clientId": client_id,
                    "equipmentId": 50,
                    "startDate": "2026-09-20T10:00:00Z",
                    "endDate": "2026-09-25T18:00:00Z",
                },
            )

    app.dependency_overrides[get_db] = independent_db
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: create_rental(), range(2)))
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert sorted(response.status_code for response in responses) == [201, 409]
    assert stock == {"available": 0, "consultations": 2}

    db_session.rollback()
    assert (
        db_session.query(Rental).filter_by(equipment_id=50, status="ACTIVE").count()
        == 1
    )

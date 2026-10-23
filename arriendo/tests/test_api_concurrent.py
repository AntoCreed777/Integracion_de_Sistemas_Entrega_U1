from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import sessionmaker

from app.bd_models import Rental
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
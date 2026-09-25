"""
Popula datos de prueba determinísticos (idempotentes) para las pruebas de
resiliencia de test_resiliencia_grpc.py.

"""

import sys
import pathlib

sys.path.append(str(pathlib.Path(__file__).parent.parent.resolve()))
sys.path.append(str(pathlib.Path(__file__).parent.parent.resolve() / "arriendo"))

from Arriendo.app.bd_models import Client, Rental
from Arriendo.app.database import SessionLocal

# Deben coincidir con TEST_CLIENT_ID / TEST_EQUIPMENT_ID en
# test_resiliencia_grpc.py
TEST_CLIENT_EMAIL = "resiliencia.test@example.com"
TEST_EQUIPMENT_ID = 1


def get_or_create_test_client(session) -> Client:
    """Reutiliza el cliente de prueba si ya existe, en vez de crear uno
    nuevo en cada corrida (evita ensuciar la DB con clientes duplicados)."""
    client = (
        session.query(Client)
        .filter(Client.email == TEST_CLIENT_EMAIL)
        .first()
    )
    if client:
        print(f"[INFO] Cliente de prueba ya existe (id={client.id}).")
        return client

    client = Client(
        name="Cliente Resiliencia Test",
        email=TEST_CLIENT_EMAIL,
    )
    session.add(client)
    session.commit()
    session.refresh(client)
    print(f"[INFO] Cliente de prueba creado (id={client.id}).")
    return client


def ensure_active_rental_for_cancel_test(session, client: Client) -> Rental:
    """Deja un arriendo en estado ACTIVE para poder probar cancel_rental
    con un ID real (en vez de un ID inexistente como 999999)."""
    rental = (
        session.query(Rental)
        .filter(
            Rental.client_id == client.id,
            Rental.equipment_id == TEST_EQUIPMENT_ID,
            Rental.status == "ACTIVE",
        )
        .first()
    )
    if rental:
        print(f"[INFO] Ya existe un arriendo ACTIVE de prueba (id={rental.id}).")
        return rental

    rental = Rental(
        client_id=client.id,
        equipment_id=TEST_EQUIPMENT_ID,
        start_date="2026-01-01",
        end_date="2026-01-10",
        status="ACTIVE",
    )
    session.add(rental)
    session.commit()
    session.refresh(rental)
    print(f"[INFO] Arriendo ACTIVE de prueba creado (id={rental.id}).")
    return rental


def fill_database():
    session = SessionLocal()
    try:
        client = get_or_create_test_client(session)
        rental = ensure_active_rental_for_cancel_test(session, client)

        print("\n--- Datos para usar en test_resiliencia_grpc.py ---")
        print(f"TEST_CLIENT_ID = {client.id}")
        print(f"TEST_EQUIPMENT_ID = {TEST_EQUIPMENT_ID}  (pendiente: debe existir en equipos-db)")
        print(f"ID de arriendo ACTIVE disponible para test de cancelación = {rental.id}")

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    try:
        fill_database()
    except Exception as exc:
        print(f"[ERROR] No se pudo llenar la base de datos: {exc}")
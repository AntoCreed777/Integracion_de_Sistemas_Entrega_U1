"""
Popula un equipo de prueba en la base de datos de EQUIPOS (equipos-db),
para que TEST_EQUIPMENT_ID en test_resiliencia_grpc.py tenga un registro
real contra el cual el servicio gRPC pueda responder.

Uso:
    $env:DATABASE_HOST="localhost"
    $env:DATABASE_PORT="5433"
    $env:DATABASE_NAME="equipos_db"
    $env:DATABASE_USER="equipos_user"
    $env:DATABASE_PASSWORD="equipos_password"
    python fill_bd_equipos.py
    //en powershell
    DATABASE_HOST=localhost \ DATABASE_PORT=5433 \ DATABASE_NAME=equipos_db \ DATABASE_USER=equipos_user \ DATABASE_PASSWORD=equipos_password \ python fill_bd_equipos.py
    //en linux/mac
"""

import os
import sys
import pathlib

sys.path.append(str(pathlib.Path(__file__).parent.parent.resolve()))
sys.path.append(str(pathlib.Path(__file__).parent.parent.resolve() / "Equipos"))

from Equipos.app.models.equipo import Equipo  
from Equipos.app.database import SessionLocal 

# Debe coincidir con TEST_EQUIPMENT_ID en test_resiliencia_grpc.py
TEST_EQUIPO_ID = 1
UNIDADES_TOTALES = 100
UNIDADES_DISPONIBLES = 100


def get_or_create_test_equipment(session) -> Equipo:
    equipo = (
        session.query(Equipo)
        .filter(Equipo.equipo_id == TEST_EQUIPO_ID)
        .first()
    )
    if equipo:
        print(
            f"[INFO] Equipo de prueba ya existe "
            f"(id={equipo.id}, equipo_id={equipo.equipo_id}, "
            f"disponibles={equipo.unidades_disponibles})."
        )
        # Nos aseguramos de que siempre tenga stock disponible para los
        # tests de "happy path" (create_rental / reservar_unidad).
        if equipo.unidades_disponibles <= 0:
            equipo.unidades_disponibles = UNIDADES_DISPONIBLES
            session.commit()
            session.refresh(equipo)
            print(f"[INFO] Stock repuesto a {UNIDADES_DISPONIBLES} unidades.")
        return equipo

    equipo = Equipo(
        equipo_id=TEST_EQUIPO_ID,
        nombre="Equipo de prueba - resiliencia",
        descripcion="Creado por seed_equipment.py para tests de resiliencia gRPC.",
        cantidad_total=UNIDADES_TOTALES,
        unidades_disponibles=UNIDADES_DISPONIBLES,
        activo=True,
    )
    session.add(equipo)
    session.commit()
    session.refresh(equipo)
    print(
        f"[INFO] Equipo de prueba creado "
        f"(id={equipo.id}, equipo_id={equipo.equipo_id}, "
        f"disponibles={equipo.unidades_disponibles})."
    )
    return equipo


def fill_database():
    session = SessionLocal()
    try:
        equipo = get_or_create_test_equipment(session)

        print("\n--- Dato para usar en test_resiliencia_grpc.py ---")
        print(f"TEST_EQUIPMENT_ID = {equipo.equipo_id}")

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    required_env = [
        "DATABASE_USER",
        "DATABASE_PASSWORD",
        "DATABASE_HOST",
        "DATABASE_PORT",
        "DATABASE_NAME",
    ]
    missing = [v for v in required_env if not os.environ.get(v)]
    if missing:
        print(f"[ERROR] Faltan variables de entorno: {', '.join(missing)}")
        sys.exit(1)

    try:
        fill_database()
    except Exception as exc:
        print(f"[ERROR] No se pudo llenar la base de datos: {exc}")
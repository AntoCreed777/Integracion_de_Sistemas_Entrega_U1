import random
import string
import sys
import pathlib

sys.path.append(str(pathlib.Path(__file__).parent.parent.resolve()))
sys.path.append(str(pathlib.Path(__file__).parent.parent.resolve() / "arriendo"))


from arriendo.app.bd_models import Client, Rental
from arriendo.app.database import SessionLocal


def cadena_aleatoria(longitud: int) -> str:
    return "".join(
        random.choices(
            string.ascii_letters + string.digits,
            k=longitud,
        )
    )


def fill_database(cantidad_arriendos: int):
    session = SessionLocal()

    try:
        nuevo_cliente = Client(
            name=cadena_aleatoria(10),
            email=f"{cadena_aleatoria(5)}@example.com",
        )

        session.add(nuevo_cliente)
        session.commit()
        session.refresh(nuevo_cliente)

        for _ in range(cantidad_arriendos):
            nuevo_equipo = Rental(
                client_id=nuevo_cliente.id,
                equipment_id=random.randint(1, 1000),
                start_date=f"2023-01-{random.randint(1, 28)}",
                end_date=f"2023-02-{random.randint(1, 28)}",
                status=random.choice(
                    ["ACTIVE", "COMPLETED", "CANCELLED"]
                ),
            )

            session.add(nuevo_equipo)

        session.commit()

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()


if __name__ == "__main__":
    try:
        fill_database(1)
    except Exception as exc:
        print(f"[ERROR] No se pudo llenar la base de datos: {exc}")

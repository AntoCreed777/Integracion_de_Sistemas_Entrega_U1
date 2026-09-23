import random
import string

from arriendo.app.bd_models import Client, Rental
from arriendo.app.database import SessionLocal


def fill_database(cantidad_arriendos: int):
    """
    Llena la base de datos con una cantidad específica de arriendos de prueba y un solo cliente.

    Cada arriendo tendra valores aleatorios para sus atributos.
    """
    session = SessionLocal()
    cadena_aleatoria = lambda longitud: "".join(
        random.choices(string.ascii_letters + string.digits, k=longitud)
    )

    nuevo_cliente = Client(
        name=f"{cadena_aleatoria(10)}",
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
            status=random.choice(["ACTIVE", "COMPLETED", "CANCELLED"]),
        )

        session.add(nuevo_equipo)

    session.commit()
    session.close()

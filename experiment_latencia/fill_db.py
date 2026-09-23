import random
import string

from Equipos.app.database import SessionLocal
from Equipos.app.models.equipo import Equipo


def fill_database(cantidad_equipos: int):
    """
    Llena la base de datos con una cantidad específica de equipos de prueba.

    Cada equipo tendra valores aleatorios para sus atributos, y se asegura de que la cantidad de unidades disponibles no exceda la cantidad total.
    """
    session = SessionLocal()
    cadena_aleatoria = lambda longitud: "".join(
        random.choices(string.ascii_letters + string.digits, k=longitud)
    )

    for _ in range(cantidad_equipos):
        nombre = f"{cadena_aleatoria(10)}"
        descripcion = f"{cadena_aleatoria(10)}"
        cantidad_total = random.randint(1, 100)  # Cantidad total entre 1 y 100
        unidades_disponibles = random.randint(
            0, cantidad_total
        )  # Unidades disponibles entre 0 y cantidad_total

        nuevo_equipo = Equipo(
            nombre=nombre,
            descripcion=descripcion,
            cantidad_total=cantidad_total,
            unidades_disponibles=unidades_disponibles,
        )

        session.add(nuevo_equipo)

    session.commit()
    session.close()


import json
import sys
from pathlib import Path

from app.database import db_session
from app.models.equipo import Equipo
from sqlalchemy import select


def cargar_equipos(path_initial_data: Path) -> None:
    with path_initial_data.open("r", encoding="utf-8") as archivo:
        equipos = json.load(archivo)

    if not isinstance(equipos, list):
        raise ValueError("El archivo JSON debe contener una lista de equipos.")

    with db_session() as db:
        try:
            existe_equipos = db.scalar(
                select(Equipo.id).limit(1)
            )

            if existe_equipos:
                print(
                    f"Ya existen datos en la base de datos. Se omitirá la carga de los equipos iniciales."
                )
                return

            for datos in equipos:
                db.query(Equipo).filter_by(equipo_id=datos["equipo_id"])
                db.add(
                    Equipo(
                        equipo_id=datos["equipo_id"],
                        nombre=datos["nombre"],
                        descripcion=datos.get("descripcion"),
                        cantidad_total=datos["cantidad_total"],
                        unidades_disponibles=datos["unidades_disponibles"],
                        activo=datos.get("activo", True),
                    )
                )

            db.commit()

        except Exception:
            db.rollback()
            raise

    print(
        f"Se han cargado {len(equipos)} equipos "
        f"en la base de datos desde {path_initial_data}."
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python cargar_equipos.py <ruta_al_json>")
        sys.exit(1)

    cargar_equipos(Path(sys.argv[1]))

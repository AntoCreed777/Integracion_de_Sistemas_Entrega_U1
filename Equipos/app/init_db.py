from app.database import engine
from app.models.base import Base
from app.models.equipo import Equipo


def crear_tablas():
    Base.metadata.create_all(bind=engine)
    from sqlalchemy import inspect

    inspector = inspect(engine)

    print(inspector.get_table_names())
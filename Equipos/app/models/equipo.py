from datetime import datetime

from app.models.base import Base
from sqlalchemy import Boolean, CheckConstraint, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column


class Equipo(Base):
    __tablename__ = "equipos"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    equipo_id: Mapped[int] = mapped_column(
        nullable=False,
        index=True,
    )

    nombre: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    descripcion: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    cantidad_total: Mapped[int] = mapped_column(
        nullable=False,
    )

    unidades_disponibles: Mapped[int] = mapped_column(
        nullable=False,
    )

    activo: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "cantidad_total >= 0",
            name="ck_equipos_total_no_negativo",
        ),
        CheckConstraint(
            "unidades_disponibles >= 0",
            name="ck_equipos_disponible_no_negativo",
        ),
        CheckConstraint(
            "unidades_disponibles <= cantidad_total",
            name="ck_equipos_disponible_menor_total",
        ),
    )


from sqlalchemy import update
from sqlalchemy.orm import Session


def reservar_equipo(db: Session, equipo_id: int) -> bool:

    stmt = (
        update(Equipo)
        .where(
            Equipo.equipo_id == equipo_id,
            Equipo.activo == True,
            Equipo.unidades_disponibles > 0,
        )
        .values(unidades_disponibles=Equipo.unidades_disponibles - 1)
    )

    result = db.execute(stmt)
    db.commit()

    return result.rowcount == 1


def liberar_equipo(db: Session, equipo_id: int) -> bool:

    stmt = (
        update(Equipo)
        .where(
            Equipo.equipo_id == equipo_id,
            Equipo.activo == True,
            Equipo.unidades_disponibles + 1 <= Equipo.cantidad_total,
        )
        .values(unidades_disponibles=Equipo.unidades_disponibles + 1)
    )

    result = db.execute(stmt)
    db.commit()

    return result.rowcount == 1

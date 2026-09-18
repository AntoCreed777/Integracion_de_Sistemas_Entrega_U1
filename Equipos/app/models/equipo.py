from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


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

    cantidad_disponible: Mapped[int] = mapped_column(
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
            "cantidad_disponible >= 0",
            name="ck_equipos_disponible_no_negativo",
        ),
        CheckConstraint(
            "cantidad_disponible <= cantidad_total",
            name="ck_equipos_disponible_menor_total",
        ),
    )
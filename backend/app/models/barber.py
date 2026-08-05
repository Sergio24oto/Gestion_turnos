from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class Barber(Base):
    __tablename__ = "peluqueros"
    __table_args__ = (
        CheckConstraint("intervalo_turnos_minutos > 0", name="ck_peluqueros_intervalo_turnos_positivo"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column("nombre", String(120), nullable=False)
    description: Mapped[str] = mapped_column("descripcion", String(180), nullable=True)
    photo_url: Mapped[str] = mapped_column("foto_url", String(255), nullable=True)
    active: Mapped[bool] = mapped_column("activo", Boolean, nullable=False, default=True)
    order: Mapped[int] = mapped_column("orden", Integer, nullable=False, default=0)
    appointment_interval_minutes: Mapped[int] = mapped_column(
        "intervalo_turnos_minutos",
        Integer,
        nullable=False,
        default=20,
    )
    created_at: Mapped[datetime] = mapped_column("creado_en", DateTime, server_default=func.now(), nullable=False)

    service_prices = relationship("BarberService", back_populates="barber")

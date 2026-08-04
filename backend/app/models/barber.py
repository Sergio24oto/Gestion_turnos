from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class Barber(Base):
    __tablename__ = "peluqueros"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column("nombre", String(120), nullable=False)
    description: Mapped[str] = mapped_column("descripcion", String(180), nullable=True)
    photo_url: Mapped[str] = mapped_column("foto_url", String(255), nullable=True)
    active: Mapped[bool] = mapped_column("activo", Boolean, nullable=False, default=True)
    order: Mapped[int] = mapped_column("orden", Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column("creado_en", DateTime, server_default=func.now(), nullable=False)

    service_prices = relationship("BarberService", back_populates="barber")

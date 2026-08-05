from decimal import Decimal
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class Service(Base):
    __tablename__ = "servicios"
    __table_args__ = (CheckConstraint("precio >= 0", name="ck_servicios_precio_no_negativo"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column("nombre", String(120), nullable=False, unique=True)
    description: Mapped[str] = mapped_column("descripcion", String(255), nullable=True)
    category: Mapped[str] = mapped_column("categoria", String(80), nullable=True)
    duration_minutes: Mapped[int] = mapped_column("duracion", Integer, nullable=False, default=20)
    # Legacy expand/contract column. New pricing logic uses peluqueros_servicios.precio.
    price: Mapped[Decimal] = mapped_column("precio", Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    active: Mapped[bool] = mapped_column("activo", Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column("creado_en", DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column("actualizado_en", DateTime, nullable=True, onupdate=func.now())

    barber_prices = relationship("BarberService", back_populates="service")

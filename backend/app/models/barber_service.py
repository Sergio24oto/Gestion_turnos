from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, Numeric, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class BarberService(Base):
    __tablename__ = "peluqueros_servicios"
    __table_args__ = (
        UniqueConstraint("peluquero_id", "servicio_id", name="uq_peluqueros_servicios_peluquero_servicio"),
        CheckConstraint("precio >= 0", name="ck_peluqueros_servicios_precio_no_negativo"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    barber_id: Mapped[int] = mapped_column("peluquero_id", ForeignKey("peluqueros.id"), nullable=False, index=True)
    service_id: Mapped[int] = mapped_column("servicio_id", ForeignKey("servicios.id"), nullable=False, index=True)
    price: Mapped[Decimal] = mapped_column("precio", Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    active: Mapped[bool] = mapped_column("activo", Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column("creado_en", DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column("actualizado_en", DateTime, nullable=True, onupdate=func.now())

    barber = relationship("Barber", back_populates="service_prices")
    service = relationship("Service", back_populates="barber_prices")

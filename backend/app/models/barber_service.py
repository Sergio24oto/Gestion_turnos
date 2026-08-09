from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Integer, Numeric, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class BarberService(Base):
    __tablename__ = "peluqueros_servicios"
    __table_args__ = (
        UniqueConstraint("peluquero_id", "servicio_id", name="uq_peluqueros_servicios_peluquero_servicio"),
        CheckConstraint("precio IS NULL OR precio >= 0", name="ck_peluqueros_servicios_precio_no_negativo"),
        CheckConstraint(
            "duracion_visible_minutos IS NULL OR duracion_visible_minutos > 0",
            name="ck_peluqueros_servicios_duracion_visible_positiva",
        ),
        CheckConstraint("duracion_bloqueo_minutos > 0", name="ck_peluqueros_servicios_duracion_bloqueo_positiva"),
        CheckConstraint("monto_senia IS NULL OR monto_senia >= 0", name="ck_peluqueros_servicios_monto_senia_no_negativo"),
        CheckConstraint(
            "porcentaje_senia IS NULL OR (porcentaje_senia > 0 AND porcentaje_senia <= 100)",
            name="ck_peluqueros_servicios_porcentaje_senia_valido",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    barber_id: Mapped[int] = mapped_column("peluquero_id", ForeignKey("peluqueros.id"), nullable=False, index=True)
    service_id: Mapped[int] = mapped_column("servicio_id", ForeignKey("servicios.id"), nullable=False, index=True)
    price: Mapped[Decimal] = mapped_column("precio", Numeric(10, 2), nullable=True)
    visible_duration_minutes: Mapped[int] = mapped_column("duracion_visible_minutos", Integer, nullable=True)
    blocking_duration_minutes: Mapped[int] = mapped_column(
        "duracion_bloqueo_minutos",
        Integer,
        nullable=False,
        default=20,
    )
    active: Mapped[bool] = mapped_column("activo", Boolean, nullable=False, default=True)
    requires_deposit: Mapped[bool] = mapped_column("requiere_senia", Boolean, nullable=False, default=False)
    deposit_type: Mapped[str] = mapped_column(
        "tipo_senia",
        Enum("fijo", "porcentaje", name="tipo_senia"),
        nullable=True,
    )
    deposit_amount: Mapped[Decimal] = mapped_column("monto_senia", Numeric(10, 2), nullable=True)
    deposit_percentage: Mapped[Decimal] = mapped_column("porcentaje_senia", Numeric(5, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column("creado_en", DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column("actualizado_en", DateTime, nullable=True, onupdate=func.now())

    barber = relationship("Barber", back_populates="service_prices")
    service = relationship("Service", back_populates="barber_prices")

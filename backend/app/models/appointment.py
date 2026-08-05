from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import CheckConstraint, Computed, Date, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Time, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class Appointment(Base):
    __tablename__ = "turnos"
    __table_args__ = (
        Index("uq_turnos_peluquero_fecha_hora_activo", "peluquero_id", "fecha_activa", "hora_activa", unique=True),
        Index("uq_turnos_cancelacion_token_hash", "cancelacion_token_hash", unique=True),
        CheckConstraint(
            "precio_servicio IS NULL OR precio_servicio >= 0",
            name="ck_turnos_precio_servicio_no_negativo",
        ),
        CheckConstraint(
            "duracion_visible_servicio IS NULL OR duracion_visible_servicio > 0",
            name="ck_turnos_duracion_visible_servicio_positiva",
        ),
        CheckConstraint(
            "duracion_bloqueo_servicio > 0",
            name="ck_turnos_duracion_bloqueo_servicio_positiva",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column("cliente_id", ForeignKey("clientes.id"), nullable=False)
    service_id: Mapped[int] = mapped_column("servicio_id", ForeignKey("servicios.id"), nullable=False)
    barber_id: Mapped[int] = mapped_column("peluquero_id", ForeignKey("peluqueros.id"), nullable=False, index=True)
    service_price: Mapped[Decimal] = mapped_column(
        "precio_servicio",
        Numeric(10, 2),
        nullable=True,
        default=Decimal("0.00"),
    )
    service_visible_duration_minutes: Mapped[int] = mapped_column(
        "duracion_visible_servicio",
        Integer,
        nullable=True,
    )
    service_blocking_duration_minutes: Mapped[int] = mapped_column(
        "duracion_bloqueo_servicio",
        Integer,
        nullable=False,
        default=20,
    )
    date: Mapped[date] = mapped_column("fecha", Date, nullable=False, index=True)
    start_time: Mapped[time] = mapped_column("hora_inicio", Time, nullable=False)
    status: Mapped[str] = mapped_column(
        "estado",
        Enum("Confirmado", "Cancelado", "Completado", name="estado_turno"),
        nullable=False,
        default="Confirmado",
    )
    origin: Mapped[str] = mapped_column(
        "origen",
        Enum("APP", "MANUAL", name="origen_turno"),
        nullable=False,
        default="APP",
    )
    cancellation_token_hash: Mapped[str] = mapped_column(
        "cancelacion_token_hash",
        String(64),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column("creado_en", DateTime, server_default=func.now(), nullable=False)
    active_date: Mapped[date] = mapped_column(
        "fecha_activa",
        Date,
        Computed("CASE WHEN estado <> 'Cancelado' THEN fecha ELSE NULL END", persisted=True),
        nullable=True,
    )
    active_time: Mapped[time] = mapped_column(
        "hora_activa",
        Time,
        Computed("CASE WHEN estado <> 'Cancelado' THEN hora_inicio ELSE NULL END", persisted=True),
        nullable=True,
    )

    client = relationship("Client")
    service = relationship("Service")
    barber = relationship("Barber")

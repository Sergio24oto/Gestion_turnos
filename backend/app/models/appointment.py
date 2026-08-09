from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Computed, Date, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Time, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

STATUS_PENDING_PAYMENT = "PENDING_PAYMENT"
STATUS_CONFIRMED = "CONFIRMED"
STATUS_CANCELLED = "CANCELLED"
STATUS_EXPIRED = "EXPIRED"
STATUS_COMPLETED = "COMPLETED"
LEGACY_STATUS_CONFIRMED = "Confirmado"
LEGACY_STATUS_CANCELLED = "Cancelado"
LEGACY_STATUS_COMPLETED = "Completado"

CANCELLED_STATUSES = (STATUS_CANCELLED, LEGACY_STATUS_CANCELLED)
EXPIRED_STATUSES = (STATUS_EXPIRED,)
BLOCKING_CONFIRMED_STATUSES = (STATUS_CONFIRMED, STATUS_COMPLETED, LEGACY_STATUS_CONFIRMED, LEGACY_STATUS_COMPLETED)


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
        CheckConstraint("monto_senia IS NULL OR monto_senia >= 0", name="ck_turnos_monto_senia_no_negativo"),
        CheckConstraint("saldo_pendiente IS NULL OR saldo_pendiente >= 0", name="ck_turnos_saldo_pendiente_no_negativo"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column("cliente_id", ForeignKey("clientes.id"), nullable=False)
    service_id: Mapped[int] = mapped_column("servicio_id", ForeignKey("servicios.id"), nullable=False)
    barber_id: Mapped[int] = mapped_column("peluquero_id", ForeignKey("peluqueros.id"), nullable=False, index=True)
    service_price: Mapped[Decimal] = mapped_column(
        "precio_servicio",
        Numeric(10, 2),
        nullable=True,
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
        Enum(
            LEGACY_STATUS_CONFIRMED,
            LEGACY_STATUS_CANCELLED,
            LEGACY_STATUS_COMPLETED,
            STATUS_PENDING_PAYMENT,
            STATUS_CONFIRMED,
            STATUS_CANCELLED,
            STATUS_EXPIRED,
            STATUS_COMPLETED,
            name="estado_turno",
        ),
        nullable=False,
        default=STATUS_CONFIRMED,
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
    payment_status_token_hash: Mapped[str] = mapped_column(
        "payment_status_token_hash",
        String(64),
        nullable=True,
        unique=True,
    )
    deposit_amount: Mapped[Decimal] = mapped_column("monto_senia", Numeric(10, 2), nullable=True)
    remaining_balance: Mapped[Decimal] = mapped_column("saldo_pendiente", Numeric(10, 2), nullable=True)
    payment_expires_at: Mapped[datetime] = mapped_column("payment_expires_at", DateTime, nullable=True)
    no_show: Mapped[bool] = mapped_column("no_show", Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column("creado_en", DateTime, server_default=func.now(), nullable=False)
    active_date: Mapped[date] = mapped_column(
        "fecha_activa",
        Date,
        Computed("CASE WHEN estado NOT IN ('Cancelado', 'CANCELLED', 'EXPIRED') THEN fecha ELSE NULL END", persisted=True),
        nullable=True,
    )
    active_time: Mapped[time] = mapped_column(
        "hora_activa",
        Time,
        Computed("CASE WHEN estado NOT IN ('Cancelado', 'CANCELLED', 'EXPIRED') THEN hora_inicio ELSE NULL END", persisted=True),
        nullable=True,
    )

    client = relationship("Client")
    service = relationship("Service")
    barber = relationship("Barber")
    payments = relationship("Payment", back_populates="appointment")

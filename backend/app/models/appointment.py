from datetime import date, datetime, time

from sqlalchemy import Computed, Date, DateTime, Enum, ForeignKey, Index, Integer, String, Time, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

class Appointment(Base):
    __tablename__ = "turnos"
    __table_args__ = (
        Index("uq_turnos_fecha_hora_activo", "fecha_activa", "hora_activa", unique=True),
        Index("uq_turnos_cancelacion_token_hash", "cancelacion_token_hash", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column("cliente_id", ForeignKey("clientes.id"), nullable=False)
    service_id: Mapped[int] = mapped_column("servicio_id", ForeignKey("servicios.id"), nullable=False)
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



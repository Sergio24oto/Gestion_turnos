from datetime import date, datetime, time

from sqlalchemy import Date, DateTime, Integer, String, Time, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class BlockedSlot(Base):
    __tablename__ = "bloqueos_horarios"
    __table_args__ = (UniqueConstraint("fecha", "hora_inicio", name="uq_bloqueos_fecha_hora"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    date: Mapped[date] = mapped_column("fecha", Date, nullable=False, index=True)
    start_time: Mapped[time] = mapped_column("hora_inicio", Time, nullable=False)
    reason: Mapped[str] = mapped_column("motivo", String(180), nullable=True)
    created_at: Mapped[datetime] = mapped_column("creado_en", DateTime, server_default=func.now(), nullable=False)

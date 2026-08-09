from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

PAYMENT_STATUS_PENDING = "PENDING"
PAYMENT_STATUS_APPROVED = "APPROVED"
PAYMENT_STATUS_REJECTED = "REJECTED"
PAYMENT_STATUS_CANCELLED = "CANCELLED"
PAYMENT_STATUS_REFUNDED = "REFUNDED"


class Payment(Base):
    __tablename__ = "pagos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    appointment_id: Mapped[int] = mapped_column("turno_id", ForeignKey("turnos.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column("proveedor", String(40), nullable=False, default="mercadopago")
    external_payment_id: Mapped[str] = mapped_column("external_payment_id", String(120), nullable=True, unique=True)
    external_preference_id: Mapped[str] = mapped_column("external_preference_id", String(120), nullable=True, index=True)
    checkout_url: Mapped[str] = mapped_column("checkout_url", String(500), nullable=True)
    amount: Mapped[Decimal] = mapped_column("monto", Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column("moneda", String(3), nullable=False, default="ARS")
    status: Mapped[str] = mapped_column(
        "estado",
        Enum(
            PAYMENT_STATUS_PENDING,
            PAYMENT_STATUS_APPROVED,
            PAYMENT_STATUS_REJECTED,
            PAYMENT_STATUS_CANCELLED,
            PAYMENT_STATUS_REFUNDED,
            name="estado_pago",
        ),
        nullable=False,
        default=PAYMENT_STATUS_PENDING,
    )
    raw_status: Mapped[str] = mapped_column("raw_status", Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column("creado_en", DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column("actualizado_en", DateTime, nullable=True, onupdate=func.now())
    approved_at: Mapped[datetime] = mapped_column("aprobado_en", DateTime, nullable=True)

    appointment = relationship("Appointment", back_populates="payments")

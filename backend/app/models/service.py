from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class Service(Base):
    __tablename__ = "servicios"
    __table_args__ = (CheckConstraint("precio >= 0", name="ck_servicios_precio_no_negativo"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column("nombre", String(120), nullable=False, unique=True)
    duration_minutes: Mapped[int] = mapped_column("duracion", Integer, nullable=False, default=20)
    price: Mapped[Decimal] = mapped_column("precio", Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    active: Mapped[bool] = mapped_column("activo", Boolean, nullable=False, default=True)

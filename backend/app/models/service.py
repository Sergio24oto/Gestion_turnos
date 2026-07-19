from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class Service(Base):
    __tablename__ = "servicios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column("nombre", String(120), nullable=False, unique=True)
    duration_minutes: Mapped[int] = mapped_column("duracion", Integer, nullable=False, default=20)
    active: Mapped[bool] = mapped_column("activo", Boolean, nullable=False, default=True)

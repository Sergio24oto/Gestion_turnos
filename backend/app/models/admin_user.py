from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class AdminUser(Base):
    __tablename__ = "usuarios_admin"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column("usuario", String(80), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column("password_hash", String(255), nullable=False)
    active: Mapped[bool] = mapped_column("activo", Boolean, nullable=False, default=True)

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class Client(Base):
    __tablename__ = "clientes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    first_name: Mapped[str] = mapped_column("nombre", String(80), nullable=False)
    last_name: Mapped[str] = mapped_column("apellido", String(80), nullable=False)
    phone: Mapped[str] = mapped_column("telefono", String(40), nullable=False)

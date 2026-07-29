from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .models.admin_user import AdminUser
from .models.barber import Barber
from .models.service import Service
from .services.auth import hash_password


DEFAULT_SERVICES = [
    ("Corte clásico", 20),
    ("Corte clásico + barba + cejas", 20),
    ("Corte clásico + cejas", 20),
    ("Barba solamente", 20),
]

DEFAULT_BARBERS = [
    ("Marcelo Navarro", "Cortes clásicos, barba y atención unisex.", "/marcelo-navarro-logo.png", 1),
    ("Equipo Marcelo Navarro", "Atención unisex y turnos de apoyo.", "/marcelo-navarro-logo.png", 2),
]


def seed_initial_data(db: Session) -> None:
    for name, duration in DEFAULT_SERVICES:
        exists = db.scalar(select(Service).where(Service.name == name))
        if not exists:
            db.add(Service(name=name, duration_minutes=duration, active=True))

    for name, description, photo_url, order in DEFAULT_BARBERS:
        exists = db.scalar(select(Barber).where(Barber.name == name))
        if not exists:
            db.add(Barber(name=name, description=description, photo_url=photo_url, active=True, order=order))

    admin = db.scalar(select(AdminUser).where(AdminUser.username == settings.admin_default_user))
    if not admin:
        db.add(
            AdminUser(
                username=settings.admin_default_user,
                password_hash=hash_password(settings.admin_default_password),
                active=True,
            )
        )
    db.commit()

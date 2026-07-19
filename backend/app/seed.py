from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .models.admin_user import AdminUser
from .models.service import Service
from .services.auth import hash_password


DEFAULT_SERVICES = [
    ("Corte clásico", 20),
    ("Corte clásico + barba + cejas", 20),
    ("Corte clásico + cejas", 20),
    ("Barba solamente", 20),
]


def seed_initial_data(db: Session) -> None:
    for name, duration in DEFAULT_SERVICES:
        exists = db.scalar(select(Service).where(Service.name == name))
        if not exists:
            db.add(Service(name=name, duration_minutes=duration, active=True))

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

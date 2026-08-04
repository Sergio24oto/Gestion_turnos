from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .models.admin_user import AdminUser
from .models.barber import Barber
from .models.barber_service import BarberService
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
            db.add(Service(name=name, duration_minutes=duration, price=Decimal("0.00"), active=True))

    for name, description, photo_url, order in DEFAULT_BARBERS:
        exists = db.scalar(select(Barber).where(Barber.name == name))
        if not exists:
            db.add(Barber(name=name, description=description, photo_url=photo_url, active=True, order=order))

    db.flush()

    barbers = db.scalars(select(Barber).where(Barber.active.is_(True))).all()
    services = db.scalars(select(Service).where(Service.active.is_(True))).all()
    for barber in barbers:
        for service in services:
            exists = db.scalar(
                select(BarberService).where(
                    BarberService.barber_id == barber.id,
                    BarberService.service_id == service.id,
                )
            )
            if not exists:
                db.add(BarberService(barber=barber, service=service, price=Decimal("0.00"), active=True))

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

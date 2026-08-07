from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import settings
from .models.admin_user import AdminUser
from .models.barber import Barber
from .models.service import Service
from .services.auth import hash_password


# Datos mínimos para una instalación vacía. El catálogo global vive en servicios;
# precio, duración y asignación por profesional viven en peluqueros_servicios.
DEFAULT_SERVICES = [
    ("Corte clásico", 20),
    ("Corte clásico + barba + cejas", 20),
    ("Corte clásico + cejas", 20),
    ("Barba solamente", 20),
]

DEFAULT_BARBERS = [
    {
        "name": "Marcelo Navarro",
        "description": "Cortes clásicos, barba y atención unisex.",
        "photo_url": "/barbers/marcelo.jpeg",
        "order": 1,
        "appointment_interval_minutes": 20,
    },
    {
        "name": "Jeremías Vivas",
        "description": "Atención unisex, cortes actuales y turnos de apoyo.",
        "photo_url": "/barbers/jeremias.jpeg",
        "order": 2,
        "appointment_interval_minutes": 30,
    },
]


def seed_initial_data(db: Session) -> None:
    services_count = db.scalar(select(func.count(Service.id))) or 0
    if services_count == 0:
        for name, duration in DEFAULT_SERVICES:
            db.add(Service(name=name, duration_minutes=duration, price=Decimal("0.00"), active=True))

    barbers_count = db.scalar(select(func.count(Barber.id))) or 0
    if barbers_count == 0:
        for barber_data in DEFAULT_BARBERS:
            db.add(
                Barber(
                    name=barber_data["name"],
                    description=barber_data["description"],
                    photo_url=barber_data["photo_url"],
                    active=True,
                    order=barber_data["order"],
                    appointment_interval_minutes=barber_data["appointment_interval_minutes"],
                )
            )

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

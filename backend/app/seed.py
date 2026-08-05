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
    ("Corte clásico", ("Corte clásico", "Corte clasico", "Corte clÃ¡sico"), 20),
    (
        "Corte clásico + barba + cejas",
        ("Corte clásico + barba + cejas", "Corte clasico + barba + cejas", "Corte clÃ¡sico + barba + cejas"),
        20,
    ),
    (
        "Corte clásico + cejas",
        ("Corte clásico + cejas", "Corte clasico + cejas", "Corte clÃ¡sico + cejas"),
        20,
    ),
    ("Barba solamente", ("Barba solamente",), 20),
]

DEFAULT_BARBERS = [
    {
        "name": "Marcelo Navarro",
        "aliases": ("Marcelo Navarro",),
        "description": "Cortes clásicos, barba y atención unisex.",
        "photo_url": "/barbers/marcelo.jpeg",
        "order": 1,
        "appointment_interval_minutes": 20,
    },
    {
        "name": "Jeremías Vivas",
        "aliases": ("Jeremias Vivas", "Jeremías Vivas", "Equipo Marcelo Navarro"),
        "description": "Atención unisex, cortes actuales y turnos de apoyo.",
        "photo_url": "/barbers/jeremias.jpeg",
        "order": 2,
        "appointment_interval_minutes": 30,
    },
]


def seed_initial_data(db: Session) -> None:
    for name, aliases, duration in DEFAULT_SERVICES:
        exists = db.scalar(select(Service).where(Service.name.in_(aliases)))
        if not exists:
            db.add(Service(name=name, duration_minutes=duration, price=Decimal("0.00"), active=True))

    for barber_data in DEFAULT_BARBERS:
        exists = db.scalar(select(Barber).where(Barber.name.in_(barber_data["aliases"])))
        if not exists:
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
                db.add(
                    BarberService(
                        barber=barber,
                        service=service,
                        price=Decimal("0.00"),
                        visible_duration_minutes=service.duration_minutes,
                        blocking_duration_minutes=barber.appointment_interval_minutes,
                        active=True,
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

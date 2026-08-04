from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.barber import Barber
from ..models.barber_service import BarberService
from ..models.service import Service
from ..schemas.service import ServiceOfferingRead

router = APIRouter(prefix="/services", tags=["services"])


def offering_response(
    *,
    service_id: int,
    service_name: str,
    duration: int,
    price,
    active: bool,
    barber_id: int | None = None,
    is_from_price: bool = False,
) -> ServiceOfferingRead:
    return ServiceOfferingRead(
        barber_id=barber_id,
        service_id=service_id,
        service_name=service_name,
        duration=duration,
        price=price,
        active=active,
        is_from_price=is_from_price,
        id=service_id,
        name=service_name,
        duration_minutes=duration,
    )


@router.get("", response_model=list[ServiceOfferingRead])
def list_services(barber_id: int | None = Query(default=None), db: Session = Depends(get_db)):
    if barber_id is not None:
        rows = db.execute(
            select(BarberService, Service)
            .join(Service, Service.id == BarberService.service_id)
            .join(Barber, Barber.id == BarberService.barber_id)
            .where(
                BarberService.barber_id == barber_id,
                BarberService.active.is_(True),
                Service.active.is_(True),
                Barber.active.is_(True),
            )
            .order_by(Service.id)
        ).all()
        return [
            offering_response(
                barber_id=barber_service.barber_id,
                service_id=service.id,
                service_name=service.name,
                duration=service.duration_minutes,
                price=barber_service.price,
                active=barber_service.active,
            )
            for barber_service, service in rows
        ]

    rows = db.execute(
        select(
            Service.id,
            Service.name,
            Service.duration_minutes,
            func.min(BarberService.price).label("price"),
        )
        .join(BarberService, BarberService.service_id == Service.id)
        .join(Barber, Barber.id == BarberService.barber_id)
        .where(
            Service.active.is_(True),
            Barber.active.is_(True),
            BarberService.active.is_(True),
        )
        .group_by(Service.id, Service.name, Service.duration_minutes)
        .order_by(Service.id)
    ).all()
    return [
        offering_response(
            service_id=service_id,
            service_name=service_name,
            duration=duration,
            price=price,
            active=True,
            is_from_price=True,
        )
        for service_id, service_name, duration, price in rows
    ]

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.barber import Barber
from ..models.barber_service import BarberService
from ..models.service import Service
from ..schemas.service import ServiceOfferingRead

router = APIRouter(prefix="/services", tags=["services"])


def deposit_value(price, requires_deposit: bool, deposit_type: str | None, amount, percentage):
    if not requires_deposit:
        return None
    if deposit_type == "fijo":
        return amount
    if deposit_type == "porcentaje" and price is not None and percentage is not None:
        return price * percentage / 100
    return None


def remaining_balance(price, deposit):
    if price is None or deposit is None:
        return None
    return max(price - deposit, 0)


def offering_response(
    *,
    service_id: int,
    service_name: str,
    price,
    duration_visible_minutes: int | None,
    blocking_duration_minutes: int,
    active: bool,
    requires_deposit: bool = False,
    deposit_type: str | None = None,
    deposit_amount=None,
    deposit_percentage=None,
    remaining_balance_amount=None,
    barber_id: int | None = None,
    is_from_price: bool = False,
    has_consultation_price: bool = False,
    duration_depends_on_professional: bool = False,
) -> ServiceOfferingRead:
    return ServiceOfferingRead(
        barber_id=barber_id,
        service_id=service_id,
        service_name=service_name,
        price=price,
        duration_visible_minutes=duration_visible_minutes,
        blocking_duration_minutes=blocking_duration_minutes,
        active=active,
        requires_deposit=requires_deposit,
        deposit_type=deposit_type,
        deposit_amount=deposit_amount,
        deposit_percentage=deposit_percentage,
        remaining_balance=remaining_balance_amount,
        is_from_price=is_from_price,
        has_consultation_price=has_consultation_price,
        duration_depends_on_professional=duration_depends_on_professional,
        id=service_id,
        name=service_name,
        duration_minutes=duration_visible_minutes,
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
                price=barber_service.price,
                duration_visible_minutes=barber_service.visible_duration_minutes,
                blocking_duration_minutes=barber_service.blocking_duration_minutes,
                active=barber_service.active,
                requires_deposit=barber_service.requires_deposit,
                deposit_type=barber_service.deposit_type,
                deposit_amount=deposit_value(
                    barber_service.price,
                    barber_service.requires_deposit,
                    barber_service.deposit_type,
                    barber_service.deposit_amount,
                    barber_service.deposit_percentage,
                ),
                deposit_percentage=barber_service.deposit_percentage,
                remaining_balance_amount=remaining_balance(
                    barber_service.price,
                    deposit_value(
                        barber_service.price,
                        barber_service.requires_deposit,
                        barber_service.deposit_type,
                        barber_service.deposit_amount,
                        barber_service.deposit_percentage,
                    ),
                ),
            )
            for barber_service, service in rows
        ]

    rows = db.execute(
        select(
            Service.id,
            Service.name,
            func.min(BarberService.price).label("price"),
            func.count(BarberService.id).label("offering_count"),
            func.sum(case((BarberService.price.is_(None), 1), else_=0)).label("consultation_count"),
            func.min(BarberService.visible_duration_minutes).label("min_visible_duration"),
            func.max(BarberService.visible_duration_minutes).label("max_visible_duration"),
            func.sum(case((BarberService.visible_duration_minutes.is_(None), 1), else_=0)).label("variable_duration_count"),
            func.min(BarberService.blocking_duration_minutes).label("min_blocking_duration"),
            func.sum(case((BarberService.requires_deposit.is_(True), 1), else_=0)).label("deposit_count"),
        )
        .join(BarberService, BarberService.service_id == Service.id)
        .join(Barber, Barber.id == BarberService.barber_id)
        .where(
            Service.active.is_(True),
            Barber.active.is_(True),
            BarberService.active.is_(True),
        )
        .group_by(Service.id, Service.name)
        .order_by(Service.id)
    ).all()
    responses = []
    for (
        service_id,
        service_name,
        price,
        offering_count,
        consultation_count,
        min_visible_duration,
        max_visible_duration,
        variable_duration_count,
        min_blocking_duration,
        deposit_count,
    ) in rows:
        has_consultation_price = bool(consultation_count)
        has_consultation_duration = bool(variable_duration_count)
        duration_depends = not has_consultation_duration and min_visible_duration != max_visible_duration
        visible_duration = None if has_consultation_duration or duration_depends else min_visible_duration
        responses.append(
            offering_response(
                service_id=service_id,
                service_name=service_name,
                price=None if has_consultation_price else price,
                duration_visible_minutes=visible_duration,
                blocking_duration_minutes=min_blocking_duration,
                active=True,
                requires_deposit=bool(deposit_count),
                is_from_price=not has_consultation_price and offering_count > 1,
                has_consultation_price=has_consultation_price,
                duration_depends_on_professional=duration_depends,
            )
        )
    return responses

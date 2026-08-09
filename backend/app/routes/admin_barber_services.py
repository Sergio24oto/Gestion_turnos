from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.barber import Barber
from ..models.barber_service import BarberService
from ..models.service import Service
from ..schemas.service import (
    BarberServiceAdminCreate,
    BarberServiceAdminRead,
    BarberServiceAdminUpdate,
    BarberServiceStatusUpdate,
)
from ..services.auth import require_admin

router = APIRouter(
    prefix="/admin/barbers/{barber_id}/services",
    tags=["admin-barber-services"],
    dependencies=[Depends(require_admin)],
)


def get_barber_or_404(db: Session, barber_id: int) -> Barber:
    barber = db.get(Barber, barber_id)
    if not barber:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Peluquero no encontrado.")
    return barber


def get_service_or_404(db: Session, service_id: int) -> Service:
    service = db.get(Service, service_id)
    if not service:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Servicio no encontrado.")
    return service


def get_relation(db: Session, barber_id: int, service_id: int) -> BarberService | None:
    return db.scalar(
        select(BarberService).where(
            BarberService.barber_id == barber_id,
            BarberService.service_id == service_id,
        )
    )


def relation_to_read(barber: Barber, service: Service, relation: BarberService | None) -> BarberServiceAdminRead:
    return BarberServiceAdminRead(
        barber_id=barber.id,
        service_id=service.id,
        service_name=service.name,
        service_description=service.description,
        service_category=service.category,
        service_active=service.active,
        assigned=relation is not None,
        price=relation.price if relation else None,
        duration_visible_minutes=relation.visible_duration_minutes if relation else None,
        blocking_duration_minutes=relation.blocking_duration_minutes if relation else barber.appointment_interval_minutes,
        active=relation.active if relation else False,
        requires_deposit=relation.requires_deposit if relation else False,
        deposit_type=relation.deposit_type if relation else None,
        deposit_amount=relation.deposit_amount if relation else None,
        deposit_percentage=relation.deposit_percentage if relation else None,
        created_at=relation.created_at if relation else None,
        updated_at=relation.updated_at if relation else None,
    )


def validate_deposit_config(
    *,
    requires_deposit: bool,
    deposit_type: str | None,
    deposit_amount,
    deposit_percentage,
    service_price,
) -> None:
    if not requires_deposit:
        return
    if deposit_type not in ("fijo", "porcentaje"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Seleccioná un tipo de seña válido.")
    if deposit_type == "fijo" and deposit_amount is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Ingresá el monto fijo de la seña.")
    if deposit_type == "porcentaje":
        if deposit_percentage is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Ingresá el porcentaje de la seña.")
        if service_price is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "No se puede usar seña porcentual con precio a consultar.")


@router.get("", response_model=list[BarberServiceAdminRead])
def list_barber_services(barber_id: int, db: Session = Depends(get_db)):
    barber = get_barber_or_404(db, barber_id)
    services = db.scalars(select(Service).order_by(Service.active.desc(), Service.name)).all()
    relations = {
        relation.service_id: relation
        for relation in db.scalars(select(BarberService).where(BarberService.barber_id == barber_id)).all()
    }
    return [relation_to_read(barber, service, relations.get(service.id)) for service in services]


@router.post("", response_model=BarberServiceAdminRead, status_code=201)
def assign_barber_service(
    barber_id: int,
    payload: BarberServiceAdminCreate,
    db: Session = Depends(get_db),
):
    barber = get_barber_or_404(db, barber_id)
    service = get_service_or_404(db, payload.service_id)
    if get_relation(db, barber_id, payload.service_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El servicio ya está configurado para este peluquero.")
    relation = BarberService(
        barber_id=barber_id,
        service_id=payload.service_id,
        price=payload.price,
        visible_duration_minutes=payload.duration_visible_minutes,
        blocking_duration_minutes=payload.blocking_duration_minutes,
        active=payload.active,
        requires_deposit=payload.requires_deposit,
        deposit_type=payload.deposit_type if payload.requires_deposit else None,
        deposit_amount=payload.deposit_amount if payload.requires_deposit and payload.deposit_type == "fijo" else None,
        deposit_percentage=payload.deposit_percentage if payload.requires_deposit and payload.deposit_type == "porcentaje" else None,
    )
    validate_deposit_config(
        requires_deposit=relation.requires_deposit,
        deposit_type=relation.deposit_type,
        deposit_amount=relation.deposit_amount,
        deposit_percentage=relation.deposit_percentage,
        service_price=relation.price,
    )
    db.add(relation)
    db.commit()
    db.refresh(relation)
    return relation_to_read(barber, service, relation)


@router.patch("/{service_id}", response_model=BarberServiceAdminRead)
def update_barber_service(
    barber_id: int,
    service_id: int,
    payload: BarberServiceAdminUpdate,
    db: Session = Depends(get_db),
):
    barber = get_barber_or_404(db, barber_id)
    service = get_service_or_404(db, service_id)
    relation = get_relation(db, barber_id, service_id)
    if not relation:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El servicio no está configurado para este peluquero.")
    data = payload.model_dump(exclude_unset=True)
    if "price" in data:
        relation.price = data["price"]
    if "duration_visible_minutes" in data:
        relation.visible_duration_minutes = data["duration_visible_minutes"]
    if "blocking_duration_minutes" in data and data["blocking_duration_minutes"] is not None:
        relation.blocking_duration_minutes = data["blocking_duration_minutes"]
    if "active" in data:
        relation.active = data["active"]
    if "requires_deposit" in data:
        relation.requires_deposit = data["requires_deposit"]
    if "deposit_type" in data:
        relation.deposit_type = data["deposit_type"]
    if "deposit_amount" in data:
        relation.deposit_amount = data["deposit_amount"]
    if "deposit_percentage" in data:
        relation.deposit_percentage = data["deposit_percentage"]
    if not relation.requires_deposit:
        relation.deposit_type = None
        relation.deposit_amount = None
        relation.deposit_percentage = None
    elif relation.deposit_type == "fijo":
        relation.deposit_percentage = None
    elif relation.deposit_type == "porcentaje":
        relation.deposit_amount = None
    validate_deposit_config(
        requires_deposit=relation.requires_deposit,
        deposit_type=relation.deposit_type,
        deposit_amount=relation.deposit_amount,
        deposit_percentage=relation.deposit_percentage,
        service_price=relation.price,
    )
    relation.updated_at = datetime.now()
    db.commit()
    db.refresh(relation)
    return relation_to_read(barber, service, relation)


@router.patch("/{service_id}/status", response_model=BarberServiceAdminRead)
def update_barber_service_status(
    barber_id: int,
    service_id: int,
    payload: BarberServiceStatusUpdate,
    db: Session = Depends(get_db),
):
    barber = get_barber_or_404(db, barber_id)
    service = get_service_or_404(db, service_id)
    relation = get_relation(db, barber_id, service_id)
    if not relation:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El servicio no está configurado para este peluquero.")
    relation.active = payload.active
    relation.updated_at = datetime.now()
    db.commit()
    db.refresh(relation)
    return relation_to_read(barber, service, relation)

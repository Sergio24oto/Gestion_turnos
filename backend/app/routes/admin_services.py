from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.appointment import Appointment
from ..models.barber import Barber
from ..models.barber_service import BarberService
from ..models.service import Service
from ..schemas.service import (
    ServiceAdminCreate,
    ServiceAdminRead,
    ServiceAdminUpdate,
    ServiceStatusUpdate,
)
from ..services.auth import require_admin

router = APIRouter(prefix="/admin/services", tags=["admin-services"], dependencies=[Depends(require_admin)])


def normalized_service_name(value: str) -> str:
    return " ".join(str(value or "").strip().split()).casefold()


def get_service_or_404(db: Session, service_id: int) -> Service:
    service = db.get(Service, service_id)
    if not service:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Servicio no encontrado.")
    return service


def ensure_unique_name(db: Session, name: str, current_service_id: int | None = None) -> None:
    services = db.execute(select(Service.id, Service.name)).all()
    requested = normalized_service_name(name)
    for service_id, service_name in services:
        if current_service_id is not None and service_id == current_service_id:
            continue
        if normalized_service_name(service_name) == requested:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Ya existe un servicio con ese nombre.")


def active_assigned_barbers(db: Session, service_id: int) -> list[str]:
    return list(
        db.scalars(
            select(Barber.name)
            .join(BarberService, BarberService.barber_id == Barber.id)
            .where(
                BarberService.service_id == service_id,
                BarberService.active.is_(True),
                Barber.active.is_(True),
            )
            .order_by(Barber.order, Barber.id)
        ).all()
    )


def service_counts(db: Session, service_id: int) -> tuple[int, int, list[str]]:
    assigned_barbers = active_assigned_barbers(db, service_id)
    future_appointments_count = db.scalar(
        select(func.count(Appointment.id)).where(
            Appointment.service_id == service_id,
            Appointment.date >= date.today(),
            Appointment.status != "Cancelado",
        )
    )
    return len(assigned_barbers), int(future_appointments_count or 0), assigned_barbers


def service_to_read(db: Session, service: Service) -> ServiceAdminRead:
    assigned_barbers_count, future_appointments_count, assigned_barbers = service_counts(db, service.id)
    return ServiceAdminRead(
        id=service.id,
        name=service.name,
        description=service.description,
        category=service.category,
        active=service.active,
        assigned_barbers_count=assigned_barbers_count,
        assigned_barbers=assigned_barbers,
        future_appointments_count=future_appointments_count,
        created_at=service.created_at,
        updated_at=service.updated_at,
    )


@router.get("", response_model=list[ServiceAdminRead])
def list_admin_services(db: Session = Depends(get_db)):
    services = db.scalars(select(Service).order_by(Service.active.desc(), Service.name)).all()
    return [service_to_read(db, service) for service in services]


@router.post("", response_model=ServiceAdminRead, status_code=201)
def create_admin_service(payload: ServiceAdminCreate, db: Session = Depends(get_db)):
    ensure_unique_name(db, payload.name)
    service = Service(
        name=payload.name,
        description=payload.description,
        category=payload.category,
        active=payload.active,
    )
    db.add(service)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No se pudo crear el servicio.")
    db.refresh(service)
    return service_to_read(db, service)


@router.patch("/{service_id}", response_model=ServiceAdminRead)
def update_admin_service(service_id: int, payload: ServiceAdminUpdate, db: Session = Depends(get_db)):
    service = get_service_or_404(db, service_id)
    data = payload.model_dump(exclude_unset=True)
    if "name" in data:
        ensure_unique_name(db, data["name"], current_service_id=service_id)
        service.name = data["name"]
    if "description" in data:
        service.description = data["description"]
    if "category" in data:
        service.category = data["category"]
    if "active" in data:
        service.active = data["active"]
    service.updated_at = datetime.now()
    db.commit()
    db.refresh(service)
    return service_to_read(db, service)


@router.patch("/{service_id}/status", response_model=ServiceAdminRead)
def update_admin_service_status(service_id: int, payload: ServiceStatusUpdate, db: Session = Depends(get_db)):
    service = get_service_or_404(db, service_id)
    service.active = payload.active
    service.updated_at = datetime.now()
    db.commit()
    db.refresh(service)
    return service_to_read(db, service)

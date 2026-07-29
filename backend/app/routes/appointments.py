from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas.appointment import (
    AgendaSlot,
    AppointmentCreate,
    AppointmentRead,
    ManualAppointmentCreate,
    PublicAppointmentCreated,
    PublicCancellationAppointment,
)
from ..services.auth import require_admin
from ..services.schedule import (
    appointment_by_cancellation_token,
    appointment_to_public_cancellation,
    appointment_to_read,
    cancel_appointment,
    cancel_appointment_by_token,
    create_appointment,
    daily_agenda,
)

router = APIRouter(prefix="/appointments", tags=["appointments"])


@router.post("", response_model=PublicAppointmentCreated, status_code=201)
def create_public_appointment(payload: AppointmentCreate, db: Session = Depends(get_db)):
    appointment = create_appointment(db, payload, origin="APP")
    return PublicAppointmentCreated(
        **appointment_to_read(appointment).model_dump(),
        cancellation_token=appointment._cancellation_token,
    )


@router.post("/manual", response_model=AppointmentRead, status_code=201, dependencies=[Depends(require_admin)])
def create_manual_appointment(payload: ManualAppointmentCreate, db: Session = Depends(get_db)):
    return appointment_to_read(create_appointment(db, payload, origin="MANUAL"))


@router.get("/agenda", response_model=list[AgendaSlot], dependencies=[Depends(require_admin)])
def get_agenda(date_: date, db: Session = Depends(get_db)):
    return daily_agenda(db, date_)


@router.get("/cancel/{token}", response_model=PublicCancellationAppointment)
def get_public_cancellation(token: str, db: Session = Depends(get_db)):
    return appointment_to_public_cancellation(appointment_by_cancellation_token(db, token))


@router.patch("/cancel/{token}", response_model=PublicCancellationAppointment)
def cancel_public_appointment(token: str, db: Session = Depends(get_db)):
    return appointment_to_public_cancellation(cancel_appointment_by_token(db, token))


@router.patch("/{appointment_id}/cancel", response_model=AppointmentRead, dependencies=[Depends(require_admin)])
def cancel(appointment_id: int, db: Session = Depends(get_db)):
    return appointment_to_read(cancel_appointment(db, appointment_id))
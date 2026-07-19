from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas.appointment import AgendaSlot, AppointmentCreate, AppointmentRead, ManualAppointmentCreate
from ..services.auth import require_admin
from ..services.schedule import appointment_to_read, cancel_appointment, create_appointment, daily_agenda

router = APIRouter(prefix="/appointments", tags=["appointments"])


@router.post("", response_model=AppointmentRead, status_code=201)
def create_public_appointment(payload: AppointmentCreate, db: Session = Depends(get_db)):
    return appointment_to_read(create_appointment(db, payload, origin="APP"))


@router.post("/manual", response_model=AppointmentRead, status_code=201, dependencies=[Depends(require_admin)])
def create_manual_appointment(payload: ManualAppointmentCreate, db: Session = Depends(get_db)):
    return appointment_to_read(create_appointment(db, payload, origin="MANUAL"))


@router.get("/agenda", response_model=list[AgendaSlot], dependencies=[Depends(require_admin)])
def get_agenda(date_: date, db: Session = Depends(get_db)):
    return daily_agenda(db, date_)


@router.patch("/{appointment_id}/cancel", response_model=AppointmentRead, dependencies=[Depends(require_admin)])
def cancel(appointment_id: int, db: Session = Depends(get_db)):
    return appointment_to_read(cancel_appointment(db, appointment_id))

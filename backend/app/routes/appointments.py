from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas.appointment import (
    AgendaSlot,
    AppointmentCreationResponse,
    AppointmentCreate,
    AppointmentRead,
    ManualAppointmentCreate,
    PublicCancellationAppointment,
)
from ..models.appointment import STATUS_EXPIRED, STATUS_PENDING_PAYMENT
from ..models.payment import PAYMENT_STATUS_CANCELLED
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
from ..services.payments import latest_payment, ensure_checkout_for_appointment

router = APIRouter(prefix="/appointments", tags=["appointments"])


@router.post("", response_model=AppointmentCreationResponse, status_code=201)
def create_public_appointment(payload: AppointmentCreate, db: Session = Depends(get_db)):
    appointment = create_appointment(db, payload, origin="APP")
    checkout = None
    payment_status_token = getattr(appointment, "_payment_status_token", None)
    if appointment.status == STATUS_PENDING_PAYMENT and payment_status_token:
        try:
            checkout = ensure_checkout_for_appointment(db, appointment, payment_status_token)
        except HTTPException as exc:
            payment = latest_payment(db, appointment.id)
            if payment:
                payment.status = PAYMENT_STATUS_CANCELLED
            appointment.status = STATUS_EXPIRED
            db.commit()
            raise exc
    appointment_read = appointment_to_read(appointment)
    return AppointmentCreationResponse(
        status=appointment.status,
        appointment=appointment_read,
        appointment_id=appointment.id,
        deposit_amount=appointment.deposit_amount,
        remaining_balance=appointment.remaining_balance,
        expires_at=appointment.payment_expires_at,
        cancellation_token=None if appointment.status == STATUS_PENDING_PAYMENT else appointment._cancellation_token,
        payment_status_token=payment_status_token,
        checkout_url=checkout.checkout_url if checkout else None,
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

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas.appointment import PaymentStartResponse, PublicPaymentStatus
from ..services.payments import (
    appointment_by_payment_status_token,
    build_payment_status,
    reconcile_payment_return,
    start_checkout_by_token,
)

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/appointments/{appointment_id}", response_model=PaymentStartResponse)
def start_payment(appointment_id: int, token: str, db: Session = Depends(get_db)):
    return start_checkout_by_token(db, appointment_id, token)


@router.get("/status/{token}", response_model=PublicPaymentStatus)
def get_payment_status(
    token: str,
    payment_id: str | None = Query(default=None),
    collection_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    appointment = appointment_by_payment_status_token(db, token)
    reconcile_payment_return(db, appointment, payment_id or collection_id)
    return build_payment_status(db, appointment)

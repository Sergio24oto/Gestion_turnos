from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas.appointment import AppointmentRead
from ..schemas.sales import SaleUpdate, SalesResponse
from ..services.auth import require_admin
from ..services.sales import list_sales, update_sale
from ..services.schedule import appointment_to_read

router = APIRouter(prefix="/admin/sales", tags=["admin-sales"], dependencies=[Depends(require_admin)])


@router.get("", response_model=SalesResponse)
def get_admin_sales(date_: date, db: Session = Depends(get_db)):
    return list_sales(db, date_)


@router.patch("/appointments/{appointment_id}", response_model=AppointmentRead)
def update_appointment_sale(appointment_id: int, payload: SaleUpdate, db: Session = Depends(get_db)):
    return appointment_to_read(update_sale(db, appointment_id, payload))

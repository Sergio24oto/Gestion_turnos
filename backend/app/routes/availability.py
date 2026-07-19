from datetime import date, time

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.schedule import available_slots

router = APIRouter(prefix="/availability", tags=["availability"])


@router.get("", response_model=list[time])
def get_availability(date_: date = Query(alias="date"), db: Session = Depends(get_db)):
    return available_slots(db, date_)

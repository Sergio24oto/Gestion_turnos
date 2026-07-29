from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.barber import Barber
from ..schemas.barber import BarberRead

router = APIRouter(prefix="/barbers", tags=["barbers"])


@router.get("", response_model=list[BarberRead])
def list_barbers(db: Session = Depends(get_db)):
    return db.scalars(select(Barber).where(Barber.active.is_(True)).order_by(Barber.order, Barber.id)).all()

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.service import Service
from ..schemas.service import ServiceRead

router = APIRouter(prefix="/services", tags=["services"])


@router.get("", response_model=list[ServiceRead])
def list_services(db: Session = Depends(get_db)):
    return db.scalars(select(Service).where(Service.active.is_(True)).order_by(Service.id)).all()

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class ServiceOfferingRead(BaseModel):
    barber_id: int | None = None
    service_id: int
    service_name: str
    price: Optional[Decimal] = Field(default=None, ge=Decimal("0"), max_digits=10, decimal_places=2)
    duration_visible_minutes: int | None = Field(default=None, gt=0)
    blocking_duration_minutes: int = Field(gt=0)
    active: bool
    is_from_price: bool = False
    has_consultation_price: bool = False
    duration_depends_on_professional: bool = False
    id: int
    name: str
    duration_minutes: int | None = None

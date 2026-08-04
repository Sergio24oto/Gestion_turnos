from decimal import Decimal

from pydantic import BaseModel, Field


class ServiceOfferingRead(BaseModel):
    barber_id: int | None = None
    service_id: int
    service_name: str
    duration: int
    price: Decimal = Field(ge=Decimal("0"), max_digits=10, decimal_places=2)
    active: bool
    is_from_price: bool = False
    id: int
    name: str
    duration_minutes: int

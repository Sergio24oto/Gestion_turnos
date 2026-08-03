from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ServiceRead(BaseModel):
    id: int
    name: str
    duration_minutes: int
    price: Decimal = Field(ge=Decimal("0"), max_digits=10, decimal_places=2)
    active: bool

    model_config = ConfigDict(from_attributes=True)

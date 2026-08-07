from pydantic import BaseModel, ConfigDict


class BarberRead(BaseModel):
    id: int
    name: str
    description: str | None = None
    photo_url: str | None = None
    active: bool
    order: int
    appointment_interval_minutes: int

    model_config = ConfigDict(from_attributes=True)

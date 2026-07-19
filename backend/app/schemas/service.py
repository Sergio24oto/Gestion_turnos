from pydantic import BaseModel, ConfigDict


class ServiceRead(BaseModel):
    id: int
    name: str
    duration_minutes: int
    active: bool

    model_config = ConfigDict(from_attributes=True)

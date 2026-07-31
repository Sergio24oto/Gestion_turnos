from datetime import date, time

from pydantic import BaseModel, Field, field_validator


def normalize_phone(value: str) -> str:
    raw = str(value or "").strip()
    allowed_format_chars = set(" -()")
    if any(not char.isdigit() and char not in allowed_format_chars for char in raw):
        raise ValueError("Ingresá un teléfono válido de 10 u 11 números.")
    phone = "".join(char for char in raw if char.isdigit())
    if len(phone) not in (10, 11):
        raise ValueError("Ingresá un teléfono válido de 10 u 11 números.")
    return phone


class ClientInput(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    phone: str = Field(min_length=1, max_length=40)

    @field_validator("phone", mode="before")
    @classmethod
    def normalize_phone_value(cls, value: str) -> str:
        return normalize_phone(value)


class AppointmentCreate(BaseModel):
    service_id: int
    barber_id: int | None = None
    date: date
    start_time: time
    client: ClientInput


class ManualAppointmentCreate(AppointmentCreate):
    pass


class AppointmentRead(BaseModel):
    id: int
    date: date
    start_time: time
    status: str
    origin: str
    barber_id: int
    barber_name: str
    service_id: int
    service_name: str
    client_id: int
    client_first_name: str
    client_last_name: str
    client_phone: str


class PublicAppointmentCreated(AppointmentRead):
    cancellation_token: str


class PublicCancellationAppointment(BaseModel):
    date: date
    start_time: time
    status: str
    barber_name: str
    service_name: str
    client_first_name: str
    client_last_name: str


class AgendaSlot(BaseModel):
    time: time
    status: str
    barber_id: int | None = None
    barber_name: str | None = None
    appointment: AppointmentRead | None = None
    block_id: int | None = None
    block_reason: str | None = None


from datetime import date, time

from pydantic import BaseModel, Field


class ClientInput(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    phone: str = Field(min_length=1, max_length=40)


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


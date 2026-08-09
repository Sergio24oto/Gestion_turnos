from datetime import date, datetime, time
from decimal import Decimal
from typing import Optional

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
    end_time: time
    status: str
    origin: str
    barber_id: int
    barber_name: str
    service_id: int
    service_name: str
    service_price: Optional[Decimal] = Field(default=None, ge=Decimal("0"), max_digits=10, decimal_places=2)
    service_visible_duration_minutes: int | None = Field(default=None, gt=0)
    service_blocking_duration_minutes: int = Field(gt=0)
    deposit_amount: Optional[Decimal] = Field(default=None, ge=Decimal("0"), max_digits=10, decimal_places=2)
    remaining_balance: Optional[Decimal] = Field(default=None, ge=Decimal("0"), max_digits=10, decimal_places=2)
    payment_expires_at: datetime | None = None
    payment_status: str | None = None
    client_id: int
    client_first_name: str
    client_last_name: str
    client_phone: str


class PublicAppointmentCreated(AppointmentRead):
    cancellation_token: str


class AppointmentCreationResponse(BaseModel):
    status: str
    appointment: AppointmentRead | None = None
    appointment_id: int | None = None
    deposit_amount: Optional[Decimal] = Field(default=None, ge=Decimal("0"), max_digits=10, decimal_places=2)
    remaining_balance: Optional[Decimal] = Field(default=None, ge=Decimal("0"), max_digits=10, decimal_places=2)
    expires_at: datetime | None = None
    cancellation_token: str | None = None
    payment_status_token: str | None = None
    checkout_url: str | None = None


class PaymentStartResponse(BaseModel):
    status: str
    appointment_id: int
    deposit_amount: Optional[Decimal] = Field(default=None, ge=Decimal("0"), max_digits=10, decimal_places=2)
    expires_at: datetime | None = None
    payment_status_token: str
    checkout_url: str


class PublicPaymentStatus(BaseModel):
    appointment_status: str
    payment_status: str | None = None
    deposit_amount: Optional[Decimal] = Field(default=None, ge=Decimal("0"), max_digits=10, decimal_places=2)
    remaining_balance: Optional[Decimal] = Field(default=None, ge=Decimal("0"), max_digits=10, decimal_places=2)
    expires_at: datetime | None = None
    barber_name: str
    service_name: str
    date: date
    start_time: time
    end_time: time
    checkout_url: str | None = None


class PublicCancellationAppointment(BaseModel):
    date: date
    start_time: time
    end_time: time
    status: str
    barber_name: str
    service_name: str
    service_price: Optional[Decimal] = Field(default=None, ge=Decimal("0"), max_digits=10, decimal_places=2)
    service_visible_duration_minutes: int | None = Field(default=None, gt=0)
    service_blocking_duration_minutes: int = Field(gt=0)
    deposit_amount: Optional[Decimal] = Field(default=None, ge=Decimal("0"), max_digits=10, decimal_places=2)
    remaining_balance: Optional[Decimal] = Field(default=None, ge=Decimal("0"), max_digits=10, decimal_places=2)
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

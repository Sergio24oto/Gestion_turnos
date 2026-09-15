from datetime import date, time
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class SaleUpdate(BaseModel):
    sale_amount: Optional[Decimal] = Field(default=None, ge=Decimal("0"), max_digits=10, decimal_places=2)
    payment_method: str


class SaleAppointmentRead(BaseModel):
    appointment_id: int
    date: date
    start_time: time
    status: str
    origin: str
    barber_id: int
    barber_name: str
    service_name: str
    service_price: Optional[Decimal] = Field(default=None, ge=Decimal("0"), max_digits=10, decimal_places=2)
    sale_amount: Optional[Decimal] = Field(default=None, ge=Decimal("0"), max_digits=10, decimal_places=2)
    payment_method: str
    client_name: str


class SalesBarberSummary(BaseModel):
    barber_id: int
    barber_name: str
    appointments_count: int
    total_sold: Decimal = Field(ge=Decimal("0"), max_digits=12, decimal_places=2)
    cash_total: Decimal = Field(ge=Decimal("0"), max_digits=12, decimal_places=2)
    transfer_total: Decimal = Field(ge=Decimal("0"), max_digits=12, decimal_places=2)
    unregistered_total: Decimal = Field(ge=Decimal("0"), max_digits=12, decimal_places=2)
    pending_amount_count: int


class SalesResponse(BaseModel):
    date: date
    week_start: date
    week_end: date
    daily_total: Decimal = Field(ge=Decimal("0"), max_digits=12, decimal_places=2)
    weekly_total: Decimal = Field(ge=Decimal("0"), max_digits=12, decimal_places=2)
    cash_total: Decimal = Field(ge=Decimal("0"), max_digits=12, decimal_places=2)
    transfer_total: Decimal = Field(ge=Decimal("0"), max_digits=12, decimal_places=2)
    unregistered_total: Decimal = Field(ge=Decimal("0"), max_digits=12, decimal_places=2)
    pending_amount_count: int
    barbers: list[SalesBarberSummary]
    appointments: list[SaleAppointmentRead]

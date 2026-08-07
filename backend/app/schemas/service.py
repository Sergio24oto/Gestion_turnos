from decimal import Decimal
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


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


def clean_required_name(value: str) -> str:
    cleaned = " ".join(str(value or "").strip().split())
    if not cleaned:
        raise ValueError("El nombre del servicio es obligatorio.")
    return cleaned


def clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(str(value).strip().split())
    return cleaned or None


class ServiceAdminBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=255)
    category: str | None = Field(default=None, max_length=80)
    active: bool = True

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return clean_required_name(value)

    @field_validator("description", "category", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return clean_optional_text(value)


class ServiceAdminCreate(ServiceAdminBase):
    pass


class ServiceAdminUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=255)
    category: str | None = Field(default=None, max_length=80)
    active: bool | None = None

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return clean_required_name(value)

    @field_validator("description", "category", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return clean_optional_text(value)


class ServiceStatusUpdate(BaseModel):
    active: bool


class ServiceAdminRead(BaseModel):
    id: int
    name: str
    description: str | None = None
    category: str | None = None
    active: bool
    assigned_barbers_count: int
    future_appointments_count: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


class BarberServiceAdminRead(BaseModel):
    barber_id: int
    service_id: int
    service_name: str
    service_description: str | None = None
    service_category: str | None = None
    service_active: bool
    assigned: bool
    price: Optional[Decimal] = Field(default=None, ge=Decimal("0"), max_digits=10, decimal_places=2)
    duration_visible_minutes: int | None = Field(default=None, gt=0)
    blocking_duration_minutes: int = Field(gt=0)
    active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class BarberServiceAdminCreate(BaseModel):
    service_id: int
    price: Optional[Decimal] = Field(default=None, ge=Decimal("0"), max_digits=10, decimal_places=2)
    duration_visible_minutes: int | None = Field(default=None, gt=0)
    blocking_duration_minutes: int = Field(gt=0)
    active: bool = True


class BarberServiceAdminUpdate(BaseModel):
    price: Optional[Decimal] = Field(default=None, ge=Decimal("0"), max_digits=10, decimal_places=2)
    duration_visible_minutes: int | None = Field(default=None, gt=0)
    blocking_duration_minutes: int | None = Field(default=None, gt=0)
    active: bool | None = None


class BarberServiceStatusUpdate(BaseModel):
    active: bool

from datetime import date, datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.appointment import (
    LEGACY_STATUS_COMPLETED,
    LEGACY_STATUS_CONFIRMED,
    PAYMENT_METHOD_CASH,
    PAYMENT_METHOD_TRANSFER,
    PAYMENT_METHOD_UNREGISTERED,
    STATUS_COMPLETED,
    STATUS_CONFIRMED,
    Appointment,
)
from ..models.barber import Barber
from ..schemas.sales import SaleAppointmentRead, SaleUpdate, SalesBarberSummary, SalesResponse

SALE_STATUSES = (STATUS_CONFIRMED, STATUS_COMPLETED, LEGACY_STATUS_CONFIRMED, LEGACY_STATUS_COMPLETED)
PAYMENT_METHODS = (PAYMENT_METHOD_UNREGISTERED, PAYMENT_METHOD_CASH, PAYMENT_METHOD_TRANSFER)
ZERO = Decimal("0.00")


def week_range(selected_date: date) -> tuple[date, date]:
    days_since_tuesday = (selected_date.weekday() - 1) % 7
    week_start = selected_date - timedelta(days=days_since_tuesday)
    return week_start, week_start + timedelta(days=6)


def sale_value(appointment: Appointment) -> Decimal:
    return appointment.sale_amount or ZERO


def sale_to_read(appointment: Appointment) -> SaleAppointmentRead:
    return SaleAppointmentRead(
        appointment_id=appointment.id,
        date=appointment.date,
        start_time=appointment.start_time,
        status=appointment.status,
        origin=appointment.origin,
        barber_id=appointment.barber_id,
        barber_name=appointment.barber.name,
        service_name=appointment.service.name,
        service_price=appointment.service_price,
        sale_amount=appointment.sale_amount,
        payment_method=appointment.payment_method,
        client_name=f"{appointment.client.first_name} {appointment.client.last_name}".strip(),
    )


def empty_barber_summary(barber: Barber) -> SalesBarberSummary:
    return SalesBarberSummary(
        barber_id=barber.id,
        barber_name=barber.name,
        appointments_count=0,
        total_sold=ZERO,
        cash_total=ZERO,
        transfer_total=ZERO,
        unregistered_total=ZERO,
        pending_amount_count=0,
    )


def add_to_summary(summary: SalesBarberSummary, appointment: Appointment) -> None:
    amount = sale_value(appointment)
    summary.appointments_count += 1
    summary.total_sold += amount
    if appointment.sale_amount is None:
        summary.pending_amount_count += 1
    elif appointment.payment_method == PAYMENT_METHOD_CASH:
        summary.cash_total += amount
    elif appointment.payment_method == PAYMENT_METHOD_TRANSFER:
        summary.transfer_total += amount
    else:
        summary.unregistered_total += amount


def list_sales(db: Session, selected_date: date) -> SalesResponse:
    week_start, week_end = week_range(selected_date)
    barbers = db.scalars(select(Barber).order_by(Barber.order, Barber.id)).all()
    appointments = db.scalars(
        select(Appointment)
        .where(Appointment.date == selected_date, Appointment.status.in_(SALE_STATUSES))
        .order_by(Appointment.barber_id, Appointment.start_time, Appointment.id)
    ).all()
    weekly_appointments = db.scalars(
        select(Appointment).where(
            Appointment.date >= week_start,
            Appointment.date <= week_end,
            Appointment.status.in_(SALE_STATUSES),
        )
    ).all()

    summaries = {barber.id: empty_barber_summary(barber) for barber in barbers}
    daily_total = ZERO
    cash_total = ZERO
    transfer_total = ZERO
    unregistered_total = ZERO
    pending_amount_count = 0

    for appointment in appointments:
        if appointment.barber_id not in summaries:
            summaries[appointment.barber_id] = empty_barber_summary(appointment.barber)
        add_to_summary(summaries[appointment.barber_id], appointment)
        amount = sale_value(appointment)
        daily_total += amount
        if appointment.sale_amount is None:
            pending_amount_count += 1
        elif appointment.payment_method == PAYMENT_METHOD_CASH:
            cash_total += amount
        elif appointment.payment_method == PAYMENT_METHOD_TRANSFER:
            transfer_total += amount
        else:
            unregistered_total += amount

    return SalesResponse(
        date=selected_date,
        week_start=week_start,
        week_end=week_end,
        daily_total=daily_total,
        weekly_total=sum((sale_value(appointment) for appointment in weekly_appointments), ZERO),
        cash_total=cash_total,
        transfer_total=transfer_total,
        unregistered_total=unregistered_total,
        pending_amount_count=pending_amount_count,
        barbers=list(summaries.values()),
        appointments=[sale_to_read(appointment) for appointment in appointments],
    )


def update_sale(db: Session, appointment_id: int, payload: SaleUpdate) -> Appointment:
    if payload.payment_method not in PAYMENT_METHODS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Seleccioná un método de pago válido.")
    appointment = db.get(Appointment, appointment_id)
    if not appointment:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Turno no encontrado.")
    if appointment.status not in SALE_STATUSES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Solo se pueden editar ventas de turnos confirmados o completados.")
    appointment.sale_amount = payload.sale_amount
    appointment.payment_method = payload.payment_method
    appointment.sale_updated_at = datetime.now()
    db.commit()
    db.refresh(appointment)
    return appointment

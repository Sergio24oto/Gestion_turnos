from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
from secrets import token_urlsafe
from zoneinfo import ZoneInfo
from zoneinfo._common import ZoneInfoNotFoundError

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..models.appointment import Appointment
from ..models.appointment import (
    BLOCKING_CONFIRMED_STATUSES,
    CANCELLED_STATUSES,
    LEGACY_STATUS_CANCELLED,
    STATUS_CANCELLED,
    STATUS_CONFIRMED,
    STATUS_EXPIRED,
    STATUS_PENDING_PAYMENT,
)
from ..models.barber import Barber
from ..models.barber_service import BarberService
from ..models.block import BlockedSlot
from ..models.client import Client
from ..models.payment import PAYMENT_STATUS_PENDING, Payment
from ..models.service import Service
from ..schemas.appointment import AgendaSlot, AppointmentCreate, AppointmentRead, PublicCancellationAppointment
from ..schemas.block import BlockCreate

OPEN_RANGES = ((time(9, 0), time(13, 0)), (time(17, 0), time(21, 0)))
MIN_BOOKING_NOTICE_MINUTES = 20
try:
    ARGENTINA_TZ = ZoneInfo("America/Argentina/Cordoba")
except ZoneInfoNotFoundError:
    ARGENTINA_TZ = timezone(timedelta(hours=-3), "America/Argentina/Cordoba")


def minutes_of(value: time) -> int:
    return value.hour * 60 + value.minute


def time_from_minutes(value: int) -> time:
    return time((value // 60) % 24, value % 60)


def add_minutes(value: time, minutes: int) -> time:
    return time_from_minutes(minutes_of(value) + minutes)


def generate_slots(interval_minutes: int) -> list[time]:
    slots: list[time] = []
    for start, end in OPEN_RANGES:
        cursor_minutes = minutes_of(start)
        end_minutes = minutes_of(end)
        while cursor_minutes + interval_minutes <= end_minutes:
            slots.append(time_from_minutes(cursor_minutes))
            cursor_minutes += interval_minutes
    return slots


def slot_fits_open_range(slot_time: time, duration_minutes: int) -> bool:
    start_minutes = minutes_of(slot_time)
    end_minutes = start_minutes + duration_minutes
    return any(minutes_of(start) <= start_minutes and end_minutes <= minutes_of(end) for start, end in OPEN_RANGES)


def now_in_argentina() -> datetime:
    return datetime.now(ARGENTINA_TZ)


def slot_datetime(slot_date: date, slot_time: time) -> datetime:
    return datetime.combine(slot_date, slot_time, tzinfo=ARGENTINA_TZ)


def is_future_slot(slot_date: date, slot_time: time) -> bool:
    minimum_start = now_in_argentina().replace(second=0, microsecond=0) + timedelta(
        minutes=MIN_BOOKING_NOTICE_MINUTES
    )
    return slot_datetime(slot_date, slot_time) >= minimum_start


def is_past_slot(slot_date: date, slot_time: time) -> bool:
    return slot_datetime(slot_date, slot_time) < now_in_argentina()


def naive_now_for_db() -> datetime:
    return now_in_argentina().replace(tzinfo=None)


def ranges_overlap(start_a: time, duration_a: int, start_b: time, duration_b: int) -> bool:
    a_start = minutes_of(start_a)
    a_end = a_start + duration_a
    b_start = minutes_of(start_b)
    b_end = b_start + duration_b
    return a_start < b_end and a_end > b_start


def validate_open_day(slot_date: date) -> None:
    if slot_date.weekday() not in (1, 2, 3, 4, 5):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Solo se permiten turnos de martes a sabado.")


def validate_slot(slot_date: date, slot_time: time, barber: Barber, blocking_duration_minutes: int) -> None:
    validate_open_day(slot_date)
    if slot_time not in generate_slots(barber.appointment_interval_minutes):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El horario esta fuera de la atencion disponible.")
    if not slot_fits_open_range(slot_time, blocking_duration_minutes):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El servicio no entra completo dentro del horario de atencion.")
    if not is_future_slot(slot_date, slot_time):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "El horario seleccionado ya paso o no cumple con los 20 minutos minimos de anticipacion.",
        )


def active_barbers(db: Session, service_id: int | None = None) -> list[Barber]:
    statement = select(Barber).where(Barber.active.is_(True))
    if service_id is not None:
        statement = statement.join(BarberService, BarberService.barber_id == Barber.id).where(
            BarberService.service_id == service_id,
            BarberService.active.is_(True),
        )
    return db.scalars(statement.order_by(Barber.order, Barber.id)).all()


def get_active_barber(db: Session, barber_id: int) -> Barber:
    barber = db.get(Barber, barber_id)
    if not barber or not barber.active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Peluquero no encontrado.")
    return barber


def get_active_barber_service(db: Session, barber_id: int, service_id: int) -> BarberService:
    offering = db.scalar(
        select(BarberService)
        .join(Service, Service.id == BarberService.service_id)
        .join(Barber, Barber.id == BarberService.barber_id)
        .where(
            BarberService.barber_id == barber_id,
            BarberService.service_id == service_id,
            BarberService.active.is_(True),
            Service.active.is_(True),
            Barber.active.is_(True),
        )
    )
    if not offering:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Servicio no disponible para ese peluquero.")
    return offering


def expire_pending_payments(db: Session) -> None:
    expired = db.scalars(
        select(Appointment).where(
            Appointment.status == STATUS_PENDING_PAYMENT,
            Appointment.payment_expires_at.is_not(None),
            Appointment.payment_expires_at <= naive_now_for_db(),
        )
    ).all()
    if not expired:
        return
    for appointment in expired:
        appointment.status = STATUS_EXPIRED
    db.commit()


def is_blocking_appointment(appointment: Appointment) -> bool:
    if appointment.status in BLOCKING_CONFIRMED_STATUSES:
        return True
    if appointment.status == STATUS_PENDING_PAYMENT:
        return bool(appointment.payment_expires_at and appointment.payment_expires_at > naive_now_for_db())
    return False


def calculate_deposit(offering: BarberService) -> tuple[Decimal | None, Decimal | None]:
    if not offering.requires_deposit:
        return None, None
    if offering.deposit_type == "fijo":
        if offering.deposit_amount is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "La seña fija no está configurada.")
        deposit = offering.deposit_amount
    elif offering.deposit_type == "porcentaje":
        if offering.price is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "No se puede calcular una seña porcentual con precio a consultar.")
        if offering.deposit_percentage is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "El porcentaje de seña no está configurado.")
        deposit = (offering.price * offering.deposit_percentage / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    else:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El tipo de seña no está configurado.")
    balance = None if offering.price is None else max(offering.price - deposit, Decimal("0.00"))
    return deposit, balance


def appointment_end_time(appointment: Appointment) -> time:
    return add_minutes(appointment.start_time, appointment.service_blocking_duration_minutes)


def latest_payment_status(appointment: Appointment) -> str | None:
    if not appointment.payments:
        return None
    return sorted(appointment.payments, key=lambda payment: payment.id)[-1].status


def appointment_to_read(appointment: Appointment) -> AppointmentRead:
    return AppointmentRead(
        id=appointment.id,
        date=appointment.date,
        start_time=appointment.start_time,
        end_time=appointment_end_time(appointment),
        status=appointment.status,
        origin=appointment.origin,
        barber_id=appointment.barber_id,
        barber_name=appointment.barber.name,
        service_id=appointment.service_id,
        service_name=appointment.service.name,
        service_price=appointment.service_price,
        service_visible_duration_minutes=appointment.service_visible_duration_minutes,
        service_blocking_duration_minutes=appointment.service_blocking_duration_minutes,
        deposit_amount=appointment.deposit_amount,
        remaining_balance=appointment.remaining_balance,
        payment_expires_at=appointment.payment_expires_at,
        payment_status=latest_payment_status(appointment),
        client_id=appointment.client_id,
        client_first_name=appointment.client.first_name,
        client_last_name=appointment.client.last_name,
        client_phone=appointment.client.phone,
    )


def appointment_to_public_cancellation(appointment: Appointment) -> PublicCancellationAppointment:
    return PublicCancellationAppointment(
        date=appointment.date,
        start_time=appointment.start_time,
        end_time=appointment_end_time(appointment),
        status=appointment.status,
        barber_name=appointment.barber.name,
        service_name=appointment.service.name,
        service_price=appointment.service_price,
        service_visible_duration_minutes=appointment.service_visible_duration_minutes,
        service_blocking_duration_minutes=appointment.service_blocking_duration_minutes,
        deposit_amount=appointment.deposit_amount,
        remaining_balance=appointment.remaining_balance,
        client_first_name=appointment.client.first_name,
        client_last_name=appointment.client.last_name,
    )


def hash_cancellation_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def generate_unique_cancellation_token(db: Session) -> tuple[str, str]:
    for _ in range(5):
        token = token_urlsafe(32)
        token_hash = hash_cancellation_token(token)
        exists = db.scalar(select(Appointment.id).where(Appointment.cancellation_token_hash == token_hash))
        if not exists:
            return token, token_hash
    raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "No se pudo generar el token de cancelacion.")


def generate_unique_payment_status_token(db: Session) -> tuple[str, str]:
    for _ in range(5):
        token = token_urlsafe(32)
        token_hash = hash_cancellation_token(token)
        exists = db.scalar(select(Appointment.id).where(Appointment.payment_status_token_hash == token_hash))
        if not exists:
            return token, token_hash
    raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "No se pudo generar el token de estado de pago.")


def occupied_appointment(
    db: Session,
    slot_date: date,
    slot_time: time,
    barber_id: int,
    blocking_duration_minutes: int,
) -> Appointment | None:
    expire_pending_payments(db)
    appointments = db.scalars(
        select(Appointment).where(
            Appointment.date == slot_date,
            Appointment.barber_id == barber_id,
        )
    ).all()
    return next(
        (
            appointment
            for appointment in appointments
            if is_blocking_appointment(appointment)
            if ranges_overlap(
                slot_time,
                blocking_duration_minutes,
                appointment.start_time,
                appointment.service_blocking_duration_minutes,
            )
        ),
        None,
    )


def overlapping_appointment_at_slot(db: Session, slot_date: date, slot_time: time, barber: Barber) -> Appointment | None:
    expire_pending_payments(db)
    appointments = db.scalars(
        select(Appointment).where(
            Appointment.date == slot_date,
            Appointment.barber_id == barber.id,
        )
    ).all()
    return next(
        (
            appointment
            for appointment in appointments
            if is_blocking_appointment(appointment)
            if ranges_overlap(
                slot_time,
                barber.appointment_interval_minutes,
                appointment.start_time,
                appointment.service_blocking_duration_minutes,
            )
        ),
        None,
    )


def occupied_block(db: Session, slot_date: date, slot_time: time) -> BlockedSlot | None:
    return db.scalar(select(BlockedSlot).where(BlockedSlot.date == slot_date, BlockedSlot.start_time == slot_time))


def is_barber_available(
    db: Session,
    slot_date: date,
    slot_time: time,
    barber: Barber,
    blocking_duration_minutes: int,
) -> bool:
    return not occupied_block(db, slot_date, slot_time) and not occupied_appointment(
        db,
        slot_date,
        slot_time,
        barber.id,
        blocking_duration_minutes,
    )


def ensure_available(
    db: Session,
    slot_date: date,
    slot_time: time,
    barber: Barber,
    blocking_duration_minutes: int,
) -> None:
    validate_slot(slot_date, slot_time, barber, blocking_duration_minutes)
    if not is_barber_available(db, slot_date, slot_time, barber, blocking_duration_minutes):
        raise HTTPException(status.HTTP_409_CONFLICT, "El horario ya no esta disponible para ese peluquero.")


def available_slots(db: Session, slot_date: date, barber_id: int | None = None, service_id: int | None = None) -> list[time]:
    expire_pending_payments(db)
    if slot_date.weekday() not in (1, 2, 3, 4, 5):
        return []

    if barber_id is not None:
        barber = get_active_barber(db, barber_id)
        offering = get_active_barber_service(db, barber_id, service_id) if service_id is not None else None
        blocking_duration = offering.blocking_duration_minutes if offering else barber.appointment_interval_minutes
        slots = {
            slot
            for slot in generate_slots(barber.appointment_interval_minutes)
            if is_future_slot(slot_date, slot) and slot_fits_open_range(slot, blocking_duration)
        }
        return sorted(
            slot
            for slot in slots
            if is_barber_available(db, slot_date, slot, barber, blocking_duration)
        )

    available: set[time] = set()
    for barber in active_barbers(db, service_id):
        offering = get_active_barber_service(db, barber.id, service_id) if service_id is not None else None
        blocking_duration = offering.blocking_duration_minutes if offering else barber.appointment_interval_minutes
        for slot in generate_slots(barber.appointment_interval_minutes):
            if (
                is_future_slot(slot_date, slot)
                and slot_fits_open_range(slot, blocking_duration)
                and is_barber_available(db, slot_date, slot, barber, blocking_duration)
            ):
                available.add(slot)
    return sorted(available)


def available_barbers_for_slot(db: Session, slot_date: date, slot_time: time, service_id: int) -> list[Barber]:
    validate_open_day(slot_date)
    candidates = []
    for barber in active_barbers(db, service_id):
        offering = get_active_barber_service(db, barber.id, service_id)
        if (
            slot_time in generate_slots(barber.appointment_interval_minutes)
            and slot_fits_open_range(slot_time, offering.blocking_duration_minutes)
            and is_future_slot(slot_date, slot_time)
            and is_barber_available(db, slot_date, slot_time, barber, offering.blocking_duration_minutes)
        ):
            candidates.append(barber)
    return candidates


def choose_available_barber(db: Session, slot_date: date, slot_time: time, service_id: int) -> Barber:
    candidates = available_barbers_for_slot(db, slot_date, slot_time, service_id)
    if not candidates:
        raise HTTPException(status.HTTP_409_CONFLICT, "El horario ya no esta disponible.")
    counts = dict(
        db.execute(
            select(Appointment.barber_id, func.count(Appointment.id))
            .where(Appointment.date == slot_date, Appointment.status.in_(BLOCKING_CONFIRMED_STATUSES + (STATUS_PENDING_PAYMENT,)))
            .group_by(Appointment.barber_id)
        ).all()
    )
    return sorted(candidates, key=lambda barber: (counts.get(barber.id, 0), barber.order, barber.id))[0]


def create_appointment(db: Session, payload: AppointmentCreate, origin: str) -> Appointment:
    expire_pending_payments(db)
    if payload.barber_id is not None:
        barber = get_active_barber(db, payload.barber_id)
    else:
        barber = choose_available_barber(db, payload.date, payload.start_time, payload.service_id)

    offering = get_active_barber_service(db, barber.id, payload.service_id)
    ensure_available(db, payload.date, payload.start_time, barber, offering.blocking_duration_minutes)

    client = Client(
        first_name=payload.client.first_name.strip(),
        last_name=payload.client.last_name.strip(),
        phone=payload.client.phone.strip(),
    )
    cancellation_token, cancellation_token_hash = generate_unique_cancellation_token(db)
    requires_payment = origin == "APP" and offering.requires_deposit
    payment_status_token, payment_status_token_hash = (
        generate_unique_payment_status_token(db) if requires_payment else (None, None)
    )
    deposit_amount, remaining_balance = calculate_deposit(offering) if requires_payment else (None, None)
    payment_expires_at = naive_now_for_db() + timedelta(minutes=settings.payment_reservation_minutes) if requires_payment else None
    appointment = Appointment(
        client=client,
        service=offering.service,
        barber=barber,
        service_price=offering.price,
        service_visible_duration_minutes=offering.visible_duration_minutes,
        service_blocking_duration_minutes=offering.blocking_duration_minutes,
        deposit_amount=deposit_amount,
        remaining_balance=remaining_balance,
        payment_expires_at=payment_expires_at,
        date=payload.date,
        start_time=payload.start_time,
        status=STATUS_PENDING_PAYMENT if requires_payment else STATUS_CONFIRMED,
        origin=origin,
        cancellation_token_hash=cancellation_token_hash,
        payment_status_token_hash=payment_status_token_hash,
    )
    appointment._cancellation_token = cancellation_token
    appointment._payment_status_token = payment_status_token
    db.add(appointment)
    if requires_payment:
        db.add(Payment(appointment=appointment, amount=deposit_amount, status=PAYMENT_STATUS_PENDING))
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "El horario ya fue reservado.")
    db.refresh(appointment)
    appointment._cancellation_token = cancellation_token
    appointment._payment_status_token = payment_status_token
    return appointment


def cancel_appointment(db: Session, appointment_id: int) -> Appointment:
    appointment = db.get(Appointment, appointment_id)
    if not appointment:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Turno no encontrado.")
    appointment.status = STATUS_CANCELLED
    db.commit()
    db.refresh(appointment)
    return appointment


def appointment_by_cancellation_token(db: Session, token: str) -> Appointment:
    appointment = db.scalar(
        select(Appointment).where(Appointment.cancellation_token_hash == hash_cancellation_token(token))
    )
    if not appointment:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Token de cancelacion invalido.")
    if appointment.status in CANCELLED_STATUSES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El turno ya fue cancelado.")
    if appointment.status == STATUS_EXPIRED:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La reserva ya venció.")
    if is_past_slot(appointment.date, appointment.start_time):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No se puede cancelar un turno pasado.")
    return appointment


def cancel_appointment_by_token(db: Session, token: str) -> Appointment:
    appointment = appointment_by_cancellation_token(db, token)
    appointment.status = STATUS_CANCELLED
    db.commit()
    db.refresh(appointment)
    return appointment


def create_block(db: Session, payload: BlockCreate) -> BlockedSlot:
    validate_open_day(payload.date)
    if payload.start_time not in {slot for barber in active_barbers(db) for slot in generate_slots(barber.appointment_interval_minutes)}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El horario esta fuera de la atencion disponible.")
    if not is_future_slot(payload.date, payload.start_time):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "El horario seleccionado ya paso o no cumple con los 20 minutos minimos de anticipacion.",
        )
    if occupied_block(db, payload.date, payload.start_time):
        raise HTTPException(status.HTTP_409_CONFLICT, "El horario ya esta bloqueado.")
    block = BlockedSlot(date=payload.date, start_time=payload.start_time, reason=payload.reason)
    db.add(block)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "El horario ya esta bloqueado.")
    db.refresh(block)
    return block


def delete_block(db: Session, block_id: int) -> None:
    block = db.get(BlockedSlot, block_id)
    if not block:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bloqueo no encontrado.")
    db.delete(block)
    db.commit()


def daily_agenda(db: Session, slot_date: date) -> list[AgendaSlot]:
    expire_pending_payments(db)
    barbers = active_barbers(db)
    blocks = {item.start_time: item for item in db.scalars(select(BlockedSlot).where(BlockedSlot.date == slot_date)).all()}
    agenda: list[AgendaSlot] = []
    for barber in barbers:
        for slot in generate_slots(barber.appointment_interval_minutes):
            appointment = overlapping_appointment_at_slot(db, slot_date, slot, barber)
            block = blocks.get(slot)
            if appointment:
                slot_status = "Pendiente de pago" if appointment.status == STATUS_PENDING_PAYMENT else "Reservado"
                agenda.append(
                    AgendaSlot(
                        time=slot,
                        status=slot_status,
                        barber_id=barber.id,
                        barber_name=barber.name,
                        appointment=appointment_to_read(appointment),
                    )
                )
            elif block:
                agenda.append(
                    AgendaSlot(
                        time=slot,
                        status="Bloqueado",
                        barber_id=barber.id,
                        barber_name=barber.name,
                        block_id=block.id,
                        block_reason=block.reason,
                    )
                )
            else:
                agenda.append(AgendaSlot(time=slot, status="Libre", barber_id=barber.id, barber_name=barber.name))
    return agenda

from datetime import date, datetime, time, timedelta, timezone
from hashlib import sha256
from secrets import token_urlsafe
from zoneinfo import ZoneInfo
from zoneinfo._common import ZoneInfoNotFoundError

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models.appointment import Appointment
from ..models.barber import Barber
from ..models.block import BlockedSlot
from ..models.client import Client
from ..models.service import Service
from ..schemas.appointment import AgendaSlot, AppointmentCreate, AppointmentRead, PublicCancellationAppointment
from ..schemas.block import BlockCreate

OPEN_RANGES = ((time(9, 0), time(13, 0)), (time(17, 0), time(21, 0)))
SLOT_MINUTES = 20
MIN_BOOKING_NOTICE_MINUTES = 20
try:
    ARGENTINA_TZ = ZoneInfo("America/Argentina/Cordoba")
except ZoneInfoNotFoundError:
    ARGENTINA_TZ = timezone(timedelta(hours=-3), "America/Argentina/Cordoba")


def generate_slots() -> list[time]:
    slots: list[time] = []
    for start, end in OPEN_RANGES:
        cursor_minutes = start.hour * 60 + start.minute
        end_minutes = end.hour * 60 + end.minute
        while cursor_minutes + SLOT_MINUTES <= end_minutes:
            slots.append(time(cursor_minutes // 60, cursor_minutes % 60))
            cursor_minutes += SLOT_MINUTES
    return slots


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


def validate_slot(slot_date: date, slot_time: time) -> None:
    if slot_date.weekday() not in (1, 2, 3, 4, 5):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Solo se permiten turnos de martes a sabado.")
    if slot_time not in generate_slots():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El horario esta fuera de la atencion disponible.")
    if not is_future_slot(slot_date, slot_time):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "El horario seleccionado ya paso o no cumple con los 20 minutos minimos de anticipacion.",
        )


def active_barbers(db: Session) -> list[Barber]:
    return db.scalars(select(Barber).where(Barber.active.is_(True)).order_by(Barber.order, Barber.id)).all()


def get_active_barber(db: Session, barber_id: int) -> Barber:
    barber = db.get(Barber, barber_id)
    if not barber or not barber.active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Peluquero no encontrado.")
    return barber


def appointment_to_read(appointment: Appointment) -> AppointmentRead:
    return AppointmentRead(
        id=appointment.id,
        date=appointment.date,
        start_time=appointment.start_time,
        status=appointment.status,
        origin=appointment.origin,
        barber_id=appointment.barber_id,
        barber_name=appointment.barber.name,
        service_id=appointment.service_id,
        service_name=appointment.service.name,
        client_id=appointment.client_id,
        client_first_name=appointment.client.first_name,
        client_last_name=appointment.client.last_name,
        client_phone=appointment.client.phone,
    )


def appointment_to_public_cancellation(appointment: Appointment) -> PublicCancellationAppointment:
    return PublicCancellationAppointment(
        date=appointment.date,
        start_time=appointment.start_time,
        status=appointment.status,
        barber_name=appointment.barber.name,
        service_name=appointment.service.name,
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


def occupied_appointment(db: Session, slot_date: date, slot_time: time, barber_id: int) -> Appointment | None:
    return db.scalar(
        select(Appointment).where(
            Appointment.date == slot_date,
            Appointment.start_time == slot_time,
            Appointment.barber_id == barber_id,
            Appointment.status != "Cancelado",
        )
    )


def occupied_block(db: Session, slot_date: date, slot_time: time) -> BlockedSlot | None:
    return db.scalar(select(BlockedSlot).where(BlockedSlot.date == slot_date, BlockedSlot.start_time == slot_time))


def is_barber_available(db: Session, slot_date: date, slot_time: time, barber_id: int) -> bool:
    return not occupied_block(db, slot_date, slot_time) and not occupied_appointment(db, slot_date, slot_time, barber_id)


def ensure_available(db: Session, slot_date: date, slot_time: time, barber_id: int) -> None:
    validate_slot(slot_date, slot_time)
    get_active_barber(db, barber_id)
    if not is_barber_available(db, slot_date, slot_time, barber_id):
        raise HTTPException(status.HTTP_409_CONFLICT, "El horario ya no esta disponible para ese peluquero.")


def available_slots(db: Session, slot_date: date, barber_id: int | None = None) -> list[time]:
    if slot_date.weekday() not in (1, 2, 3, 4, 5):
        return []
    slots = {slot for slot in generate_slots() if is_future_slot(slot_date, slot)}
    blocks = db.scalars(select(BlockedSlot).where(BlockedSlot.date == slot_date)).all()
    blocked = {item.start_time for item in blocks}
    slots -= blocked
    if barber_id is not None:
        get_active_barber(db, barber_id)
        appointments = db.scalars(
            select(Appointment).where(
                Appointment.date == slot_date,
                Appointment.barber_id == barber_id,
                Appointment.status != "Cancelado",
            )
        ).all()
        occupied = {item.start_time for item in appointments}
        return sorted(slots - occupied)

    barbers = active_barbers(db)
    if not barbers:
        return []
    appointments = db.scalars(
        select(Appointment).where(Appointment.date == slot_date, Appointment.status != "Cancelado")
    ).all()
    occupied_by_barber: dict[int, set[time]] = {barber.id: set() for barber in barbers}
    for appointment in appointments:
        occupied_by_barber.setdefault(appointment.barber_id, set()).add(appointment.start_time)
    available = {
        slot
        for slot in slots
        if any(slot not in occupied_by_barber.get(barber.id, set()) for barber in barbers)
    }
    return sorted(available)


def available_barbers_for_slot(db: Session, slot_date: date, slot_time: time) -> list[Barber]:
    validate_slot(slot_date, slot_time)
    return [barber for barber in active_barbers(db) if is_barber_available(db, slot_date, slot_time, barber.id)]


def choose_available_barber(db: Session, slot_date: date, slot_time: time) -> Barber:
    candidates = available_barbers_for_slot(db, slot_date, slot_time)
    if not candidates:
        raise HTTPException(status.HTTP_409_CONFLICT, "El horario ya no esta disponible.")
    counts = dict(
        db.execute(
            select(Appointment.barber_id, func.count(Appointment.id))
            .where(Appointment.date == slot_date, Appointment.status != "Cancelado")
            .group_by(Appointment.barber_id)
        ).all()
    )
    return sorted(candidates, key=lambda barber: (counts.get(barber.id, 0), barber.order, barber.id))[0]


def create_appointment(db: Session, payload: AppointmentCreate, origin: str) -> Appointment:
    service = db.get(Service, payload.service_id)
    if not service or not service.active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Servicio no encontrado.")

    barber = get_active_barber(db, payload.barber_id) if payload.barber_id is not None else choose_available_barber(
        db, payload.date, payload.start_time
    )
    ensure_available(db, payload.date, payload.start_time, barber.id)

    client = Client(
        first_name=payload.client.first_name.strip(),
        last_name=payload.client.last_name.strip(),
        phone=payload.client.phone.strip(),
    )
    cancellation_token, cancellation_token_hash = generate_unique_cancellation_token(db)
    appointment = Appointment(
        client=client,
        service=service,
        barber=barber,
        date=payload.date,
        start_time=payload.start_time,
        status="Confirmado",
        origin=origin,
        cancellation_token_hash=cancellation_token_hash,
    )
    appointment._cancellation_token = cancellation_token
    db.add(appointment)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "El horario ya fue reservado.")
    db.refresh(appointment)
    appointment._cancellation_token = cancellation_token
    return appointment


def cancel_appointment(db: Session, appointment_id: int) -> Appointment:
    appointment = db.get(Appointment, appointment_id)
    if not appointment:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Turno no encontrado.")
    appointment.status = "Cancelado"
    db.commit()
    db.refresh(appointment)
    return appointment


def appointment_by_cancellation_token(db: Session, token: str) -> Appointment:
    appointment = db.scalar(
        select(Appointment).where(Appointment.cancellation_token_hash == hash_cancellation_token(token))
    )
    if not appointment:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Token de cancelacion invalido.")
    if appointment.status == "Cancelado":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El turno ya fue cancelado.")
    if is_past_slot(appointment.date, appointment.start_time):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No se puede cancelar un turno pasado.")
    return appointment


def cancel_appointment_by_token(db: Session, token: str) -> Appointment:
    appointment = appointment_by_cancellation_token(db, token)
    appointment.status = "Cancelado"
    db.commit()
    db.refresh(appointment)
    return appointment


def create_block(db: Session, payload: BlockCreate) -> BlockedSlot:
    validate_slot(payload.date, payload.start_time)
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
    barbers = active_barbers(db)
    appointments = {
        (item.barber_id, item.start_time): item
        for item in db.scalars(
            select(Appointment).where(Appointment.date == slot_date, Appointment.status != "Cancelado")
        ).all()
    }
    blocks = {item.start_time: item for item in db.scalars(select(BlockedSlot).where(BlockedSlot.date == slot_date)).all()}
    agenda: list[AgendaSlot] = []
    for barber in barbers:
        for slot in generate_slots():
            appointment = appointments.get((barber.id, slot))
            block = blocks.get(slot)
            if appointment:
                agenda.append(
                    AgendaSlot(
                        time=slot,
                        status="Reservado",
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

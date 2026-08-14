import json
import logging
from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.appointment import STATUS_CONFIRMED, STATUS_EXPIRED, STATUS_PENDING_PAYMENT, Appointment
from ..models.payment import (
    PAYMENT_STATUS_APPROVED,
    PAYMENT_STATUS_CANCELLED,
    PAYMENT_STATUS_PENDING,
    PAYMENT_STATUS_REJECTED,
    PAYMENT_STATUS_REFUNDED,
    Payment,
)
from ..schemas.appointment import PaymentStartResponse, PublicPaymentStatus
from . import mercadopago
from .schedule import appointment_end_time, expire_pending_payments, hash_cancellation_token, naive_now_for_db

logger = logging.getLogger(__name__)


def latest_payment(db: Session, appointment_id: int) -> Payment | None:
    return db.scalar(
        select(Payment)
        .where(Payment.appointment_id == appointment_id)
        .order_by(Payment.id.desc())
        .limit(1)
    )


def appointment_by_payment_status_token(db: Session, token: str) -> Appointment:
    expire_pending_payments(db)
    appointment = db.scalar(
        select(Appointment).where(Appointment.payment_status_token_hash == hash_cancellation_token(token))
    )
    if not appointment:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El enlace de pago no es válido o ya no está disponible.")
    return appointment


def build_payment_status(db: Session, appointment: Appointment) -> PublicPaymentStatus:
    db.refresh(appointment)
    payment = latest_payment(db, appointment.id)
    return PublicPaymentStatus(
        appointment_status=appointment.status,
        payment_status=payment.status if payment else None,
        service_price=appointment.service_price,
        service_visible_duration_minutes=appointment.service_visible_duration_minutes,
        service_blocking_duration_minutes=appointment.service_blocking_duration_minutes,
        deposit_amount=appointment.deposit_amount,
        remaining_balance=appointment.remaining_balance,
        expires_at=appointment.payment_expires_at,
        barber_name=appointment.barber.name,
        service_name=appointment.service.name,
        date=appointment.date,
        start_time=appointment.start_time,
        end_time=appointment_end_time(appointment),
        client_first_name=appointment.client.first_name,
        client_last_name=appointment.client.last_name,
        client_phone=appointment.client.phone,
        checkout_url=payment.checkout_url if payment else None,
    )


def ensure_checkout_for_appointment(
    db: Session,
    appointment: Appointment,
    payment_status_token: str,
) -> PaymentStartResponse:
    expire_pending_payments(db)
    db.refresh(appointment)
    if appointment.status == STATUS_EXPIRED:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La reserva ya venció.")
    if appointment.status == STATUS_CONFIRMED:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El turno ya está confirmado.")
    if appointment.status != STATUS_PENDING_PAYMENT:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El turno no requiere pago pendiente.")

    payment = latest_payment(db, appointment.id)
    if not payment or payment.status != PAYMENT_STATUS_PENDING:
        if appointment.deposit_amount is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "El turno no tiene seña configurada.")
        payment = Payment(appointment=appointment, amount=appointment.deposit_amount, status=PAYMENT_STATUS_PENDING)
        db.add(payment)
        db.commit()
        db.refresh(payment)

    if payment.external_preference_id and payment.checkout_url:
        return PaymentStartResponse(
            status=appointment.status,
            appointment_id=appointment.id,
            deposit_amount=appointment.deposit_amount,
            expires_at=appointment.payment_expires_at,
            payment_status_token=payment_status_token,
            checkout_url=payment.checkout_url,
        )

    try:
        preference = mercadopago.create_preference(
            appointment=appointment,
            payment=payment,
            payment_status_token=payment_status_token,
        )
    except mercadopago.MercadoPagoError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc

    payment.external_preference_id = str(preference["id"])
    payment.checkout_url = preference["checkout_url"]
    db.commit()
    db.refresh(payment)
    return PaymentStartResponse(
        status=appointment.status,
        appointment_id=appointment.id,
        deposit_amount=appointment.deposit_amount,
        expires_at=appointment.payment_expires_at,
        payment_status_token=payment_status_token,
        checkout_url=payment.checkout_url,
    )


def start_checkout_by_token(db: Session, appointment_id: int, payment_status_token: str) -> PaymentStartResponse:
    appointment = appointment_by_payment_status_token(db, payment_status_token)
    if appointment.id != appointment_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El enlace de pago no corresponde al turno.")
    return ensure_checkout_for_appointment(db, appointment, payment_status_token)


def payment_amount_matches(payment: Payment, mp_payment: dict) -> bool:
    try:
        amount = Decimal(str(mp_payment.get("transaction_amount"))).quantize(Decimal("0.01"))
    except Exception:
        return False
    expected = Decimal(payment.amount).quantize(Decimal("0.01"))
    return payment.currency == mp_payment.get("currency_id") and expected == amount


def payment_external_reference(payment: Payment) -> str:
    return f"payment:{payment.id}"


def approved_datetime(mp_payment: dict) -> datetime:
    approved_at = mp_payment.get("date_approved")
    if approved_at:
        try:
            return datetime.fromisoformat(str(approved_at).replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            logger.warning("Mercado Pago devolvió date_approved inválido para payment_id=%s.", mp_payment.get("id") or "sin-id")
    return naive_now_for_db()


def mp_payment_belongs_to_payment(payment: Payment, mp_payment: dict) -> bool:
    external_reference = str(mp_payment.get("external_reference") or "")
    if external_reference != payment_external_reference(payment):
        logger.warning(
            "Pago Mercado Pago no corresponde al pago interno esperado. expected=%s received=%s",
            payment_external_reference(payment),
            external_reference or "sin-referencia",
        )
        return False

    preference_id = mp_payment.get("preference_id")
    if preference_id and payment.external_preference_id and str(preference_id) != str(payment.external_preference_id):
        logger.warning(
            "Pago Mercado Pago con preference_id inconsistente para pago %s.",
            payment.id,
        )
        return False
    return True


def payment_from_mp_payload(db: Session, mp_payment: dict) -> Payment | None:
    external_payment_id = str(mp_payment.get("id") or "")
    if external_payment_id:
        existing = db.scalar(select(Payment).where(Payment.external_payment_id == external_payment_id))
        if existing:
            logger.info("Webhook Mercado Pago duplicado para payment_id=%s.", external_payment_id)
            return existing

    external_reference = str(mp_payment.get("external_reference") or "")
    if external_reference.startswith("payment:"):
        try:
            payment = db.get(Payment, int(external_reference.split(":", 1)[1]))
            if payment:
                return payment
        except ValueError:
            return None
        return None
    if external_reference:
        logger.warning("Payment Mercado Pago con external_reference inválido: %s.", external_reference)
        return None

    metadata = mp_payment.get("metadata") or {}
    payment_attempt_id = metadata.get("payment_attempt_id")
    if payment_attempt_id:
        try:
            payment = db.get(Payment, int(payment_attempt_id))
            if payment:
                return payment
        except (TypeError, ValueError):
            return None

    preference_id = mp_payment.get("preference_id")
    if preference_id:
        return db.scalar(select(Payment).where(Payment.external_preference_id == str(preference_id)))
    return None


def process_expected_mercadopago_payment(db: Session, payment: Payment, mp_payment: dict) -> Payment:
    if not mp_payment_belongs_to_payment(payment, mp_payment):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El pago informado no corresponde a esta reserva.")
    return process_mercadopago_payment(db, mp_payment)


def reconcile_payment_return(db: Session, appointment: Appointment, payment_id: str | None = None) -> Payment | None:
    payment = latest_payment(db, appointment.id)
    if not payment:
        return None
    if payment.status == PAYMENT_STATUS_APPROVED:
        return payment
    if appointment.status not in (STATUS_PENDING_PAYMENT, STATUS_EXPIRED):
        return payment

    mp_payments = []
    if payment_id:
        try:
            mp_payments.append(mercadopago.get_payment(payment_id))
        except mercadopago.MercadoPagoError as exc:
            logger.warning("No se pudo reconciliar payment_id=%s: %s", payment_id, exc)
            return payment
    else:
        try:
            mp_payments.extend(mercadopago.search_payments_by_external_reference(payment_external_reference(payment)))
        except mercadopago.MercadoPagoError as exc:
            logger.warning("No se pudo reconciliar por external_reference para pago %s: %s", payment.id, exc)
            return payment

    for mp_payment in mp_payments:
        if not mp_payment_belongs_to_payment(payment, mp_payment):
            continue
        return process_mercadopago_payment(db, mp_payment)
    return payment


def process_mercadopago_payment(db: Session, mp_payment: dict) -> Payment:
    payment = payment_from_mp_payload(db, mp_payment)
    if not payment:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pago interno no encontrado.")

    external_payment_id = str(mp_payment.get("id") or "")
    mapped_status = mercadopago.map_payment_status(mp_payment.get("status"))
    payment.raw_status = json.dumps(
        {
            "id": external_payment_id,
            "status": mp_payment.get("status"),
            "status_detail": mp_payment.get("status_detail"),
            "preference_id": mp_payment.get("preference_id"),
        },
        ensure_ascii=False,
    )

    if mapped_status == PAYMENT_STATUS_APPROVED:
        if payment.status == PAYMENT_STATUS_APPROVED:
            payment.external_payment_id = external_payment_id or payment.external_payment_id
            db.commit()
            return payment
        if not payment_amount_matches(payment, mp_payment):
            logger.warning("Pago %s no confirmado por monto o moneda inconsistente.", payment.id)
            payment.external_payment_id = external_payment_id or payment.external_payment_id
            payment.status = PAYMENT_STATUS_REJECTED
            db.commit()
            db.refresh(payment)
            return payment

        payment.external_payment_id = external_payment_id
        payment.status = PAYMENT_STATUS_APPROVED
        payment.approved_at = approved_datetime(mp_payment)
        appointment = payment.appointment
        if appointment.status == STATUS_PENDING_PAYMENT:
            if appointment.payment_expires_at and appointment.payment_expires_at <= naive_now_for_db():
                appointment.status = STATUS_EXPIRED
                logger.warning("Pago aprobado tardío para turno expirado %s. Requiere revisión manual.", appointment.id)
            else:
                appointment.status = STATUS_CONFIRMED
                logger.info("Turno %s confirmado por payment %s.", appointment.id, external_payment_id)
        elif appointment.status == STATUS_CONFIRMED:
            logger.info("Turno %s ya estaba confirmado. Webhook idempotente.", appointment.id)
        elif appointment.status == STATUS_EXPIRED:
            logger.warning("Pago aprobado para turno expirado %s. No se confirma automáticamente.", appointment.id)
    elif mapped_status in (PAYMENT_STATUS_REJECTED, PAYMENT_STATUS_CANCELLED, PAYMENT_STATUS_REFUNDED):
        payment.external_payment_id = external_payment_id or payment.external_payment_id
        payment.status = mapped_status
        logger.info("Pago %s actualizado a %s desde Mercado Pago.", payment.id, mapped_status)
    else:
        payment.external_payment_id = external_payment_id or payment.external_payment_id
        payment.status = PAYMENT_STATUS_PENDING
        logger.info("Pago %s continúa pendiente según Mercado Pago.", payment.id)

    db.commit()
    db.refresh(payment)
    return payment

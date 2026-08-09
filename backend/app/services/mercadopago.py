import logging
from decimal import Decimal
from urllib.parse import quote

import mercadopago
from mercadopago.webhook import InvalidWebhookSignatureError, WebhookSignatureValidator

from ..config import settings

logger = logging.getLogger(__name__)


class MercadoPagoError(Exception):
    pass


def is_configured() -> bool:
    return bool(settings.mercadopago_access_token.strip())


def public_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def create_preference(*, appointment, payment, payment_status_token: str) -> dict:
    if not is_configured():
        raise MercadoPagoError("Mercado Pago no está configurado.")

    frontend_url = settings.frontend_public_url.rstrip("/")
    amount = Decimal(payment.amount).quantize(Decimal("0.01"))
    payload = {
        "items": [
            {
                "title": f"Seña turno {appointment.service.name}",
                "quantity": 1,
                "currency_id": payment.currency,
                "unit_price": float(amount),
            }
        ],
        "external_reference": f"payment:{payment.id}",
        "metadata": {
            "appointment_id": appointment.id,
            "payment_attempt_id": payment.id,
        },
        "back_urls": {
            "success": public_url(frontend_url, f"/pago/exito?token={quote(payment_status_token)}"),
            "pending": public_url(frontend_url, f"/pago/pendiente?token={quote(payment_status_token)}"),
            "failure": public_url(frontend_url, f"/pago/error?token={quote(payment_status_token)}"),
        },
    }

    try:
        response = mercadopago.SDK(settings.mercadopago_access_token).preference().create(payload)
    except Exception as exc:
        logger.warning("No se pudo crear la preference de Mercado Pago: %s", exc)
        raise MercadoPagoError("No se pudo crear el checkout de Mercado Pago.") from exc

    status_code = response.get("status")
    preference = response.get("response") or {}
    if status_code and int(status_code) >= 400:
        logger.warning("Mercado Pago rechazó la preference. HTTP %s", status_code)
        raise MercadoPagoError("Mercado Pago rechazó la solicitud.")

    preference_id = preference.get("id")
    checkout_url = preference.get("sandbox_init_point") or preference.get("init_point")
    if not preference_id or not checkout_url:
        logger.warning("Mercado Pago no devolvió id/init_point para el pago %s.", payment.id)
        raise MercadoPagoError("Mercado Pago no devolvió un checkout válido.")

    logger.info("Preference de Mercado Pago creada para pago %s.", payment.id)
    return {
        "id": preference_id,
        "checkout_url": checkout_url,
    }


def get_payment(payment_id: str) -> dict:
    if not is_configured():
        raise MercadoPagoError("Mercado Pago no está configurado.")
    try:
        response = mercadopago.SDK(settings.mercadopago_access_token).payment().get(payment_id)
    except Exception as exc:
        logger.warning("No se pudo consultar el payment %s en Mercado Pago: %s", payment_id, exc)
        raise MercadoPagoError("No se pudo consultar el pago en Mercado Pago.") from exc

    status_code = response.get("status")
    payment = response.get("response") or {}
    if status_code and int(status_code) >= 400:
        logger.warning("Mercado Pago rechazó la consulta del payment %s. HTTP %s", payment_id, status_code)
        raise MercadoPagoError("Mercado Pago rechazó la consulta del pago.")
    return payment


def validate_webhook_signature(*, x_signature: str | None, x_request_id: str | None, data_id: str | None) -> bool:
    secret = settings.mercadopago_webhook_secret.strip()
    if not secret:
        logger.warning("Webhook Mercado Pago rechazado: MERCADOPAGO_WEBHOOK_SECRET no está configurado.")
        return False
    try:
        WebhookSignatureValidator.validate(x_signature, x_request_id, data_id, secret)
        return True
    except InvalidWebhookSignatureError:
        logger.warning("Webhook Mercado Pago rechazado por firma inválida para payment_id=%s.", data_id or "sin-id")
        return False


def map_payment_status(status: str | None) -> str:
    if status == "approved":
        return "APPROVED"
    if status == "rejected":
        return "REJECTED"
    if status == "cancelled":
        return "CANCELLED"
    if status in ("refunded", "charged_back"):
        return "REFUNDED"
    return "PENDING"

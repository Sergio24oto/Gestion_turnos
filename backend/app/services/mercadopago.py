import hashlib
import logging
from decimal import Decimal
from urllib.parse import quote, urlparse

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


def partial_sha256(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]


def signature_diagnostics(x_signature: str | None, x_request_id: str | None, data_id: str | None, secret: str) -> dict:
    ts = None
    v1 = None
    for part in (x_signature or "").split(","):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip().lower()
        value = value.strip()
        if key == "ts":
            ts = value
        elif key == "v1":
            v1 = value

    request_id_hash = partial_sha256(x_request_id)
    manifest_parts = []
    if data_id:
        manifest_parts.append(f"id:{data_id}")
    if x_request_id:
        manifest_parts.append(f"request-id-sha256-8:{request_id_hash}")
    if ts:
        manifest_parts.append(f"ts:{ts}")

    return {
        "x_signature_present": bool(x_signature),
        "x_signature_length": len(x_signature or ""),
        "x_request_id_present": bool(x_request_id),
        "x_request_id_length": len(x_request_id or ""),
        "data_id": data_id,
        "ts": ts,
        "v1_present": bool(v1),
        "v1_length": len(v1 or ""),
        "webhook_secret_configured": bool(secret),
        "webhook_secret_length": len(secret or ""),
        "x_request_id_sha256_8": request_id_hash,
        "webhook_secret_sha256_8": partial_sha256(secret),
        "manifest_redacted": ";".join(manifest_parts) + (";" if manifest_parts else ""),
    }


def is_public_https_url(url: str) -> bool:
    parsed = urlparse(url.strip())
    return parsed.scheme == "https" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}


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
    backend_url = settings.backend_public_url.strip()
    if is_public_https_url(backend_url):
        payload["notification_url"] = public_url(backend_url, "/api/webhooks/mercadopago")

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
    diagnostics = signature_diagnostics(x_signature, x_request_id, data_id, secret)
    if not secret:
        logger.info("Diagnostico webhook Mercado Pago: %s resultado=invalid reason=missing_secret", diagnostics)
        logger.warning("Webhook Mercado Pago rechazado: MERCADOPAGO_WEBHOOK_SECRET no está configurado.")
        return False
    try:
        WebhookSignatureValidator.validate(x_signature, x_request_id, data_id, secret)
        logger.info("Diagnostico webhook Mercado Pago: %s resultado=valid reason=none", diagnostics)
        return True
    except InvalidWebhookSignatureError as exc:
        reason = getattr(getattr(exc, "reason", None), "value", "invalid_signature")
        logger.info("Diagnostico webhook Mercado Pago: %s resultado=invalid reason=%s", diagnostics, reason)
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

import logging
from dataclasses import dataclass
from decimal import Decimal
import hashlib
import hmac
from urllib.parse import quote, urlparse

import mercadopago
from mercadopago.webhook import InvalidWebhookSignatureError, WebhookSignatureValidator

from ..config import settings

logger = logging.getLogger(__name__)


class MercadoPagoError(Exception):
    pass


@dataclass(frozen=True)
class WebhookValidationResult:
    valid: bool
    reason: str | None = None


def is_configured() -> bool:
    return bool(settings.mercadopago_access_token.strip())


def public_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def partial_sha256(value: str | None, length: int = 12) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def parse_signature_header(x_signature: str | None) -> tuple[str | None, str | None]:
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
    return ts, v1


def build_webhook_manifest(data_id: str | None, request_id: str | None, ts: str | None) -> str:
    parts = []
    if data_id:
        parts.append(f"id:{data_id}")
    if request_id:
        parts.append(f"request-id:{request_id}")
    if ts:
        parts.append(f"ts:{ts}")
    return ";".join(parts) + (";" if parts else "")


def redacted_webhook_manifest(data_id: str | None, request_id: str | None, ts: str | None) -> str:
    parts = []
    if data_id:
        parts.append(f"id:{data_id}")
    if request_id:
        parts.append(f"request-id:{partial_sha256(request_id)}")
    if ts:
        parts.append(f"ts:{ts}")
    return ";".join(parts) + (";" if parts else "")


def log_webhook_signature_diagnostics(
    *,
    x_signature: str | None,
    x_request_id: str | None,
    x_railway_request_id: str | None,
    data_id: str | None,
    secret: str,
    valid: bool,
    reason: str | None,
) -> None:
    ts, v1 = parse_signature_header(x_signature)
    computed_matches = None
    if secret and v1 and ts:
        manifest = build_webhook_manifest(data_id, x_request_id, ts)
        computed = hmac.new(secret.encode("utf-8"), manifest.encode("utf-8"), hashlib.sha256).hexdigest()
        computed_matches = hmac.compare_digest(computed, v1)

    logger.info(
        "Diagnostico HMAC Mercado Pago: "
        "x_request_id_present=%s x_request_id_length=%s x_request_id_sha256_12=%s "
        "x_railway_request_id_present=%s x_railway_request_id_length=%s x_railway_request_id_sha256_12=%s "
        "request_ids_equal=%s data_id=%s ts=%s manifest_redacted=%s hmac_matches=%s result=%s reason=%s",
        bool(x_request_id),
        len(x_request_id or ""),
        partial_sha256(x_request_id),
        bool(x_railway_request_id),
        len(x_railway_request_id or ""),
        partial_sha256(x_railway_request_id),
        x_request_id == x_railway_request_id,
        data_id,
        ts,
        redacted_webhook_manifest(data_id, x_request_id, ts),
        computed_matches,
        "valid" if valid else "invalid",
        reason or "none",
    )


def is_public_https_url(url: str) -> bool:
    parsed = urlparse(url.strip())
    return parsed.scheme == "https" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}


def sdk() -> mercadopago.SDK:
    if not is_configured():
        raise MercadoPagoError("Mercado Pago no está configurado.")
    return mercadopago.SDK(settings.mercadopago_access_token)


def build_preference_payload(*, appointment, payment, payment_status_token: str) -> dict:
    frontend_url = settings.frontend_public_url.rstrip("/")
    backend_url = settings.backend_public_url.strip()
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
    if is_public_https_url(backend_url):
        payload["notification_url"] = public_url(backend_url, "/api/webhooks/mercadopago")
    return payload


def create_preference(*, appointment, payment, payment_status_token: str) -> dict:
    payload = build_preference_payload(
        appointment=appointment,
        payment=payment,
        payment_status_token=payment_status_token,
    )

    try:
        response = sdk().preference().create(payload)
    except Exception as exc:
        logger.warning("No se pudo crear la preference de Mercado Pago: %s", exc)
        raise MercadoPagoError("No se pudo crear el checkout de Mercado Pago.") from exc

    status_code = response.get("status")
    preference = response.get("response") or {}
    if status_code and int(status_code) >= 400:
        logger.warning("Mercado Pago rechazó la preference. HTTP %s", status_code)
        raise MercadoPagoError("Mercado Pago rechazó la solicitud.")

    preference_id = preference.get("id")
    checkout_url = preference.get("init_point") or preference.get("sandbox_init_point")
    if not preference_id or not checkout_url:
        logger.warning("Mercado Pago no devolvió id/init_point para el pago %s.", payment.id)
        raise MercadoPagoError("Mercado Pago no devolvió un checkout válido.")

    logger.info("Preference de Mercado Pago creada para pago %s.", payment.id)
    return {
        "id": preference_id,
        "checkout_url": checkout_url,
    }


def get_payment(payment_id: str) -> dict:
    try:
        response = sdk().payment().get(payment_id)
    except Exception as exc:
        logger.warning("No se pudo consultar el payment %s en Mercado Pago: %s", payment_id, exc)
        raise MercadoPagoError("No se pudo consultar el pago en Mercado Pago.") from exc

    status_code = response.get("status")
    payment = response.get("response") or {}
    if status_code and int(status_code) >= 400:
        logger.warning("Mercado Pago rechazó la consulta del payment %s. HTTP %s", payment_id, status_code)
        raise MercadoPagoError("Mercado Pago rechazó la consulta del pago.")
    return payment


def validate_webhook_signature(
    *,
    x_signature: str | None,
    x_request_id: str | None,
    x_railway_request_id: str | None = None,
    data_id: str | None,
) -> WebhookValidationResult:
    secret = settings.mercadopago_webhook_secret.strip()
    if not secret:
        logger.warning("Webhook Mercado Pago rechazado: MERCADOPAGO_WEBHOOK_SECRET no está configurado.")
        log_webhook_signature_diagnostics(
            x_signature=x_signature,
            x_request_id=x_request_id,
            x_railway_request_id=x_railway_request_id,
            data_id=data_id,
            secret=secret,
            valid=False,
            reason="missing_secret",
        )
        return WebhookValidationResult(valid=False, reason="missing_secret")
    try:
        WebhookSignatureValidator.validate(x_signature, x_request_id, data_id, secret)
        log_webhook_signature_diagnostics(
            x_signature=x_signature,
            x_request_id=x_request_id,
            x_railway_request_id=x_railway_request_id,
            data_id=data_id,
            secret=secret,
            valid=True,
            reason=None,
        )
        return WebhookValidationResult(valid=True)
    except InvalidWebhookSignatureError as exc:
        reason = getattr(getattr(exc, "reason", None), "value", "invalid_signature")
        log_webhook_signature_diagnostics(
            x_signature=x_signature,
            x_request_id=x_request_id,
            x_railway_request_id=x_railway_request_id,
            data_id=data_id,
            secret=secret,
            valid=False,
            reason=reason,
        )
        logger.warning("Webhook Mercado Pago rechazado por firma inválida. reason=%s data_id=%s", reason, data_id or "sin-id")
        return WebhookValidationResult(valid=False, reason=reason)


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

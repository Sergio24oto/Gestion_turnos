import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..services import mercadopago
from ..services.payments import process_mercadopago_payment

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


async def safe_json_body(request: Request) -> dict:
    try:
        body = await request.json()
    except Exception:
        return {}
    return body if isinstance(body, dict) else {}


@router.post("/mercadopago")
async def mercadopago_webhook(
    request: Request,
    data_id: str | None = Query(default=None, alias="data.id"),
    event_type: str | None = Query(default=None, alias="type"),
    ipn_id: str | None = Query(default=None, alias="id"),
    ipn_topic: str | None = Query(default=None, alias="topic"),
    x_signature: str | None = Header(default=None, alias="x-signature"),
    x_request_id: str | None = Header(default=None, alias="x-request-id"),
    db: Session = Depends(get_db),
):
    body = await safe_json_body(request)
    body_type = body.get("type")
    body_data_id = str((body.get("data") or {}).get("id") or "") or None

    topic = event_type or body_type
    payment_id = data_id or body_data_id
    logger.info("Webhook Mercado Pago recibido. topic=%s payment_id=%s", topic or ipn_topic or "sin-topic", payment_id or ipn_id or "sin-id")

    if ipn_topic:
        logger.info("Notificación IPN/legacy de Mercado Pago ignorada. topic=%s id=%s", ipn_topic, ipn_id or "sin-id")
        return {"status": "ignored", "format": "ipn"}

    if topic != "payment":
        return {"status": "ignored", "topic": topic or "unknown"}

    if not data_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Notificación webhook sin data.id.")

    original_x_request_id = request.headers.get("x-request-id")
    x_railway_request_id = request.headers.get("x-railway-request-id")
    validation = mercadopago.validate_webhook_signature(
        x_signature=x_signature,
        x_request_id=original_x_request_id or x_request_id,
        x_railway_request_id=x_railway_request_id,
        data_id=data_id,
    )
    if not validation.valid:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Firma inválida.")

    try:
        mp_payment = mercadopago.get_payment(payment_id)
    except mercadopago.MercadoPagoError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    payment = process_mercadopago_payment(db, mp_payment)
    return {"status": "received", "payment_status": payment.status}

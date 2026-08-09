import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..services import mercadopago
from ..services.payments import process_mercadopago_payment

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/mercadopago")
async def mercadopago_webhook(
    request: Request,
    data_id: str | None = Query(default=None, alias="data.id"),
    x_signature: str | None = Header(default=None, alias="x-signature"),
    x_request_id: str | None = Header(default=None, alias="x-request-id"),
    db: Session = Depends(get_db),
):
    body = await request.json()
    topic = body.get("type") or body.get("topic")
    payment_id = data_id or str((body.get("data") or {}).get("id") or "")
    logger.info("Webhook Mercado Pago recibido. topic=%s payment_id=%s", topic or "sin-topic", payment_id or "sin-id")

    if topic and topic != "payment":
        return {"status": "ignored"}

    if not payment_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Notificación sin payment_id.")

    if not mercadopago.validate_webhook_signature(
        x_signature=x_signature,
        x_request_id=x_request_id,
        data_id=payment_id,
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Firma inválida.")

    try:
        mp_payment = mercadopago.get_payment(payment_id)
    except mercadopago.MercadoPagoError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    payment = process_mercadopago_payment(db, mp_payment)
    return {"status": "received", "payment_status": payment.status}

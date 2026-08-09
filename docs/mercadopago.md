# Mercado Pago Checkout Pro y Webhook

Esta integración usa el SDK oficial de Mercado Pago desde FastAPI.

## Variables

Configurar en `backend/.env`:

```env
MERCADOPAGO_ACCESS_TOKEN=
MERCADOPAGO_WEBHOOK_SECRET=
FRONTEND_PUBLIC_URL=http://localhost:5173
BACKEND_PUBLIC_URL=http://localhost:8000
```

No guardar secretos reales en el repositorio.

## Preference

Cuando un servicio requiere seña:

1. El turno se crea como `PENDING_PAYMENT`.
2. Se crea un registro en `pagos` con estado `PENDING`.
3. FastAPI crea una Preference real de Mercado Pago.
4. Se guarda `pagos.external_preference_id`.
5. Se guarda `pagos.checkout_url` para reutilizar la Preference.
6. React redirige a `checkout_url`.

## Webhook

URL a configurar en Mercado Pago:

```text
BACKEND_PUBLIC_URL/api/webhooks/mercadopago
```

Ejemplo local con túnel HTTPS:

```text
https://tu-tunel-publico/api/webhooks/mercadopago
```

El endpoint es público y no requiere autenticación admin.

## Firma

El webhook valida la firma con el validador oficial del SDK:

- `x-signature`;
- `x-request-id`;
- `data.id`;
- `MERCADOPAGO_WEBHOOK_SECRET`.

Si la firma es inválida, no se consulta Mercado Pago ni se modifica la base.

## Confirmación

El webhook no confía en el cuerpo recibido. Toma el `payment_id`, consulta el payment real en Mercado Pago y valida:

- `status = approved`;
- `transaction_amount` igual a `pagos.monto`;
- `currency_id = ARS`;
- relación segura por `external_reference`, `metadata.payment_attempt_id` o `external_preference_id`.

Solo entonces cambia:

- `pagos.estado -> APPROVED`;
- `turnos.estado PENDING_PAYMENT -> CONFIRMED`.

Si el turno ya está `EXPIRED`, el pago aprobado se registra pero el turno no se confirma automáticamente.

## Retornos Frontend

Las rutas:

```text
/pago/exito
/pago/pendiente
/pago/error
```

consultan el estado real en el backend mediante token seguro. La llegada a `/pago/exito` no confirma nada por sí sola.

## Pendiente Para Prueba Externa

Para probar desde Mercado Pago Developers falta exponer FastAPI mediante una URL pública HTTPS y configurar esa URL como webhook de topic `payment`.

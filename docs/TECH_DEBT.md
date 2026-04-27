# Deuda técnica — versión simplificada

## Implementado (pendientes previos resueltos en código)

- **SMTP**: envío de verificación con `smtplib` cuando `SMTP_HOST` (y datos) están configurados; si no, el enlace queda en **log** (`WARNING`).
- **Refresh token**: tokens **opacos** en tabla `refresh_tokens`, **rotación** en cada `POST /auth/refresh`, **revocación** en `POST /auth/logout` y al verificar correo.
- **Redis**: si `REDIS_URL` está definido, los límites de **resend** e **intentos de código Telegram** usan ventana deslizante en Redis; si falla la conexión, se usa memoria por proceso.
- **Teléfono `tg:`**: el panel muestra `Telegram · <id>` vía `formatPhone()` en el front.

## Operación en tu entorno

1. Ejecutar migraciones: `alembic upgrade head` (incluye `refresh_tokens`).
2. Configurar `.env` según `backend/api-backend/.env.example`.
3. Tras este cambio, los **refresh JWT antiguos** dejan de valer: los usuarios deben **volver a iniciar sesión** una vez.

## Mejoras futuras (opcional)

- Revocar refresh al **cambiar contraseña**.
- Cola de correo (Celery/RQ) si el volumen crece.
- Tests de integración con BD para `refresh_token_service`.

## Deuda técnica nueva (optimización tokens / reservas)

- **Estado**: resuelta para esta iteración. Parser robusto, cuotas persistentes fallback, paridad básica de canales, tests automáticos y migración a `ConfigDict` de Pydantic v2 ya están aplicados.

## Fase 6 (producto)

Ver `docs/PHASE6_BACKLOG.md` (pagos, planes, roles, CI/CD ampliado, etc.).

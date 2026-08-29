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

## Deuda técnica: convenio de timezone wall-clock-as-UTC

- **Estado**: mitigado (2026-08-29), corrección arquitectónica pendiente.
- **Problema**: las citas se guardan con la hora local del negocio **estampada como
  UTC** (`_utc_datetime` en `db_service.py`: un "9:00 AM" en Santo Domingo se guarda
  como `09:00 UTC`, no `13:00 UTC`). El resto del sistema (disponibilidad,
  calendario, dashboard) comparte el convenio, por lo que es internamente consistente,
  pero cualquier comparación contra el reloj real UTC rompe (el bug de "ver mis citas"
  que excluía las citas del día desde las 5:00 AM local).
- **Mitigación aplicada**: `get_customer_appointments(upcoming=True)` compara contra
  `_upcoming_now()` = reloj operativo (`America/Santo_Domingo`) estampado como UTC —
  el mismo convenio que el almacenamiento (tests en `tests/test_upcoming_filter_timezone.py`).
- **Deuda pendiente**: migrar el almacenamiento a UTC real (9:00 AM local = 13:00 UTC)
  tocando disponibilidad, recordatorios, dashboard y owner channel + migración de
  datos existentes. Cambio arquitectónico para después del MVP.

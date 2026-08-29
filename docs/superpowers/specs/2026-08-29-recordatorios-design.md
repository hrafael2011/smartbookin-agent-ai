# Spec: Recordatorios de citas (24h y 2h antes)

**Fecha**: 2026-08-29
**Estado**: diseño acordado con el usuario (cron dentro de Railway, sin fragmentar estructura)

## Contexto

El endpoint `POST /internal/jobs/reminders` existe y está verificado en Railway, pero
`process_appointment_reminders()` (app/services/background_tasks.py) es un esqueleto:
calcula las ventanas y no hace nada. El modelo ya tiene los flags
`reminder_24h_sent` / `reminder_2h_sent` (Appointment).

**Decisión del usuario (2026-08-29)**: el cron queda **dentro de Railway** (scheduler
en proceso del app, que ya corre 24/7 por el webhook) — sin servicios externos ni
nuevos contenedores. Precisión aceptada: **±15 min** (intervalo de 15 min).

## Cambios

### 1. Lógica real en `process_appointment_reminders()` (app/services/background_tasks.py)

- `now_op = db_service._upcoming_now()` — **convenio wall-clock-as-UTC** (NO
  `datetime.now(timezone.utc)` real; si no, los recordatorios se dispararían 4 h
  antes para Santo Domingo — mismo bug corregido en "ver mis citas").
- Ventanas (constante `REMINDER_CADENCE_MINUTES = 15`):
  - 24h: `date BETWEEN now_op + 23h45m AND now_op + 24h15m` y `reminder_24h_sent = false`
  - 2h:  `date BETWEEN now_op + 1h45m AND now_op + 2h15m` y `reminder_2h_sent = false`
  - `status IN ('P', 'C')` (excluye canceladas A y completadas D).
- Por cita: resolver canal del cliente — `customer.phone_number` con prefijo
  `tg:` → chat_id → `telegram_client.send_text_message(chat_id, mensaje)`.
  Prefijos que no sean `tg:` se omiten con log (WhatsApp queda para después).
- Mensaje: negocio (nombre+dirección), servicio, fecha legible ("viernes 30 de
  agosto"), hora (12h). Con emojis consistentes con el resto del bot.
- **Flags idempotentes**: marcar `reminder_24h_sent`/`reminder_2h_sent = true` en la
  misma transacción **solo si el envío fue exitoso** (si falla, la próxima corrida
  reintenta; nunca se duplica un recordatorio enviado).
- Robustez: cada envío con try/except + `logger.exception` (el job no debe morir por
  una cita fallida); logs `logger.info` por recordatorio enviado.

### 2. Intervalo del job (app/main.py:61)

`minutes=30` → `minutes=15` (precisión ±15 min acordada). El job ya está registrado
in-process; solo cambia la frecuencia.

### 3. Activación del scheduler en Railway

- El scheduler in-process se inicia cuando `CRON_EXTERNAL != true` (main.py:50-58).
- **Acción en Railway (dashboard)**: setear `CRON_EXTERNAL=false` (hoy `true`) para
  que el job de 15 min corra. Sin cambios de código para esto.
- Los endpoints `/internal/jobs/*` se mantienen (trigger manual/pruebas).

### 4. Docs

- `.env.example`: comentario de `CRON_EXTERNAL` actualizado (false = scheduler
  in-process con recordatorios cada 15 min).
- Nota en `docs/TECH_DEBT.md` o `docs/MVP_MIGRATION_PLAN.md`: decisión revertida —
  cron in-process en vez de externo (por pedido del usuario, sin fragmentar).

## Fuera de alcance

- Recordatorios por WhatsApp (cuando META_* esté configurado).
- Agenda diaria del dueño (`generate_daily_agenda` sigue sin implementar — no
  pedido).
- Waitlist (flag WAITLIST_ENABLED=false).

## Verificación

- Tests unitarios (TDD): ventanas correctas (±15 min), idempotencia (flags),
  status A/D excluidas, envío exitoso marca flag, envío fallido NO marca flag y
  loguea, teléfono no-`tg:` se omite, query incluye los parámetros de ventana.
- Suite completa en verde.
- Prueba manual post-deploy: agenda una cita para mañana a la misma hora → el bot
  debe recibir el recordatorio ~24 h antes; una cita a ~2 h → recordatorio 2 h antes.
  (Verificación rápida: llamar `POST /internal/jobs/reminders` con el token tras
  agendar.)

# Plan de migración y poda del MVP — SmartBooking AI

**Fecha:** 2026-08-27
**Estado:** Listo para ejecutar
**Objetivo:** pasar de "7 contenedores en VPS 24/7" a "Vercel + Railway + Neon + cron" (~$5–10/mes) con una superficie funcional de MVP, sin tocar la lógica de negocio.
**Memoria técnica:** [MVP_STACK_ANALYSIS.md](MVP_STACK_ANALYSIS.md)

---

## Orden de ejecución

```
Fase 0  Cierre del repo (commits + checklist + migraciones locales)   ← base limpia
Fase 1  Poda funcional (8 funciones diferidas, con flags reversibles)
Fase 2  Frontend → Vercel + limpieza del compose
Fase 3  Base de datos → Neon
Fase 4  Backend → Railway + cron externo + quitar Redis
Fase 5  Prueba de frío de webhooks  ← decisión: seguir vs. plan B
Fase 6  Validación final (criterios de salida)
```

Las fases 2–4 son reversibles en cualquier punto: el compose de desarrollo no se toca como plan de rollback.

---

## Fase 0 — Cierre de pendientes del repo (~2–3 h)

### 0.1 Commitear los cambios sin commitear (agrupados)
Rama actual: `smartbooking-agent-ai-dev` (en sync con origin).

- [ ] **Commit 1 — docs + tooling:** `docs/ARCHITECTURE.md`, `docs/TOKEN_FLOW_RULES.md`, `docs/TECH_DEBT.md`, `docs/PHASE6_BACKLOG.md`, `docs/REVISION_QA_SENIOR.md`, `docs/adr/` (3 ADRs), `docs/archive/` (archivos movidos desde la raíz), `README.md`, `pyproject.toml`, `.pre-commit-config.yaml`, `.editorconfig`, `.gitignore`
- [ ] **Commit 2 — backend QA:** `app/api/appointments.py`, `app/api/businesses.py`, `app/schemas/__init__.py`, `app/services/owner_channel_service.py`, `app/services/telegram_inbound.py`, `app/services/telegram_link_service.py`, `requirements.txt`, `tests/test_owner_channel_binding.py`
- [ ] **Commit 3 — frontend QA:** `src/pages/TelegramIntegration.tsx`, `src/services/api.ts`, `src/types/index.ts`, `eslint.config.js`, `package.json`, `package-lock.json`
- [ ] **Commit 4 — tests frontend:** `vitest.config.ts`, `src/test-setup.ts`, `src/components/ui/*.test.tsx`, `src/store/authStore.test.ts`

### 0.2 Cerrar spec 004 formalmente
El código de las 39 tareas ya está implementado y probado (203 tests verdes); el checklist nunca se marcó.

- [ ] Marcar las 39 tareas de `specs/004-booking-flow-robustness/tasks.md` como completadas (T001–T039)
- [ ] Actualizar `specs/004-booking-flow-robustness/spec.md` con las diferencias de comportamiento implementadas (T039)

### 0.3 Ejecutar migraciones pendientes en la DB de desarrollo
La cadena Alembic confirma 2 migraciones sin aplicar (head = `b2c3d4e5f6a7`):

- [ ] `a1b2c3d4e5f6` — `add_uq_appointment_service_datetime` (anti doble-booking)
- [ ] `b2c3d4e5f6a7` — `add_buffer_minutes_to_services` (spec 006, T003)

```bash
cd backend/api-backend && ./venv/bin/alembic upgrade head
```
- [ ] Verificar en dev: `services` tiene `buffer_minutes = 0` en filas existentes

### 0.4 Limpieza del compose (legado)
- [ ] Eliminar el bloque de comentarios Django/Celery heredado al final de `docker-compose.yml` (líneas ~89–217)

---

## Fase 1 — Poda funcional (~1 día)

**Principio:** nada se borra. Todo se desactiva con flag de entorno o se oculta en UI — reversible en v1.1.

| # | Función | Acción | Archivos |
|---|---|---|---|
| 1.1 | Canal de comandos del owner en Telegram | Flag `OWNER_CHANNEL_ENABLED=false` → el bot no enruta comandos de owner (el dueño usa el panel) | `app/services/owner_command_router.py`, punto de ruteo en `app/services/telegram_inbound.py` / `app/core/orchestrator.py` |
| 1.2 | Waitlist con auto-oferta | Flag `WAITLIST_ENABLED=false` → cancelar solo cancela (paso 4 de `cancel_handler.py` se salta); no crear el job de expiración | `app/handlers/cancel_handler.py`, `app/services/background_tasks.py` |
| 1.3 | Agenda diaria del owner (8:00) | No crear el job en el cron externo (el código queda) | `app/services/background_tasks.py` |
| 1.4 | Verificación de email | Flag `REQUIRE_EMAIL_VERIFICATION=false` → registro activa la cuenta directamente; login no gatea | `app/api/auth.py` |
| 1.5 | Rotación de invite / unlink de Telegram | Ocultar **solo el control de rotate-invite** en UI. Los botones de unlink (agregados en Fase 0) se mantienen: desvincular es seguridad del dueño, no lujo | `frontend/src/pages/TelegramIntegration.tsx` |
| 1.6 | Endpoint `restore` de excepciones | Eliminar el endpoint (el soft-delete de la columna se queda, inofensivo) | `app/api/schedules.py` |
| 1.7 | Página TestUI en producción | Quitar la ruta `/test-ui` de producción (gatear por `import.meta.env.DEV` o eliminar del router) | `frontend/src/App.tsx` |
| 1.8 | Categoría/ubicación en onboarding | Quitar campos del formulario (backend los tolera) | `frontend/src/pages/BusinessOnboarding.tsx` |

**Criterio de salida de la fase:**
- [ ] 203 tests backend + 33 tests frontend en verde tras los cambios
- [ ] Commit por separado: `feat(mvp): defer post-MVP features behind flags`

---

## Fase 2 — Frontend → Vercel (~medio día)

- [ ] Importar `frontend/` en Vercel (ya hay config en `.vercel/`): build = `npm run build`, output = `dist`
- [ ] Configurar env `VITE_API_URL` apuntando a la URL del backend (en Fase 4 pasa a ser la de Railway; mientras, puede apuntar al VPS actual o quedar vacío con proxy local)
- [ ] Verificar deploy: panel carga, login funciona contra el backend actual
- [ ] Limpiar `docker-compose.yml`: eliminar servicios `nginx`, `frontend-build`, volúmenes `webroot`, `staticfiles`
- [ ] Actualizar `ngrok` en el compose de dev: apuntar a `http://api-backend:8000` (antes iba a `nginx:80`)
- [ ] Actualizar `scripts/telegram-webhook-sync.sh` si referencia el puerto 8080/nginx

**Verificación:** `vercel deploy` exitoso · navegación del panel completa · compose de dev (`api-backend` + `postgres` + `ngrok`) sigue funcionando local.

---

## Fase 3 — Base de datos → Neon (~1 día)

- [ ] Crear proyecto free en [Neon](https://neon.tech) (0.5 GB, autosuspend 5 min, sin tarjeta)
- [ ] Dump del Postgres local:
  ```bash
  docker compose exec postgres pg_dump -U postgres smartbooking > /tmp/smartbooking_dump.sql
  ```
- [ ] Restaurar en Neon: `psql "$NEON_DATABASE_URL" < /tmp/smartbooking_dump.sql`
- [ ] Ejecutar migraciones pendientes contra Neon: `alembic upgrade head` con `DATABASE_URL` de Neon
- [ ] Verificar con la suite completa: 203 tests verdes
- [ ] Cambiar `DATABASE_URL` en el backend desplegado (Fase 4) y probar lectura/escritura real (crear una cita de prueba, borrarla)

**Verificación:** `pg_dump` de Neon idéntico en conteo de filas de tablas clave (`appointments`, `services`, `customers`) · primera query tras 5 min de inactividad responde (wake).

---

## Fase 4 — Backend → Railway + cron + quitar Redis (~1–1.5 días)

### 4.1 Deploy del backend
- [ ] Crear proyecto en Railway e importar el repo (root: `backend/api-backend`, Dockerfile existente)
- [ ] Variables de entorno: `DATABASE_URL` (Neon), `OPENAI_API_KEY`, `META_WABA_TOKEN`, `META_APP_SECRET`, `META_VERIFY_TOKEN`, `TELEGRAM_BOT_TOKEN`, `TIMEZONE=America/Santo_Domingo`, flags de la Fase 1, `DISABLE_USAGE_LIMITS` según corresponda
- [ ] Comando de arranque: `uvicorn main:app --host 0.0.0.0 --port $PORT --workers 1` (ajustar `entrypoint.sh`/Dockerfile si hace falta)
- [ ] Health check: `GET /docs` y `GET /` responden en la URL de Railway

### 4.2 Cron externo (sustituye APScheduler en proceso)
- [ ] Agregar endpoint interno protegido por `INTERNAL_CRON_TOKEN`:
  - `POST /internal/jobs/reminders` → `process_appointment_reminders()`
  - `POST /internal/jobs/waitlist-expiration` → `process_waitlist_expiration()` (solo si 1.2 activa)
  - (`generate_daily_agenda` queda fuera por 1.3)
- [ ] Crear servicios cron en Railway (o GitHub Actions): reminders cada ~10 min
- [ ] Desactivar `AsyncIOScheduler` en arranque cuando `CRON_EXTERNAL=true` (`app/core/scheduler.py`)

### 4.3 Quitar Redis
- [ ] Simplificar `app/services/rate_limit_async.py`: solo camino en memoria (el fallback ya existe)
- [ ] Quitar `redis` de `requirements.txt` y `REDIS_URL` de envs/`.env.example`

### 4.4 Reconfigurar webhooks
- [ ] WhatsApp: actualizar la URL del webhook en la app de Meta → `https://<railway>/webhooks/whatsapp` (verificar token `META_VERIFY_TOKEN`)
- [ ] Telegram: `setWebhook` a `https://<railway>/webhooks/telegram` (adaptar `scripts/telegram-webhook-sync.sh`)
- [ ] Actualizar `VITE_API_URL` en Vercel → URL de Railway

**Verificación:** mensaje de prueba por ambos canales con el servicio despierto responde correctamente · el cron dispara recordatorios sin scheduler en proceso.

---

## Fase 5 — Prueba de frío de webhooks (~medio día)

Protocolo:

1. [ ] Dejar el servicio dormir 30 min (cero tráfico)
2. [ ] Enviar mensaje por **WhatsApp** → medir tiempo hasta la respuesta
3. [ ] Enviar mensaje por **Telegram** → medir lo mismo
4. [ ] Verificar en `ProcessedChannelEvent` que cada evento se procesó **una sola vez** (idempotencia)

**Umbral de decisión:**
- ✅ Latencia total < ~60 s y cero duplicados → se sigue con Railway durmiendo
- ⚠️ Latencia 1–3 min pero sin pérdidas → aceptable; documentar
- ❌ Mensajes perdidos o latencia > 3 min consistente → **decisión**: instancia mínima en Railway (~$10/mes) o **plan B**: VPS Hetzner (~€4–5/mes) con el compose actual

---

## Fase 6 — Validación final (criterios de salida)

- [ ] 203 tests backend verdes (local + contra Neon)
- [ ] 33 tests frontend verdes
- [ ] Flujo E2E manual completo:
  - WhatsApp: agendar (menú guiado → fecha → slot → confirmar) · cancelar · consultar
  - Telegram: ídem
  - Panel web: el dueño ve la cita creada por el bot; crea/edita servicio con buffer; ve el calendario
- [ ] Recordatorio 24h/2h llega desde el cron externo
- [ ] Costos confirmados en dashboards: Vercel $0 · Neon $0 · Railway ~$5
- [ ] `README.md` actualizado con la nueva arquitectura de producción

---

## Riesgos y rollback

| Fase | Riesgo | Rollback |
|---|---|---|
| 1 | Un flag rompe un flujo | Revertir flag a `true` — sin cambios de código estructurales |
| 2 | Deploy de Vercel roto | El compose de dev sigue sirviendo la SPA; restaurar servicios nginx/frontend-build |
| 3 | Datos incompletos en Neon | El volumen `postgres_data` local queda intacto; apuntar `DATABASE_URL` de vuelta |
| 4 | Railway no despierta a tiempo | Plan B VPS con compose; el código no cambió |
| 4 | Cron externo no dispara | Re-activar `AsyncIOScheduler` con `CRON_EXTERNAL=false` |
| 5 | WhatsApp pierde eventos en frío | Instancia mínima o plan B (ver umbral) |

---

## Backlog v1.1 (reactivable, nada se perdió)

- Canal de comandos del owner en Telegram (spec 002/003 completo)
- Waitlist con auto-oferta FIFO + job de expiración
- Agenda diaria del owner a las 8:00
- Verificación de email + rotación de invite/unlink de Telegram
- Endpoint `restore` de excepciones · categoría/ubicación del negocio
- Variante $0 total: API en funciones serverless (requiere refactor de rate limiter y pools)
- Phase 6: pagos, multi-negocio, roles, auditoría avanzada, CI/CD

---

## Estimación total: 3–5 días de trabajo

| Fase | Tiempo |
|---|---|
| 0 — Cierre del repo | 2–3 h |
| 1 — Poda funcional | 1 día |
| 2 — Vercel | medio día |
| 3 — Neon | 1 día |
| 4 — Railway + cron + Redis | 1–1.5 días |
| 5 — Prueba de frío | medio día |
| 6 — Validación final | medio día |

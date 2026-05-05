# Implementation Plan: Canal De Comandos Del Dueño

**Branch**: `002-owner-command-channel` | **Date**: 2026-04-29 | **Spec**: `specs/002-owner-command-channel/spec.md`  
**Input**: Feature specification for an owner-only command channel.

## Summary

Crear un canal administrativo separado para dueños, empezando por Telegram y operaciones de solo lectura: agenda de hoy, agenda de mañana, próximas citas, métricas de hoy y detalle de cita. El MVP limita cada owner a un único negocio activo; frontend y backend deben impedir exponer multi-negocio hasta planes de pago.

## Technical Context

**Language/Version**: Python/FastAPI backend; React/Vite/TypeScript frontend.  
**Primary Dependencies**: FastAPI, SQLAlchemy, Alembic, Telegram Bot API, Zustand/React Query.  
**Storage**: PostgreSQL. Probable nueva tabla `owner_channel_bindings`; sin multi-business selector en MVP.  
**Testing**: pytest backend; frontend unit/E2E si el flujo UI se modifica.  
**Target Platform**: Telegram owner channel + existing web admin panel.  
**Project Type**: Web app + backend conversational admin feature.  
**Performance Goals**: Responder agenda/métricas en menos de 5 segundos para negocio MVP.  
**Constraints**: owner auth, one active business per owner, no admin mutation in phase 1, timezone `America/Santo_Domingo`.  
**Scale/Scope**: MVP owner operations for one business.

## Constitution Check

- Specs-first: PASS.
- Tenant safety: REQUIRED, owner channel must verify owner/business binding.
- Deterministic actions: PASS, phase 1 is read-only.
- Guided conversation first: PASS, owner menu is guided.
- Channel parity: NOT REQUIRED for owner channel MVP; Telegram first is intentional.
- Tests before sensitive changes: REQUIRED for auth/binding/business limit/metrics.

## Project Structure

### Documentation (this feature)

```text
specs/002-owner-command-channel/
├── spec.md
├── plan.md
├── research.md
├── quickstart.md
├── contracts/
│   └── owner-command-channel.md
└── tasks.md
```

### Source Code (repository root)

```text
backend/api-backend/app/
├── api/businesses.py
├── api/owners.py
├── models.py
├── services/telegram_inbound.py
├── services/owner_command_router.py
└── services/background_tasks.py

frontend/src/
├── components/Sidebar.tsx
├── pages/BusinessOnboarding.tsx
├── pages/BusinessSettings.tsx
├── pages/TelegramIntegration.tsx
└── store/businessStore.ts
```

**Structure Decision**: Crear owner command channel separado del flujo de clientes. No reutilizar `TelegramUserBinding` para permisos de dueño.

## MVP Business Limit

Para el MVP:

- Un owner puede tener un solo negocio activo.
- Backend debe rechazar `POST /api/businesses/` si el owner ya tiene negocio activo.
- Frontend debe ocultar o deshabilitar “Nuevo negocio” cuando `businesses.length >= 1`.
- Frontend no debe mostrar selector multi-negocio en MVP; si hay múltiples por datos heredados, mostrar estado de soporte/configuración requerida.
- Multi-negocio queda en `docs/PHASE6_BACKLOG.md` y requiere planes de pago.

## Telegram Payload Separation

El bot Telegram actual usa `/start <token>` para clientes. El canal del dueño debe evitar colisiones:

- Cliente: mantener formato actual `/start <business_invite_token>`.
- Dueño: usar formato explícito `/start owner_<owner_activation_token>`.
- El webhook debe resolver el prefijo antes de llamar a `resolve_invite_token()` de clientes.
- El token de dueño debe apuntar a `owner_id + business_id`, expirar y ser rotatable desde panel.
- No elegir negocio automáticamente si el owner tiene más de un negocio heredado.

Estado implementado:

- Modelo y migración Alembic `e5f6a7b8c9d0` crean `owner_channel_bindings`.
- Endpoint autenticado: `GET /api/businesses/{business_id}/owner-telegram`.
- Payload de activación: `/start owner_<token>`.
- `telegram_inbound.py` resuelve payloads `owner_` antes de tokens de cliente.
- Si el owner tiene múltiples negocios heredados, el endpoint responde `409` y pide soporte.

## Metrics Contract

Métricas de hoy usan ventana local `America/Santo_Domingo`:

- Total: `P + C + A + D`
- Pendientes: `P`
- Confirmadas: `C`
- Completadas: `D`
- Canceladas: `A`
- Ingresos estimados: suma de precios de citas `P + C`
- Ingresos realizados: suma de precios de citas `D`

## Owner Channel Phasing

Phase 1:

- Vinculación segura desde panel.
- Menú del dueño.
- Agenda de hoy.
- Agenda de mañana.
- Próximas citas.
- Métricas de hoy.
- Detalle de cita, solo lectura.

Phase 2:

- Marcar completada.
- Cancelar cita.
- Reagendar cita.
- Bloquear horario.
- Editar notificaciones.

Phase 3:

- Servicios/precios/horarios avanzados.
- Roles, recepcionistas, multi-negocio por plan.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Telegram-only owner MVP | Reduce risk and ship faster | WhatsApp owner commands add 24h-window and identity complexity |
| New owner binding entity | Separates owner permissions from clients | Reusing `TelegramUserBinding` would mix customer and owner identities |

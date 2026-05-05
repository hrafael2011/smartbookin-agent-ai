# Implementation Plan: Project Baseline

**Branch**: `000-project-baseline` | **Date**: 2026-04-29 | **Spec**: `specs/000-project-baseline/spec.md`  
**Input**: Estado actual del repo, documentación existente y constitución Spec Kit.

## Summary

Documentar SmartBooking AI como sistema brownfield ya avanzado: backend FastAPI, frontend React, canales WhatsApp/Telegram, PostgreSQL, Alembic, scheduler y NLU con OpenAI. Esta baseline no implementa funcionalidad; establece una fuente de verdad para futuras specs.

## Technical Context

**Language/Version**: Python 3.12 compatible en entorno actual; Node/TypeScript para frontend.  
**Primary Dependencies**: FastAPI, SQLAlchemy async, Alembic, React, Vite, Zustand, React Query, TailwindCSS, OpenAI SDK, httpx.  
**Storage**: PostgreSQL; contexto conversacional en `conversation_states`; límites pueden usar Redis si `REDIS_URL` existe.  
**Testing**: pytest para backend, Playwright para frontend E2E.  
**Target Platform**: Linux server / Docker Compose local.  
**Project Type**: Web app + API backend + conversational webhooks.  
**Performance Goals**: Mantener rutas determinísticas sin IA para menú, confirmaciones y selecciones numéricas.  
**Constraints**: Multi-tenant por `business_id`; acciones críticas requieren confirmación; paridad WhatsApp/Telegram.  
**Scale/Scope**: MVP para barberías/salones con potencial multi-negocio y multi-canal.

## Constitution Check

- Specs-first: PASS, esta baseline crea el punto de partida.
- Tenant safety: PASS, entidades y rutas documentan propiedad por negocio.
- IA como intérprete: PASS, se declara como principio del sistema.
- Guided conversation first: PASS, queda como dirección de la próxima feature.
- Channel parity: PASS, WhatsApp y Telegram se documentan como comportamiento compartido.
- Tests for sensitive changes: PASS, no hay cambios funcionales en esta baseline.

## Project Structure

### Documentation (this baseline)

```text
specs/000-project-baseline/
├── spec.md
├── plan.md
├── research.md
├── architecture.md
├── implementation-methodology.md
└── quickstart.md
```

### Source Code (repository root)

```text
backend/api-backend/
├── main.py
├── app/
│   ├── api/
│   ├── core/
│   ├── handlers/
│   ├── services/
│   ├── utils/
│   └── models.py
├── alembic/
└── tests/

frontend/
├── src/
│   ├── components/
│   ├── pages/
│   ├── services/
│   ├── store/
│   └── types/
└── e2e/

docs/
└── historical and support notes
```

**Structure Decision**: Mantener monorepo actual. Specs nuevas viven en `specs/`; documentación auxiliar permanece en `docs/`.

## Current Architecture

- `main.py` registra FastAPI, CORS, rate limit HTTP, routers REST y webhooks.
- REST API protege rutas de dueño con JWT y `get_current_owner`.
- Conversación pasa por `run_conversation_turn`, que combina atajos determinísticos, NLU y handlers.
- Handlers principales: booking, check, cancel, modify, business info.
- `conversation_manager` persiste contexto por `business_id + phone_number/user_key`.
- `db_service` concentra consultas de negocio, disponibilidad y entidades conversacionales.
- APScheduler ejecuta recordatorios, expiración de waitlist y agenda diaria.
- Frontend consume `/api` mediante Axios con refresh token automático.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Ninguna | N/A | N/A |

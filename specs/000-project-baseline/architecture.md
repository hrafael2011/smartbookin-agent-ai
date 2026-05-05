# Architecture & Design Patterns

## Architectural Shape

SmartBooking AI is a web app plus conversational backend:

```text
Channel Adapter -> Guided Router -> Orchestrator -> Handler -> Service -> Database/Provider
Frontend Admin  -> REST API       -> Service/Model -> Database
Scheduler       -> Service        -> Database/Provider
```

The main rule is separation of delivery mechanics from business decisions:

- WhatsApp and Telegram receive/send messages.
- Routers decide deterministic navigation.
- Orchestrator coordinates conversation state and NLU.
- Handlers execute business flows.
- Services own persistence, availability, external clients and read models.

## Patterns

### Channel Adapter

WhatsApp and Telegram are adapters. They should normalize inbound messages and send outbound responses, but they should not contain booking, owner, menu or metrics business rules.

Examples:

- WhatsApp webhook in `backend/api-backend/main.py`
- Telegram inbound in `backend/api-backend/app/services/telegram_inbound.py`

### Guided Router

Guided routers classify deterministic commands before IA:

- client menu router for customer flows,
- owner command router for owner/admin flows.

Routers should be mostly deterministic and testable without network or database when possible.

### Orchestrator

The orchestrator coordinates NLU, active state and handler dispatch. It should not duplicate channel-specific code and should not create side effects that belong in handlers.

### Handler

Handlers own a user journey such as booking, cancelling, checking or modifying appointments. Critical actions happen here only after validation and confirmation.

### Service Layer

Services wrap database queries, external providers, availability logic, Telegram/WhatsApp clients and read models. Webhooks and pages should not embed complex SQL or provider logic.

### State Machine

Conversation state is explicit. Numeric input is interpreted according to state:

- `idle`: global menu options.
- active flow: list selection or confirmation for that flow.

### Command Pattern

Owner actions should be modeled as commands, even if implemented as functions in MVP:

- `ViewTodayAgenda`
- `ViewTomorrowAgenda`
- `ViewDailyMetrics`
- future: `CancelAppointment`, `BlockTime`, `MarkDone`

Each command must validate owner/business binding and return a safe response model.

### Read Model

Operational views such as owner agenda and daily metrics should return read models, not raw ORM rows:

- `OwnerAgendaItem`
- `OwnerDailyMetrics`

This keeps formatting and permission checks separate from persistence.

### Fail-Safe UX

When uncertain or failing:

- do not invent data,
- do not mutate,
- return to menu or a narrow next step,
- log enough context to debug without leaking secrets.

### Persistent Idempotency

Webhook retries must not repeat critical actions. The MVP production strategy is PostgreSQL-backed idempotency on Railway:

- `processed_channel_events` stores processed WhatsApp/Telegram event ids.
- A unique constraint on `channel`, `business_id`, `user_key`, `event_id` is the source of truth.
- Insert success means process the event; duplicate insert means return `ok` and skip mutation.
- Redis is not required for this MVP concern.
- Implementation lives in `app.services.idempotency` and Alembic revision `d4e5f6a7b8c9`.

## Boundaries

- Client channel and owner channel are separate products with different permissions.
- `TelegramUserBinding` is for customers; owner commands require an owner-specific binding.
- MVP supports one business per owner in product flows. Backend rejects additional creation, and frontend hides multi-business creation/selection. Multi-business is a future paid-plan feature.

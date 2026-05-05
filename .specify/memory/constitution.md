# SmartBooking AI Constitution

## Core Principles

### I. Specs Are The Source Of Truth

Every significant product or architecture change MUST start from a Spec Kit artifact before implementation. The current system baseline lives in `specs/000-project-baseline/`; new work MUST reference or extend that baseline instead of relying on scattered notes, chat memory, or ad hoc assumptions.

When existing documentation conflicts, the precedence order is:

1. Active feature spec and plan in `specs/`
2. This constitution
3. Current source code
4. Historical documents in `docs/`, `PROJECT_SUMMARY.txt`, or status files

### II. Tenant Safety And Ownership Boundaries

SmartBooking AI is multi-tenant by `business_id`. Any backend route, webhook flow, scheduler job, or background action that reads or mutates business data MUST preserve tenant boundaries. Owner-facing REST APIs MUST verify ownership before exposing business, customer, appointment, service, schedule, or channel configuration data.

Channel bindings such as Telegram user links and WhatsApp phone number IDs MUST resolve to a single active business context before any conversational flow can operate.

### III. Deterministic Actions, IA As Interpreter

The IA MAY interpret user text into intent, date, time, service, or clarification signals. The IA MUST NOT be treated as the authority that creates, cancels, modifies, or confirms appointments.

The IA MUST NOT invent business facts such as prices, services, schedules, availability, addresses, policies, or customer appointments. Business facts MUST come from persisted data or deterministic services.

Critical actions MUST be executed only by deterministic handlers after:

- valid tenant context exists,
- the conversation state permits the action,
- required data has been validated against persisted business data,
- the user gives explicit confirmation when the action is destructive or commits a booking.

### IV. Guided Conversation First

For the MVP phase, the bot experience MUST prefer guided, numbered flows over open-ended conversation. Greetings, help requests, ambiguous messages, unsupported requests, and low-confidence interpretation MUST return the user to clear menu options or a narrow next question.

Direct natural-language shortcuts are allowed only as accelerators into guided flows. After interpreting a shortcut, the system MUST continue with deterministic steps and explicit confirmation.

Conversational precedence is:

1. If a flow is active, the active `ConversationState` decides how to interpret the user message.
2. If the state is `idle`, the guided menu and deterministic capability router decide first.
3. IA is used only after deterministic routing cannot safely classify the message.
4. Execution remains in handlers and services, never in IA output.

### V. Channel Parity

WhatsApp and Telegram MUST share the same product behavior for booking, checking, modifying, cancelling, business info, menu routing, abuse handling, and fallbacks. Channel-specific clients may differ in delivery mechanics, but business logic MUST remain centralized or intentionally mirrored with tests.

Text-numbered menus are the default cross-channel interface. Interactive buttons are optional enhancements and MUST NOT become required for core flows unless both channels have equivalent fallback behavior.

### VI. Security, Limits, And Operational Safety

Authentication uses JWT access tokens plus opaque refresh tokens. Owner routes MUST stay protected. Webhooks MUST validate channel-specific trust where available, such as Meta signatures for WhatsApp.

Rate limits and daily usage limits MUST preserve guided-mode availability whenever possible. If an IA quota is exhausted, deterministic menu flows should remain usable unless the total daily limit is reached.

Webhook processing and critical mutations MUST be safe under retries and concurrency. Duplicate inbound events MUST NOT create duplicate appointments or repeat destructive actions. Availability MUST be revalidated at the point of booking confirmation.

Date/time behavior MUST use a consistent business timezone. Unless a future spec introduces per-business timezone support, the default operational timezone is `America/Santo_Domingo`.

### VII. Tests Before Sensitive Changes

Changes to booking, cancellation, modification, tenant resolution, authentication, refresh tokens, channel routing, or scheduler behavior MUST include focused automated tests. Tests should verify behavior, not implementation trivia.

For conversational work, tests MUST cover at least:

- no IA call for deterministic menu paths,
- numeric menu options in `idle`,
- numeric selections inside active flows,
- explicit confirmation before mutation,
- WhatsApp/Telegram parity for the changed behavior.

## Project Constraints

- Primary backend: FastAPI, SQLAlchemy async, Alembic, PostgreSQL.
- Primary frontend: React, Vite, TypeScript, Zustand, React Query, TailwindCSS.
- Channels: WhatsApp Cloud API and Telegram Bot API.
- IA provider: OpenAI through the backend NLU service.
- Local orchestration: Docker Compose with PostgreSQL, backend, frontend build, Nginx, optional ngrok.
- Main documentation language: Spanish. Technical names, APIs, paths, schemas, commands, and identifiers remain in English when they are source-level concepts.
- MVP commercial constraint: one active business per owner. Multi-business support requires a future paid-plan spec with usage limits, quotas, and abuse controls before it can be exposed in backend or frontend product flows.

## Development Workflow

1. Capture or update a spec in `specs/`.
2. Clarify product behavior before choosing implementation details.
3. Create or update the technical plan.
4. Break implementation into tasks.
5. Implement only from accepted tasks.
6. Run relevant tests and update documentation when behavior changes.

No implementation should introduce new product policy that is absent from the active spec, unless it is a small bug fix that restores already documented behavior.

Implementation MUST be divided into small phases. Each task SHOULD declare the intended verification profile and reasoning mode:

- `low`: mechanical edits, small tests, copy existing patterns.
- `medium`: normal implementation across a few files, integration of existing modules.
- `high`: architecture, security, migrations, auth, channel routing, concurrency, or hard debugging.

Use the lowest mode that is safe for the task. Before starting a task marked `high`, ask the user to switch to high mode. Do not spend high-mode reasoning on mechanical or repetitive edits.

Verification SHOULD use `scripts/verify-mvp.sh` with the smallest profile that covers the change. Full suites are reserved for phase completion or high-risk changes.

## Governance

This constitution supersedes informal project notes. Amendments require a documented reason, the affected specs, and the migration impact on existing code or docs.

Versioning follows semantic intent:

- MAJOR: changes to non-negotiable product or architecture principles.
- MINOR: new principles or workflow gates.
- PATCH: wording clarifications that do not change requirements.

**Version**: 1.0.1 | **Ratified**: 2026-04-29 | **Last Amended**: 2026-04-29

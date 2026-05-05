# Implementation Methodology

## Goal

Keep implementation safe, incremental and token-efficient. Every feature should move in small blocks with clear tests and a declared reasoning mode.

## Phase Template

Each phase should include:

- Objective
- Scope
- Files likely touched
- Test profile
- Recommended mode: `low`, `medium` or `high`
- Exit criteria

## Reasoning Modes

### low

Use for:

- small tests,
- copy/update existing patterns,
- documentation edits,
- UI copy changes,
- simple one-file fixes.

### medium

Use for:

- normal feature implementation,
- integration across 2-4 files,
- adding routes/services using existing patterns,
- resolving ordinary test failures.

### high

Use for:

- security/auth changes,
- migrations and schema design,
- channel routing architecture,
- concurrency/idempotency,
- complex debugging,
- decisions that affect product policy.

Before starting a `high` task, ask the user to switch to high mode.

## Verification Script

Use:

```bash
./scripts/verify-mvp.sh <profile>
```

Profiles:

- `backend-unit`: pure backend unit tests.
- `backend-conversation`: orchestrator, handlers and webhook routing tests.
- `backend-api`: auth/security/business/API-oriented tests.
- `backend-owner`: future owner-channel tests.
- `frontend`: lint and build.
- `e2e`: Playwright E2E.
- `all`: all supported profiles.

Prefer the smallest profile that covers the change. Run `all` at phase boundaries or before delivery.

## MVP Implementation Blocks

### Block A - Methodology And Test Harness

Objective: establish docs and verification script.

Mode: `low`

Tests: run `./scripts/verify-mvp.sh backend-unit` if dependencies are available.

### Block B - Guided Client Menu

Objective: implement `001-guided-menu-bot`.

Mode:

- `high` for router architecture, quota ordering and idempotency decisions.
- `medium` for channel integration and handler changes.
- `low` for copy and straightforward tests.

Tests:

- `backend-conversation`
- targeted backend unit tests

### Block C - One Business MVP Limit

Objective: enforce one active business per owner in backend and frontend.

Status: implemented for MVP. Backend rejects additional business creation with `409 Conflict`; frontend hides “Nuevo negocio” and does not expose multi-business selection.

Mode:

- `medium` for backend/frontend implementation.
- `high` only if data migration or inherited multi-business cleanup is required.

Tests:

- `backend-api`
- `frontend`

### Block D - Owner Command Channel Read-Only

Objective: implement `002-owner-command-channel` phase 1.

Mode:

- `high` for owner binding schema/auth and Telegram `/start owner_` separation.
- `medium` for read-only commands and frontend activation UI.
- `low` for copy and simple display states.

Tests:

- `backend-owner`
- `backend-api`
- `frontend`

### Block E - Hardening

Objective: full validation, edge cases, docs sync.

Mode: `medium`; use `high` only for hard bugs.

Tests:

- `all`

### Block F - Persistent Idempotency On Railway PostgreSQL

Objective: replace process-memory duplicate-event guard with persistent idempotency using the existing PostgreSQL service on Railway.

Status: implemented with Alembic revision `d4e5f6a7b8c9` and service `app.services.idempotency`.

Mode:

- `high` for schema design, Alembic migration and concurrent insert behavior.
- `medium` for service integration and tests.

Tests:

- `backend-conversation`
- `backend-api`
- `backend-all` at phase exit

Decision:

- Use PostgreSQL/Railway, not Redis, for MVP duplicate webhook protection.
- Add `processed_channel_events` with a unique constraint on `channel`, `business_id`, `user_key`, `event_id`.
- The idempotency service should attempt an atomic insert; duplicate-key means return `ok` without repeating mutations.

## Token Efficiency Rules

- Do not run full suites after every tiny edit.
- Do not use high mode for mechanical changes.
- Prefer targeted tests first, full verification at phase exits.
- Keep implementation aligned with specs; avoid speculative refactors.
- Stop and update specs if implementation reveals a product decision gap.

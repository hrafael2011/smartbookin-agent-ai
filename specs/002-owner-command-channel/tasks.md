# Tasks: Canal De Comandos Del Dueño

**Input**: `spec.md`, `plan.md`, `research.md`, `contracts/owner-command-channel.md`  
**Prerequisites**: `specs/000-project-baseline/`

## Implementation Guidance

- Ask the user to switch to **high** before schema/migration tasks T008-T013 and Telegram owner/customer separation T016-T017.
- Use **medium** for frontend/backend implementation tasks.
- Use **low** for copy and quickstart updates.
- Prefer `./scripts/verify-mvp.sh backend-owner`, `backend-api`, and `frontend` for this feature.

## Phase 1: MVP Business Limit

**Mode**: medium  
**Verify**: `./scripts/verify-mvp.sh backend-api` and `./scripts/verify-mvp.sh frontend`

- [x] T001 Add backend test: owner cannot create second active business during MVP.
- [x] T002 Update `backend/api-backend/app/api/businesses.py` to reject `POST /api/businesses/` when current owner already has an active business.
- [x] T003 Add backend test: owner with multiple inherited businesses cannot generate owner-channel activation until resolved.
- [x] T004 Add frontend test or manual validation: `Sidebar.tsx` hides “Nuevo negocio” when `businesses.length >= 1`.
- [x] T005 Update `frontend/src/components/Sidebar.tsx` to remove/hide multi-business selector and “Nuevo negocio” for existing-business owners in MVP.
- [x] T006 Ensure `frontend/src/pages/BusinessOnboarding.tsx` is reachable only when owner has zero businesses.
- [x] T007 Update user-facing copy to explain multi-business requires a future plan if needed.

## Phase 2: Owner Binding

**Mode**: high  
**Verify**: `./scripts/verify-mvp.sh backend-owner` and `./scripts/verify-mvp.sh backend-api`

- [x] T008 Add `OwnerChannelBinding` model and Alembic migration.
- [x] T009 Add backend schemas for owner channel activation.
- [x] T010 Add authenticated endpoint to generate owner Telegram activation token/link for the active business.
- [x] T011 Use `/start owner_<token>` payloads for owner activation to avoid collision with customer invite tokens.
- [x] T012 Add service to resolve owner activation token and create binding.
- [x] T013 Add tests for binding ownership, expired/invalid token, duplicate binding and customer/owner token separation.

## Phase 3: Owner Command Router

**Mode**: high for T016-T017, otherwise medium  
**Verify**: `./scripts/verify-mvp.sh backend-owner`

- [x] T014 Create `backend/api-backend/app/services/owner_command_router.py`.
- [x] T015 Implement owner menu and navigation `0`, `9`, `x`.
- [x] T016 Route owner Telegram updates separately from customer Telegram binding.
- [x] T017 Ensure `telegram_inbound.py` classifies `/start owner_<token>` before customer `resolve_invite_token()`.
- [x] T018 Ensure unbound Telegram users cannot access owner commands.
- [x] T019 Add 30-minute timeout for owner command sessions.

## Phase 4: Read-Only Owner Commands

**Mode**: medium  
**Verify**: `./scripts/verify-mvp.sh backend-owner`

- [x] T020 Implement agenda of today query using `America/Santo_Domingo`.
- [x] T021 Implement agenda of tomorrow query using `America/Santo_Domingo`.
- [x] T022 Implement upcoming appointments query.
- [x] T023 Implement daily metrics query: counts and estimated/realized revenue.
- [x] T024 Implement appointment detail view from numbered agenda.
- [x] T025 Add tests for empty agenda, missing service price and status calculations.

## Phase 5: Frontend Owner Channel Entry

**Mode**: medium  
**Verify**: `./scripts/verify-mvp.sh frontend`

- [x] T026 Add panel page or section for “Canal del dueño” activation.
- [x] T027 Reuse visual patterns from `TelegramIntegration.tsx` but distinguish owner channel from customer booking link.
- [x] T028 Show active/inactive owner binding state.
- [x] T029 Do not expose multi-business owner-channel selection in MVP.

## Phase 6: Validation And Docs

**Mode**: low for docs, medium for validation failures  
**Verify**: `./scripts/verify-mvp.sh backend-all`, `./scripts/verify-mvp.sh frontend`

- [x] T030 Run backend tests for business limit, owner binding, owner commands and metrics.
- [x] T031 Run frontend build/lint or targeted UI tests if available.
- [x] T032 Update `quickstart.md` with real endpoint/UI paths after implementation.
- [x] T033 Record phase 2 actions (cancel/reagendar/block/complete) as future spec before implementation.

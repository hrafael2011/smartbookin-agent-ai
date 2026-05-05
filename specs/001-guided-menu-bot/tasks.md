# Tasks: Bot Con Menú Guiado Híbrido

**Input**: `spec.md`, `plan.md`, `research.md`, `quickstart.md`  
**Prerequisites**: Baseline en `specs/000-project-baseline/`

## Implementation Guidance

- Ask the user to switch to **high** before T013, T017, T020 and T031.
- Use **medium** for channel integration and orchestrator edits.
- Use **low** for copy, docs and straightforward tests.
- Prefer `./scripts/verify-mvp.sh backend-conversation` for this feature; use `backend-all` at the phase exit.

## Phase 1: Tests First

**Mode**: medium  
**Verify**: `./scripts/verify-mvp.sh backend-conversation`

- [x] T001 [P] Add tests in `backend/api-backend/tests/test_guided_menu_router.py` for pure routing: greetings/menu/help, options `1`-`5`, ambiguous, off-domain and rude text.
- [x] T002 [P] Add test coverage: `hola` in `idle` returns menu and does not call NLU.
- [x] T003 [P] Add test coverage: option `1` in `idle` starts booking without NLU.
- [x] T004 [P] Add active-flow precedence test: `1` in `awaiting_slot_selection` selects a slot and does not trigger global menu.
- [x] T005 [P] Add fallback tests: ambiguous, off-domain and rude messages return professional boundary/menu without mutation.
- [x] T006 [P] Add webhook parity tests in `backend/api-backend/tests/test_webhook_endpoints_ci.py` for WhatsApp and Telegram deterministic menu routing.
- [x] T007 [P] Add quota behavior tests: exhausted IA quota does not block deterministic menu routes; exhausted total quota blocks all chat interactions.
- [x] T008 [P] Add navigation tests for `0/menu`, `9/volver`, and `x/salir` from active booking states.
- [x] T009 [P] Add timeout tests: active flow older than 30 minutes clears state/pending data and returns menu on next message.
- [x] T010 [P] Add idempotency test for duplicate channel message/event around booking confirmation.
- [x] T011 [P] Add availability race test: selected slot becomes unavailable before confirmation and appointment is not created.
- [x] T012 [P] Add incomplete-business tests for no services, no schedule and missing location.

## Phase 2: Shared Routing Module

**Mode**: high for T013/T017/T020, otherwise medium  
**Verify**: `./scripts/verify-mvp.sh backend-conversation`

- [x] T013 Create `backend/api-backend/app/services/guided_menu_router.py` with `RouteDecision`, `route_guided_message()` and `execute_guided_route()`.
- [x] T014 Move option execution for `1`-`5` from WhatsApp/Telegram-specific code into `execute_guided_route()`.
- [x] T015 Implement active-flow rule: global numeric options apply only when `context["state"] == "idle"`.
- [x] T016 Implement universal navigation decisions: `go_main_menu`, `go_back`, `exit_flow`.
- [x] T017 Implement 30-minute passive active-flow timeout decision: `expired_flow`.
- [x] T018 Implement explicit `menu` escape for active flows using safe context cleanup before showing menu.
- [x] T019 Implement deterministic off-domain and rude-message boundaries with conservative keyword matching.
- [x] T020 Ensure `RouteDecision.uses_ai` is the only source used by channels for AI quota classification.

## Phase 3: Channel Integration

**Mode**: medium  
**Verify**: `./scripts/verify-mvp.sh backend-conversation`

- [x] T021 Update WhatsApp webhook in `backend/api-backend/main.py`: resolve business/context, call shared router, consume quota with `decision.uses_ai`, then execute route or pass to orchestrator.
- [x] T022 Update Telegram inbound in `backend/api-backend/app/services/telegram_inbound.py`: preserve binding/onboarding, call shared router, consume quota with `decision.uses_ai`, then execute route or pass to orchestrator.
- [x] T023 Remove duplicated `_handle_guided_menu_choice()` behavior from Telegram after shared router handles options.
- [x] T024 Preserve Telegram onboarding/name capture and business binding before guided routing.
- [x] T025 Preserve WhatsApp signature validation, business phone-number mapping and mark-as-read behavior.
- [x] T026 Ensure both channels still save assistant/user messages consistently when guided router returns a response.

## Phase 4: IA Boundaries, Orchestrator And Safeguards

**Mode**: high for T030-T032, otherwise medium  
**Verify**: `./scripts/verify-mvp.sh backend-conversation`

- [x] T027 Update `backend/api-backend/app/core/orchestrator.py` so low-confidence NLU returns guided fallback instead of open-ended fallback.
- [x] T028 Ensure direct shortcuts from `idle` may call NLU for interpretation but always continue through handlers and confirmation.
- [x] T029 Ensure NLU result fields are treated as hints only; handlers must still validate services, availability, appointments and confirmation.
- [x] T030 Verify booking confirmation revalidates selected slot immediately before creating appointment; patch if any path bypasses it.
- [x] T031 Add duplicate-message guard for critical actions using available channel `message_id` or context-level processed event tracking.
- [x] T032 Ensure date/time messages and relative parsing use `America/Santo_Domingo` consistently for this phase.
- [x] T033 Add lightweight route/action logging for deterministic menu, direct shortcut, fallback, navigation, timeout, active-flow routing and critical mutations.

## Phase 5: Documentation And Validation

**Mode**: low for docs, medium for validation failures  
**Verify**: `./scripts/verify-mvp.sh backend-all`

- [x] T034 Update `specs/001-guided-menu-bot/quickstart.md` with final manual test scripts after implementation.
- [x] T035 Run focused backend tests: orchestrator, guided router, webhook endpoints and affected handlers.
- [x] T036 Run full backend pytest suite if local dependencies/database setup allow it.
- [x] T037 Record any intentional behavior difference in `specs/001-guided-menu-bot/spec.md` before considering the feature complete.

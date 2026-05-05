# Tasks: Acciones Administrativas Del Dueño - Fase 2

**Input**: `spec.md`, `plan.md`
**Prerequisites**: `specs/002-owner-command-channel/`

## Implementation Guidance

- Pedir cambio a **high** antes de T014-T016 (router con estados de mutación).
- Usar **medium** para mutations y db_service.
- Usar **low** para docs y ajustes de formato.
- Verificar con `./scripts/verify-mvp.sh backend-owner`.

## Phase 1: Tests Primero

**Mode**: medium
**Verify**: `./scripts/verify-mvp.sh backend-owner`

- [x] T001 [P] Test: menú tiene opción 5 (Notificaciones) y opción 6 (Bloquear horario).
- [x] T002 [P] Test: teclas C/M/R desde `owner_appointment_detail` producen decisiones de acción.
- [x] T003 [P] Test: `format_appointment_detail` muestra C/M/R solo para P/C, no para A/D.
- [x] T004 [P] Test: flujo cancel — confirmación sí llama mutation, no vuelve al detalle.
- [x] T005 [P] Test: cita cancelada (A) no acepta acción `complete` — error `not_completable`.
- [x] T006 [P] Test: flujo reschedule — fecha inválida muestra error sin mutar.
- [x] T007 [P] Test: bloqueo con citas activas retorna error con nombres de clientes.
- [x] T008 [P] Test: bloqueo en ventana sin conflictos llama `create_time_block`.
- [x] T009 [P] Test: notificaciones toggle llama `toggle_business_notifications` y muestra estado.
- [x] T010 [P] Test: back desde `owner_cancel_confirm` vuelve al detalle de cita.
- [x] T011 [P] Test: estados de flujo (`owner_cancel_confirm`, etc.) producen `flow_input`.

## Phase 2: DB y Mutations

**Mode**: medium

- [x] T012 [P] Agregar `get_appointment_for_owner`, `mark_appointment_done`, `get_active_appointments_in_window`, `create_time_block`, `toggle_business_notifications` a `db_service.py`.
- [x] T013 [P] Crear `owner_mutations.py` con `MutationResult`, `owner_cancel_appointment`, `owner_complete_appointment`, `owner_reschedule_appointment`, `owner_block_timeslot`.

## Phase 3: Router y Formato

**Mode**: high para T014-T016, medium para el resto

- [x] T014 [P] Actualizar `owner_command_router.py`: definir `_FLOW_STATES`, extender `route_owner_command` para estados de flujo y teclas C/M/R desde detalle.
- [x] T015 [P] Implementar todos los ejecutores de flujo en `execute_owner_route` (cancel, complete, reschedule, block).
- [x] T016 [P] Implementar `_toggle_notifications` reemplazando el stub de la fase anterior.
- [x] T017 [P] Actualizar `format_appointment_detail` en `owner_read_models.py` para mostrar opciones C/M/R condicionales.
- [x] T018 [P] Actualizar `owner_menu()` para incluir opción 6 (Bloquear horario).

## Phase 4: Validación

**Mode**: low para docs, medium para fallas

- [x] T019 [P] Correr `tests/test_owner_actions_phase2.py` — 45 tests pasan.
- [x] T020 [P] Correr suite completa `tests/` — 147 tests pasan, sin regresiones.
- [x] T021 [P] Actualizar `spec.md` con diferencias de comportamiento implementadas.

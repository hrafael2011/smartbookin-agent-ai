# Tasks: Flujo de Agenda Futura (Calendario por Menú)

**Input**: `spec.md`, `plan.md`
**Prerequisites**: `specs/004-booking-flow-robustness/` (state_stack debe estar implementado)

## Phase 1: Foundation — Estados y Query Base

**Objetivo**: Registrar los nuevos estados y crear la función de disponibilidad por rango.
**Checkpoint**: Los 4 nuevos estados existen en el enum. `get_available_days_in_range` retorna correctamente.

- [x] T001 Agregar `BOOKING_CURRENT_WEEK`, `BOOKING_MONTH`, `BOOKING_WEEK`, `BOOKING_DAY` al enum `State` en `app/core/conversation_states.py`.
- [x] T002 Agregar los 4 nuevos estados a `BOOKING_FLOW_STATES` en `app/core/conversation_states.py`.
- [x] T003 Crear función `get_available_days_in_range(business_id, service_id, start_date, end_date) → List[dict]` en `app/services/db_service.py`. Retorna `[{"date": "YYYY-MM-DD", "slot_count": N, "label": "lunes 8"}, ...]` solo para días con slots.
- [x] T004 [P] Crear funciones de formato en `app/utils/date_parse.py`: `format_week_label(start, end) → str` y `format_month_label(year, month) → str`.
- [x] T005 [P] Tests para `get_available_days_in_range`: día sin slots no aparece, día con slots aparece con conteo correcto.
- [x] T006 [P] Tests para funciones de formato: `format_week_label`, `format_month_label`.

**Checkpoint**: Tests T005 y T006 pasan.

---

## Phase 2: Handler booking_current_week (P1)

**Objetivo**: Al iniciar el flujo de fecha, mostrar días disponibles de la semana actual.
**Checkpoint**: Usuario inicia "Agendar cita" → ve semana actual con días disponibles numerados + "8 → Buscar en otro mes".

- [x] T007 Crear archivo `app/handlers/booking_calendar_handler.py`.
- [x] T008 Implementar `handle_booking_current_week(business_id, user_key, service_id, context) → str` en `booking_calendar_handler.py`: calcular días restantes de semana actual, llamar a `get_available_days_in_range`, renderizar lista + opción "8". Si semana sin disponibilidad → llamar directamente a `handle_booking_month`.
- [x] T009 Actualizar `_start_booking()` en `app/services/guided_menu_router.py`: después de que el usuario elige servicio, transicionar a `booking_current_week` en lugar de `awaiting_date`. Guardar `service_id` en `pending_data`.
- [x] T010 Agregar case `booking_current_week` en `app/core/orchestrator.py`: interceptar "8" → llamar `handle_booking_month`; número → guardar `pending_data["date"]` y transicionar a `awaiting_slot_selection`.
- [x] T011 [P] Tests: `test_current_week_shows_available_days`, `test_current_week_skips_unavailable_days`, `test_current_week_option_8_triggers_month_flow`, `test_current_week_no_availability_jumps_to_month`.

**Checkpoint**: Tests T011 pasan. Usuario puede seleccionar día de la semana actual.

---

## Phase 3: Handler booking_month (P2)

**Objetivo**: Mostrar lista de meses con disponibilidad real.
**Checkpoint**: "8 → otro mes" → lista de hasta 3 meses futuros, solo con disponibilidad.

- [x] T012 Implementar `handle_booking_month(business_id, user_key, context) → str` en `booking_calendar_handler.py`: calcular próximos 3 meses, verificar disponibilidad por mes, renderizar solo meses con días disponibles. Guardar `pending_data["calendar_months"]`.
- [x] T013 Agregar case `booking_month` en `app/core/orchestrator.py`: número de mes → llamar `handle_booking_week` con índice de mes. "9" → `booking_current_week` (via state_stack).
- [x] T014 [P] Tests: `test_month_list_shows_only_available_months`, `test_month_selection_transitions_to_week`, `test_month_back_returns_to_current_week`.

**Checkpoint**: Tests T014 pasan.

---

## Phase 4: Handler booking_week (P2)

**Objetivo**: Mostrar semanas del mes seleccionado con disponibilidad.
**Checkpoint**: Mes seleccionado → lista de semanas, solo las que tienen días disponibles.

- [x] T015 Implementar `handle_booking_week(business_id, user_key, month_index, context) → str` en `booking_calendar_handler.py`: dividir mes en semanas ISO, verificar disponibilidad por semana, renderizar solo semanas con días. Guardar `pending_data["calendar_weeks"]`.
- [x] T016 Agregar case `booking_week` en `app/core/orchestrator.py`: número de semana → llamar `handle_booking_day` con índice de semana. "9" → `booking_month` (via state_stack).
- [x] T017 [P] Tests: `test_week_list_shows_only_available_weeks`, `test_week_selection_transitions_to_day`, `test_week_back_returns_to_month`.

**Checkpoint**: Tests T017 pasan.

---

## Phase 5: Handler booking_day (P1)

**Objetivo**: Mostrar días de la semana seleccionada y guardar fecha elegida.
**Checkpoint**: Semana seleccionada → días disponibles numerados. Selección de día → `pending_data["date"]` guardado → flujo de slots existente.

- [x] T018 Implementar `handle_booking_day(business_id, user_key, week_index, context) → str` en `booking_calendar_handler.py`: listar días de la semana seleccionada con disponibilidad real, renderizar lista. Al seleccionar día: guardar `pending_data["date"]` → transicionar a `awaiting_slot_selection` → llamar flujo de slots existente.
- [x] T019 Agregar case `booking_day` en `app/core/orchestrator.py`: número de día → guardar fecha → llamar `handle_book_appointment` con `pending_data["date"]` resuelto. "9" → `booking_week` (via state_stack).
- [x] T020 [P] Tests: `test_day_list_shows_only_available_days`, `test_day_selection_saves_date_and_continues_to_slots`, `test_day_back_returns_to_week`.

**Checkpoint**: Tests T020 pasan. Flujo completo calendario → slots → confirmación funciona.

---

## Phase 6: Integración y Validación Final

- [x] T021 Verificar que input inválido en cualquier estado del calendario incrementa el contador de intentos (spec 004) y al llegar a 3 redirige al menú.
- [x] T022 Verificar que "0" en cualquier estado del calendario va al menú principal.
- [x] T023 Verificar que "9" desde `booking_current_week` (primer estado) → `idle` + menú (stack vacío).
- [x] T024 Test flujo completo end-to-end: Agendar → semana actual → "8" → mes → semana → día → slots → confirmación → cita creada.
- [x] T025 Test: mes sin disponibilidad no aparece en la lista.
- [x] T026 Correr suite completa: `python -m pytest tests/ -v` — todos los tests pasan, sin regresiones.
- [x] T027 [P] Actualizar `spec.md` con diferencias de comportamiento implementadas.

---

## Dependencies & Execution Order

- Phase 1 (Foundation): sin dependencias — ejecutar primero.
- Phase 2–5: dependen de Phase 1. Pueden ejecutarse en el orden P1→P2→P3 por prioridad.
- Phase 2 y Phase 5 son P1 (el usuario puede seleccionar día de semana actual y confirmar sin necesitar meses/semanas).
- Phase 3 y Phase 4 son P2 — agregan la navegación de meses/semanas.
- Phase 6: depende de todas las fases anteriores.

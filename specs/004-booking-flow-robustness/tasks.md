# Tasks: Robustez del Flujo de Reserva

**Input**: `spec.md`, `plan.md`
**Prerequisites**: `specs/001-guided-menu-bot/`, `specs/003-owner-actions-phase-2/`

## Phase 1: Bugs Activos (Bloqueantes)

**Objetivo**: Corregir los 2 bugs que rompen el flujo de confirmación.
**Checkpoint**: `python -m pytest tests/ -v` — 148 tests pasan sin regresiones.

- [ ] T001 Corregir `resolve_date_from_spanish_text()` en `app/utils/date_parse.py`: cambiar `if t in ("hoy", "today")` por `if re.search(r'\bhoy\b', t)`. Aplicar mismo patrón para "mañana" y "pasado mañana".
- [ ] T002 Corregir bloque `not has_slot_or_time` en `app/handlers/booking_handler.py` (~línea 304): agregar `"service_id": service_for_query["id"]` al dict guardado en `pending_data` para `awaiting_slot_selection`.
- [ ] T003 [P] Agregar tests para bug 1: `test_date_parse_para_hoy`, `test_date_parse_hoy_con_hora`, `test_date_parse_manana_con_contexto`.
- [ ] T004 [P] Agregar test para bug 2: `test_booking_confirmation_service_id_persisted` — flujo completo sin hora → "sí" confirma correctamente.

**Checkpoint**: Bugs corregidos. Tests T003 y T004 pasan.

---

## Phase 2: Foundation del Contexto

**Objetivo**: Agregar campos base para state_stack e intentos.
**Checkpoint**: `_default_context()` incluye los nuevos campos.

- [ ] T005 Actualizar `_default_context()` en `app/services/conversation_manager.py`: agregar `"state_stack": []` y `"attempts": {}`.
- [ ] T006 Agregar `AWAITING_SESSION_RESUME = "awaiting_session_resume"` al enum `State` en `app/core/conversation_states.py`.

---

## Phase 3: Guardián Mejorado + Session Resume

**Objetivo**: Ampliar detección de abuso/dominio y preguntar si continuar cuando sesión expira con flujo activo.
**Checkpoint**: Input abusivo/fuera-de-dominio → menú + mensaje correcto. Sesión expirada con cita a medias → pregunta si continuar.

- [ ] T007 Ampliar lista `_is_abusive()` en `app/services/guided_menu_router.py` con términos locales dominicanos/caribeños relevantes.
- [ ] T008 Ampliar lista `_is_out_of_domain()` en `app/services/guided_menu_router.py` con más categorías fuera de contexto.
- [ ] T009 Mejorar mensaje de respuesta para `"abusive"` en `execute_guided_route()`: empático pero firme, incluir menú.
- [ ] T010 Mejorar mensaje de respuesta para `"out_of_domain"` en `execute_guided_route()`: explicar propósito del bot, incluir menú.
- [ ] T011 Modificar caso `"expired_flow"` en `execute_guided_route()`: si `pending_data` no vacío → preguntar "¿Continuamos donde estabas?" → guardar `state = "awaiting_session_resume"` con `pending_data` original en `context["resume_data"]`. Si `pending_data` vacío → comportamiento actual.
- [ ] T012 Manejar `awaiting_session_resume` en `app/core/orchestrator.py`: "sí" → restaurar `resume_data` como contexto; "no" → limpiar a `idle` + menú.
- [ ] T013 [P] Tests: `test_expired_flow_with_pending_asks_resume`, `test_session_resume_yes_restores_context`, `test_session_resume_no_clears_context`.

**Checkpoint**: Tests T013 pasan.

---

## Phase 4: State Stack (Navegación Back Real)

**Objetivo**: "9"/"volver" retorna al estado anterior con contexto intacto.
**Checkpoint**: Usuario en `awaiting_slot_selection` teclea "9" → vuelve a `awaiting_date`.

- [ ] T014 Agregar función `push_state(business_id, phone_number, state)` en `app/services/conversation_manager.py`: hace append al `state_stack`, máximo 10 elementos.
- [ ] T015 Actualizar `update_context()` en `app/services/conversation_manager.py`: cuando el dict de actualización contiene `"state"` diferente al actual, llamar a `push_state` con el estado anterior.
- [ ] T016 Reemplazar implementación `"go_back"` en `execute_guided_route()` (`app/services/guided_menu_router.py`): pop del `state_stack` → si stack no vacío restaurar estado previo; si vacío → `idle` + menú.
- [ ] T017 [P] Tests: `test_back_from_slot_selection_returns_awaiting_date`, `test_back_from_awaiting_date_returns_idle`, `test_back_stack_preserves_pending_data`.

**Checkpoint**: Tests T017 pasan.

---

## Phase 5: Contador de Intentos

**Objetivo**: Después de 3 inputs inválidos consecutivos en el mismo estado → menú principal.
**Checkpoint**: 3 "hola" en `awaiting_slot_selection` → menú principal con mensaje de ayuda.

- [ ] T018 Implementar lógica de intentos en `app/core/orchestrator.py`: cuando handler retorna sin avanzar estado (texto de "no entendí"), incrementar `context["attempts"][current_state]`. Si `>= 3` → limpiar + menú + mensaje.
- [ ] T019 Resetear `attempts[state]` al avanzar de estado exitosamente en `app/core/orchestrator.py`.
- [ ] T020 [P] Tests: `test_three_invalid_attempts_redirects_menu`, `test_attempt_counter_resets_on_state_advance`.

**Checkpoint**: Tests T020 pasan.

---

## Phase 6: Próximos Días Disponibles

**Objetivo**: Cuando el día no tiene slots → sugerir los próximos 3 días con disponibilidad.
**Checkpoint**: Usuario pide "lunes sin slots" → bot retorna 3 opciones numeradas de días cercanos.

- [ ] T021 Crear función `get_next_available_days(business_id, service_id, from_date, limit=3, max_days=14) → List[dict]` en `app/services/db_service.py`.
- [ ] T022 Modificar bloque "no hay slots" en `app/handlers/booking_handler.py`: llamar a `get_next_available_days` → si retorna días, mostrar opciones numeradas; si no → mensaje genérico actual.
- [ ] T023 Manejar selección de día sugerido en `handle_book_appointment`: si usuario elige número dentro del rango de días sugeridos → guardar fecha elegida → continuar flujo.
- [ ] T024 [P] Tests: `test_no_slots_shows_next_available_days`, `test_no_slots_no_alternatives_shows_generic_message`, `test_user_selects_suggested_day`.

**Checkpoint**: Tests T024 pasan.

---

## Phase 7: Paginación de Slots

**Objetivo**: Más de 8 slots → "8 → siguiente" aparece y navega páginas.
**Checkpoint**: 12 slots disponibles → página 1 muestra 8 + "8 → siguiente". Teclar 8 → página 2 con 4 slots.

- [ ] T025 Agregar `"slot_page": 0` al dict guardado en `pending_data` cuando se guardan `available_slots` en `app/handlers/booking_handler.py`.
- [ ] T026 Crear función `_paginate_slots(slots, page, page_size=8) → dict` en `app/handlers/booking_handler.py`.
- [ ] T027 Actualizar `_slots_short_list()` para mostrar indicador de paginación y navegación condicional (7/8).
- [ ] T028 Interceptar teclas "7" y "8" en `handle_slot_selection()` para navegación de página: decrementar/incrementar `slot_page` en `pending_data` → re-renderizar página sin avanzar estado.
- [ ] T029 [P] Aplicar mismo patrón de paginación en `app/handlers/modify_handler.py`.
- [ ] T030 [P] Tests: `test_slot_pagination_shows_next_button`, `test_slot_page_navigation_forward`, `test_slot_page_navigation_backward`, `test_slot_selection_correct_on_page_2`.

**Checkpoint**: Tests T030 pasan.

---

## Phase 8: REPEATABLE READ + Constraint Doble Booking

**Objetivo**: Dos confirmaciones simultáneas del mismo slot → solo una tiene éxito.
**Checkpoint**: Integridad garantizada. El segundo intento retorna error controlado + nuevos slots.

- [ ] T031 Agregar `UniqueConstraint("service_id", "date", name="uq_appointment_service_datetime")` en clase `Appointment` en `app/models.py`.
- [ ] T032 Generar migración Alembic para el nuevo constraint.
- [ ] T033 Actualizar `create_appointment()` en `app/services/db_service.py`: envolver en transacción `REPEATABLE READ`, capturar `IntegrityError`, retornar `{"error": "slot_conflict"}` en ese caso.
- [ ] T034 Actualizar `handle_booking_confirmation()` en `app/handlers/booking_handler.py`: verificar si `create_appointment` retorna `error == "slot_conflict"` → buscar slots frescos → mostrar alternativas.
- [ ] T035 [P] Test: `test_double_booking_conflict_handled_gracefully`.

**Checkpoint**: Tests T035 pasan.

---

## Phase 9: Validación Final

- [ ] T036 Correr suite completa: `python -m pytest tests/ -v` — todos los tests pasan, sin regresiones.
- [ ] T037 Verificar flujo completo en Telegram: "para hoy" → resuelve fecha → slots con service_id → "sí" → confirmación exitosa.
- [ ] T038 Verificar sesión expirada con cita a medias → pregunta resume → "sí" → continúa flujo.
- [ ] T039 [P] Actualizar `spec.md` con diferencias de comportamiento implementadas.

---

## Dependencies & Execution Order

- Phase 1 (Bugs): sin dependencias — ejecutar primero, desbloquea todo.
- Phase 2 (Foundation): sin dependencias — ejecutar en paralelo con Phase 1.
- Phase 3–8: dependen de Phase 2. Pueden ejecutarse en paralelo entre ellas.
- Phase 9: depende de todas las fases anteriores.

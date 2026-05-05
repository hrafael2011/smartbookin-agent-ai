# Tasks: Buffer de Servicio en Motor de Slots

**Input**: `spec.md`, `plan.md`
**Prerequisites**: `specs/001-guided-menu-bot/`

## Phase 1: Migración DB (Foundation — Bloqueante)

**Objetivo**: Agregar `buffer_minutes` al modelo y DB sin romper datos existentes.
**Checkpoint**: Migración ejecuta sin errores. Todos los servicios existentes tienen `buffer_minutes = 0`.

- [x] T001 Agregar `buffer_minutes = Column(Integer, nullable=False, default=0)` a la clase `Service` en `app/models.py`.
- [x] T002 Generar migración Alembic: `alembic revision --autogenerate -m "add_buffer_minutes_to_services"`. Verificar que el SQL generado es `ALTER TABLE services ADD COLUMN buffer_minutes INTEGER NOT NULL DEFAULT 0`.
- [ ] T003 Ejecutar migración en DB de desarrollo: `alembic upgrade head`. Verificar que no hay errores y servicios existentes tienen `buffer_minutes = 0`.
- [x] T004 [P] Test de migración: `test_service_model_has_buffer_minutes_field`, `test_buffer_minutes_default_is_zero`.

**Checkpoint**: Tests T004 pasan. Migración aplicada.

---

## Phase 2: Motor de Slots

**Objetivo**: `build_slots()` bloquea `duration + buffer`. Con `buffer = 0` el resultado es idéntico al actual.
**Checkpoint**: `buffer=0` → mismo resultado que hoy. `buffer=10` → slot de 30 min bloquea 40 min.

- [x] T005 Actualizar firma de `build_slots()` en `app/services/schedule_logic.py`: agregar parámetro `buffer_minutes: int = 0`.
- [x] T006 Actualizar lógica interna de `build_slots()`: separar `slot_block_delta = timedelta(duration + buffer)` para el bloqueo del rango vs `duration_delta` para el `end_datetime` del slot retornado. Usar `slot_block_delta` en la condición del while y en la detección de conflictos. Usar `duration_delta` para `end_datetime` en el dict del slot.
- [x] T007 [P] Tests del motor:
  - `test_build_slots_buffer_zero_same_as_before`: con `buffer=0` resultado idéntico al comportamiento actual.
  - `test_build_slots_buffer_blocks_extra_time`: con `duration=30, buffer=10`, slot de 9:00 bloquea hasta 9:40.
  - `test_build_slots_end_datetime_excludes_buffer`: `end_datetime` del slot es 9:30 (solo duración), no 9:40.
  - `test_build_slots_adjacent_slot_respects_buffer`: con buffer=10, no hay slot a las 9:30.

**Checkpoint**: Tests T007 pasan.

---

## Phase 3: Disponibilidad

**Objetivo**: `get_availability()` pasa `buffer_minutes` al motor y respeta el buffer de citas existentes.
**Checkpoint**: Cita existente a las 9:00 con buffer=10 bloquea hasta las 9:40 en la disponibilidad generada.

- [x] T008 Actualizar `get_availability()` en `app/services/db_service.py`: pasar `buffer_minutes=service.buffer_minutes` a `build_slots()`.
- [x] T009 Actualizar el `select` de citas existentes en `get_availability()` para incluir `Service.buffer_minutes` en el JOIN.
- [x] T010 Actualizar cálculo de `blocked_datetime_ranges` para citas existentes: `end_at = start_at + timedelta(minutes=int(duration_minutes) + int(buffer_minutes))`.
- [x] T011 Actualizar `get_business_services()` en `app/services/db_service.py`: incluir `"buffer_minutes": s.buffer_minutes` en el dict retornado.
- [x] T012 [P] Tests de disponibilidad:
  - `test_availability_existing_appointment_blocks_buffer`: cita a 9:00 con buffer=10 → no hay slot a 9:30.
  - `test_availability_buffer_zero_no_change`: buffer=0 → slots idénticos al comportamiento actual.
  - `test_get_business_services_includes_buffer_minutes`.

**Checkpoint**: Tests T012 pasan.

---

## Phase 4: API y Schema

**Objetivo**: El panel web puede leer y escribir `buffer_minutes` por servicio.
**Checkpoint**: PUT /services/{id} con `buffer_minutes=15` actualiza el campo. Validación rechaza valores inválidos.

- [x] T013 Agregar `buffer_minutes: int = 0` al schema de Service en `app/schemas/__init__.py`.
- [x] T014 Agregar `"buffer_minutes"` a `allowed_fields` en el endpoint de actualización de servicios en `app/api/services.py`.
- [x] T015 Agregar validación en el endpoint: `buffer_minutes >= 0`, `buffer_minutes <= 120`, `duration_minutes + buffer_minutes <= 480`.
- [x] T016 [P] Tests de API:
  - `test_update_service_buffer_minutes_valid`.
  - `test_update_service_buffer_minutes_negative_rejected`.
  - `test_update_service_buffer_minutes_exceeds_max_rejected`.
  - `test_update_service_duration_plus_buffer_exceeds_480_rejected`.

**Checkpoint**: Tests T016 pasan.

---

## Phase 5: Panel Web

**Objetivo**: El campo "Tiempo de preparación" es visible y editable en el formulario de servicios.
**Checkpoint**: Panel web muestra el campo. Guardar con buffer=10 → API actualiza. Listado muestra "30 min + 10 min buffer".

- [x] T017 Agregar campo `buffer_minutes` (input número, min=0, max=120) en el formulario de crear/editar servicio en el frontend. Label: "Tiempo de preparación (min)". Helper: "Tiempo de limpieza entre citas".
- [x] T018 Mostrar buffer en el listado de servicios cuando `buffer_minutes > 0`: "30 min + 10 min buffer".
- [x] T019 Verificar que el formulario envía `buffer_minutes` en el payload del PUT/POST.

---

## Phase 6: Validación Final

- [x] T020 Correr suite completa: `python -m pytest tests/ -v` — todos los tests pasan, sin regresiones.
- [x] T021 Verificar en Telegram: servicio con `buffer=10`, corte a las 9:00 → siguiente slot disponible a las 9:40 (no 9:30).
- [x] T022 Verificar en panel web: guardar servicio con buffer → campo persiste → disponibilidad en bot refleja el cambio.
- [x] T023 [P] Actualizar `spec.md` con diferencias de comportamiento implementadas.

---

## Dependencies & Execution Order

- Phase 1 (Migración): sin dependencias — ejecutar primero, bloquea todo lo demás.
- Phase 2 (Motor): depende de Phase 1. No depende de Phase 3 ni 4.
- Phase 3 (Disponibilidad): depende de Phase 1 y Phase 2.
- Phase 4 (API): depende de Phase 1. Puede ejecutarse en paralelo con Phase 2.
- Phase 5 (Frontend): depende de Phase 4.
- Phase 6: depende de todas las fases anteriores.

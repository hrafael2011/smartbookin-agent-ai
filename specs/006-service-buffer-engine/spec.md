# Feature Specification: Buffer de Servicio en Motor de Slots

**Feature Branch**: `006-service-buffer-engine`  
**Created**: 2026-05-05  
**Status**: Draft  
**Prerequisites**: `specs/004-booking-flow-robustness/`

## Scope

Agrega el campo `buffer_minutes` al modelo `Service`, actualiza el motor de generación de slots para que `slot_length = duration_minutes + buffer_minutes`, y expone el campo en el panel web para que el dueño lo configure por servicio.

## Problema Actual

El modelo `Service` solo tiene `duration_minutes`. En `build_slots()` (schedule_logic.py), el slot termina exactamente al finalizar el servicio:

```python
duration_delta = timedelta(minutes=duration_minutes)
end_cursor = cursor + duration_delta  # sin buffer
```

Esto significa que si un corte dura 30 minutos, el siguiente cliente puede ser agendado a los 30 minutos exactos — el barbero no tiene tiempo de limpieza ni descanso entre citas.

**Ejemplo actual (sin buffer):**
```
9:00 AM → Corte (30 min) → termina 9:30 AM
9:30 AM → siguiente cliente disponible ← sin margen
```

**Ejemplo correcto (con buffer de 10 min):**
```
9:00 AM → Corte (30 min + 10 min buffer) → bloquea hasta 9:40 AM
9:40 AM → siguiente cliente disponible ✓
```

## Cambio en el Modelo

### Nuevo campo en `Service`

```python
buffer_minutes = Column(Integer, nullable=False, default=0)
```

- Valor por defecto: `0` (sin buffer) — retrocompatible, no rompe negocios existentes.
- Rango válido: `0` a `120` minutos.
- Configurable por servicio individualmente.

### Migración Alembic

Nueva migración: `ALTER TABLE services ADD COLUMN buffer_minutes INTEGER NOT NULL DEFAULT 0`.

## Cambio en el Motor de Slots

### `build_slots()` en `schedule_logic.py`

Nueva firma:

```python
def build_slots(
    open_ranges,
    blocked_ranges,
    duration_minutes: int,
    buffer_minutes: int = 0,      # nuevo parámetro
    preferred_time=None,
    step_minutes=TIME_STEP_MINUTES,
)
```

Lógica actualizada:

```python
slot_length = duration_minutes + buffer_minutes   # tiempo total bloqueado
slot_delta = timedelta(minutes=slot_length)        # bloqueo real

# El slot que se muestra al usuario refleja solo duration_minutes
# El bloqueo en disponibilidad usa slot_length
end_cursor = cursor + slot_delta                   # bloquea buffer también
```

**Importante**: `end_datetime` del slot (guardado en DB) usa `duration_minutes` solamente — el appointment en DB refleja la duración real del servicio, no el buffer. El buffer solo afecta la disponibilidad generada.

### `get_availability()` en `db_service.py`

Actualizar para leer `service.buffer_minutes` y pasarlo a `build_slots()`:

```python
slots = build_slots(
    open_ranges=open_datetime_ranges,
    blocked_ranges=blocked_datetime_ranges,
    duration_minutes=service.duration_minutes,
    buffer_minutes=service.buffer_minutes,    # nuevo
    preferred_time=preferred_time,
)
```

### Cálculo de blocked_ranges de citas existentes

Actualmente los appointments bloquean `duration_minutes`. Con buffer, deben bloquear `duration_minutes + buffer_minutes` para que el buffer de citas existentes también sea respetado:

```python
# Antes:
end_at = start_at + timedelta(minutes=int(duration_minutes))

# Después:
end_at = start_at + timedelta(minutes=int(duration_minutes) + int(buffer_minutes))
```

Requiere que el JOIN en `get_availability` también traiga `Service.buffer_minutes`.

## Cambio en el Panel Web

### Formulario de Servicio (`frontend/`)

Agregar campo `buffer_minutes` en el formulario de crear/editar servicio:

- Label: "Tiempo de preparación (min)"
- Input: número entero, mínimo 0, máximo 120
- Placeholder: "0"
- Helper text: "Tiempo de limpieza o descanso entre citas"

### API de Servicios (`app/api/services.py`)

Agregar `buffer_minutes` a `allowed_fields` en el endpoint de actualización:

```python
allowed_fields = {"name", "description", "duration_minutes", "price", "is_active", "buffer_minutes"}
```

### Schema (`app/schemas/__init__.py`)

Agregar campo al schema de Service:

```python
buffer_minutes: int = 0
```

## Non-Negotiable Rules

- `buffer_minutes = 0` por defecto — no afecta negocios existentes sin configurar.
- El `end_datetime` guardado en la cita refleja `duration_minutes` (no incluye buffer) — el buffer es tiempo del negocio, no del cliente.
- El buffer de appointments existentes debe considerarse al generar nuevos slots.
- Validación: `buffer_minutes >= 0` y `duration_minutes + buffer_minutes <= 480` (máximo 8h).
- La migración debe ser retrocompatible — todos los servicios existentes quedan con `buffer_minutes = 0`.

## Acceptance Tests

- Servicio con `duration=30, buffer=0` → slots cada `TIME_STEP_MINUTES` (comportamiento actual sin cambio).
- Servicio con `duration=30, buffer=10` → cita a 9:00 AM bloquea hasta 9:40 AM → siguiente slot disponible a 9:40 AM.
- Cita existente con `duration=30, buffer=10` → bloquea 40 minutos al calcular disponibilidad.
- Panel web muestra campo "Tiempo de preparación" editable en formulario de servicio.
- `buffer_minutes = 120` con `duration = 360` → rechazado por validación (supera 480 min).
- Migración ejecuta sin errores en DB con servicios existentes → `buffer_minutes = 0` en todos.
- `get_business_services()` retorna `buffer_minutes` en el dict de cada servicio.

## Implementation Notes (v1 — 2026-05-05)

- Added `Service.buffer_minutes` and Alembic migration `b2c3d4e5f6a7_add_buffer_minutes_to_services.py`.
- `build_slots()` now uses `duration_minutes + buffer_minutes` for availability blocking while keeping slot `end_datetime` equal to service duration only.
- `get_availability()` passes the service buffer into the slot engine and existing appointments block their service duration plus buffer.
- Service API schemas and validation now accept `buffer_minutes` from 0 to 120 and enforce `duration_minutes + buffer_minutes <= 480`.
- Frontend service create/edit sends `buffer_minutes`, renders the field as "Tiempo de preparación (min)", and shows buffer in service listings.
- Verification: `./scripts/verify-mvp.sh backend-all` passed with 202 tests; `./scripts/verify-mvp.sh frontend` passed.
- Local `alembic upgrade head` was attempted but did not return because the development DB connection was unavailable in this session; Alembic chain validation shows one head: `b2c3d4e5f6a7`.

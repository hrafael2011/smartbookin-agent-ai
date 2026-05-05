# Plan Técnico: Buffer de Servicio en Motor de Slots

## Resumen

Agrega `buffer_minutes` al modelo `Service` con migración Alembic retrocompatible, actualiza `build_slots()` para que el tiempo bloqueado sea `duration + buffer`, actualiza `get_availability()` para pasar el buffer al motor, y expone el campo en el panel web y la API.

## Archivos Modificados

### Phase 1 — Migración DB

**Nueva migración Alembic** (`backend/api-backend/alembic/versions/`)
```sql
ALTER TABLE services ADD COLUMN buffer_minutes INTEGER NOT NULL DEFAULT 0;
```
- Retrocompatible: todos los servicios existentes quedan con `buffer_minutes = 0`.
- Constraint: `CHECK (buffer_minutes >= 0)`.

**`app/models.py`**
```python
# En clase Service:
buffer_minutes = Column(Integer, nullable=False, default=0)
```

### Phase 2 — Motor de Slots

**`app/services/schedule_logic.py`**

Actualizar `build_slots()`:

```python
def build_slots(
    open_ranges,
    blocked_ranges,
    duration_minutes: int,
    buffer_minutes: int = 0,       # nuevo — default 0 para retrocompat
    preferred_time=None,
    step_minutes=TIME_STEP_MINUTES,
):
    slot_block_minutes = duration_minutes + buffer_minutes  # tiempo total bloqueado
    slot_block_delta = timedelta(minutes=slot_block_minutes)
    duration_delta = timedelta(minutes=duration_minutes)    # solo para end_datetime del slot

    while cursor + slot_block_delta <= range_end:
        end_cursor_display = cursor + duration_delta        # end_datetime para DB
        end_cursor_block = cursor + slot_block_delta        # bloqueo real de disponibilidad

        is_conflicting = any(
            datetime_ranges_overlap(cursor, end_cursor_block, bs, be)  # usa bloqueo completo
            for bs, be in blocked_ranges
        )
        if not is_conflicting:
            slots.append({
                "start_time": ...,
                "start_datetime": cursor.isoformat(),
                "end_datetime": end_cursor_display.isoformat(),  # sin buffer en DB
                "is_preferred": ...,
            })
        cursor += step_delta
```

**Importante**: `end_datetime` guardado en el slot (y luego en `Appointment.end_at` si aplica) no incluye el buffer — el buffer es tiempo operativo del negocio, no del cliente.

### Phase 3 — Disponibilidad

**`app/services/db_service.py`**

En `get_availability()`:

1. Actualizar JOIN para traer `Service.buffer_minutes`:
```python
select(Service).filter(Service.id == service_id)
# ya trae buffer_minutes desde el modelo actualizado
```

2. Actualizar cálculo de `blocked_datetime_ranges` para citas existentes:
```python
for appointment, duration_minutes, buffer_minutes in result.all():
    start_at = _as_utc(appointment.date)
    # Bloquear duration + buffer de citas ya agendadas
    end_at = start_at + timedelta(minutes=int(duration_minutes) + int(buffer_minutes))
    blocked_datetime_ranges.append((start_at, end_at))
```
Requiere actualizar el `select` para incluir `Service.buffer_minutes`.

3. Pasar `buffer_minutes` a `build_slots()`:
```python
slots = build_slots(
    open_ranges=open_datetime_ranges,
    blocked_ranges=blocked_datetime_ranges,
    duration_minutes=service.duration_minutes,
    buffer_minutes=service.buffer_minutes,    # nuevo
    preferred_time=preferred_time,
)
```

4. `get_business_services()`: incluir `buffer_minutes` en el dict retornado:
```python
return [{"id": s.id, "name": s.name, "price": s.price,
         "duration_minutes": s.duration_minutes,
         "buffer_minutes": s.buffer_minutes}  # nuevo
        for s in services]
```

### Phase 4 — API y Schema

**`app/schemas/__init__.py`**
```python
class ServiceSchema:
    buffer_minutes: int = 0
```

**`app/api/services.py`**
```python
allowed_fields = {
    "name", "description", "duration_minutes",
    "price", "is_active", "buffer_minutes"   # nuevo
}
```

Validación en el endpoint:
```python
if "buffer_minutes" in data:
    b = data["buffer_minutes"]
    if not isinstance(b, int) or b < 0 or b > 120:
        raise HTTPException(400, "buffer_minutes debe ser entre 0 y 120")
    d = data.get("duration_minutes") or service.duration_minutes
    if d + b > 480:
        raise HTTPException(400, "duration + buffer no puede superar 480 minutos")
```

### Phase 5 — Panel Web

**`frontend/src/`** (componente de servicios)

Agregar campo en formulario crear/editar servicio:
- Label: "Tiempo de preparación (min)"
- Input tipo número, min=0, max=120, default=0
- Helper text: "Tiempo de limpieza o descanso entre citas. Ej: 10 para 10 minutos de margen."
- Mostrar en listado de servicios junto a duración: "30 min + 10 min buffer"

## Compatibilidad con Spec 005

`get_available_days_in_range()` (spec 005) llama a `get_availability()` internamente — heredará automáticamente el soporte de buffer sin cambios adicionales.

## Reglas No-Negociables

- Migración con `DEFAULT 0` — no rompe servicios existentes.
- `end_datetime` en el slot no incluye buffer (tiempo del cliente vs tiempo del negocio).
- `blocked_ranges` de citas existentes SÍ incluyen buffer (para respetar el margen de citas ya agendadas).
- Validación `buffer_minutes <= 120` en backend, no solo en frontend.
- Tests deben verificar que `buffer_minutes = 0` produce exactamente el mismo resultado que el comportamiento actual.

## Perfil de Verificación

```bash
cd backend/api-backend && python -m pytest tests/ -v -k "buffer or slot or availability"
```

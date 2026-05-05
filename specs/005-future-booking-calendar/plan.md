# Plan Técnico: Flujo de Agenda Futura (Calendario por Menú)

## Resumen

Implementa 4 nuevos estados en la state machine del cliente (`booking_current_week`, `booking_month`, `booking_week`, `booking_day`) con handlers puramente deterministas. La entrada al flujo de fecha ahora muestra días disponibles de la semana actual con opción "8 → Buscar en otro mes". Cada pantalla requiere query de disponibilidad en tiempo real. Al seleccionar día, el flujo continúa en el pipeline existente de slots y confirmación sin modificaciones.

## Integración con Flujo Existente

```
awaiting_service → booking_current_week (NUEVO, reemplaza awaiting_date)
  → opción día → pending_data["date"] → awaiting_slot_selection (EXISTENTE)
  → opción 8   → booking_month (NUEVO)
                  → booking_week (NUEVO)
                    → booking_day (NUEVO)
                      → pending_data["date"] → awaiting_slot_selection (EXISTENTE)
```

`awaiting_date` se mantiene como estado de entrada desde texto libre (NLU path). El nuevo flujo de calendario usa `booking_current_week` como estado inicial cuando se inicia desde el menú guiado.

## Archivos Modificados

### Foundation

**`app/core/conversation_states.py`**
- Agregar al enum `State`:
  - `BOOKING_CURRENT_WEEK = "booking_current_week"`
  - `BOOKING_MONTH = "booking_month"`
  - `BOOKING_WEEK = "booking_week"`
  - `BOOKING_DAY = "booking_day"`
- Agregar los 4 nuevos estados a `BOOKING_FLOW_STATES`.

**`app/services/db_service.py`**
- Nueva función `get_available_days_in_range(business_id, service_id, start_date, end_date) → List[dict]`: para cada día en el rango, llama a `get_availability` y retorna solo los que tienen slots. Resultado: `[{"date": "2026-06-08", "slot_count": 5, "label": "lunes 8"}, ...]`.

### Handler Principal

**`app/handlers/booking_calendar_handler.py`** (nuevo archivo)

Contiene los 4 handlers del flujo de calendario:

#### `handle_booking_current_week(service_id, context) → str`
- Calcula días restantes de la semana actual (desde hoy hasta domingo).
- Llama a `get_available_days_in_range` para esos días.
- Si hay días disponibles: renderiza lista numerada + "8 → Buscar en otro mes".
- Si no hay días disponibles esta semana: saltar directamente a `handle_booking_month`.
- Guarda `state = "booking_current_week"` en contexto.

#### `handle_booking_month(context) → str`
- Calcula próximos 3 meses (mes actual + 1 hasta mes actual + 3).
- Para cada mes: verifica si tiene al menos 1 día con slots usando `get_available_days_in_range`.
- Renderiza lista numerada de meses disponibles.
- Guarda `state = "booking_month"` y `pending_data["calendar_months"]` con la lista.

#### `handle_booking_week(month_index, context) → str`
- Recibe selección de mes (número).
- Divide el mes en semanas (lunes a domingo).
- Para cada semana: verifica disponibilidad con `get_available_days_in_range`.
- Renderiza solo semanas con días disponibles.
- Guarda `state = "booking_week"` y `pending_data["calendar_weeks"]` con las semanas.

#### `handle_booking_day(week_index, context) → str`
- Recibe selección de semana (número).
- Lista los días de la semana seleccionada con disponibilidad.
- Renderiza días disponibles numerados.
- Al seleccionar día: guarda `pending_data["date"]` → `state = "awaiting_slot_selection"`.
- Llama al flujo de slots existente.

### Routing

**`app/services/guided_menu_router.py`**
- En `_start_booking()`: cambiar `state = "awaiting_service"` → después de seleccionar servicio, transicionar a `booking_current_week` en lugar de `awaiting_date`.
- Agregar `"booking_current_week"`, `"booking_month"`, `"booking_week"`, `"booking_day"` a la condición `_is_active_context`.

**`app/core/orchestrator.py`**
- En el bloque de despacho por `current_intent == "book_appointment"`: agregar cases para los 4 nuevos estados → llamar al handler correspondiente de `booking_calendar_handler.py`.
- Interceptar tecla "8" en `booking_current_week` → `handle_booking_month`.

### Formato de Mensajes

**`app/utils/date_parse.py`**
- Nueva función `format_week_label(start_date, end_date) → str`: retorna "Semana del 1 al 7" o "Semana del 8 al 14".
- Nueva función `format_month_label(year, month) → str`: retorna "Junio 2026".

## Estructura de pending_data para el Flujo de Calendario

```json
{
  "service": "Corte",
  "service_id": 1,
  "calendar_months": [
    {"index": 1, "year": 2026, "month": 6, "label": "Junio 2026"},
    {"index": 2, "year": 2026, "month": 7, "label": "Julio 2026"}
  ],
  "calendar_weeks": [
    {"index": 1, "start": "2026-06-01", "end": "2026-06-07", "label": "Semana del 1 al 7", "day_count": 3},
    {"index": 2, "start": "2026-06-08", "end": "2026-06-14", "label": "Semana del 8 al 14", "day_count": 4}
  ],
  "calendar_days": [
    {"index": 1, "date": "2026-06-08", "label": "lunes 8"},
    {"index": 2, "date": "2026-06-09", "label": "martes 9"}
  ]
}
```

## Reglas No-Negociables

- Los nuevos handlers no llaman al NLU/LLM — son 100% deterministas.
- `state_stack` (spec 004) debe estar implementado antes de esta spec para que "9 → Volver" funcione correctamente en el calendario.
- Si `get_available_days_in_range` retorna lista vacía para todos los meses → mensaje "No hay disponibilidad en los próximos 3 meses" + menú.
- No cachear resultados de disponibilidad — cada renderizado hace query fresca.
- La semana se define como lunes a domingo (ISO week).

## Perfil de Verificación

```bash
cd backend/api-backend && python -m pytest tests/ -v -k "calendar or booking_month or booking_week or booking_day"
```

# Feature Specification: Flujo de Agenda Futura (Calendario por Menú)

**Feature Branch**: `005-future-booking-calendar`  
**Created**: 2026-05-05  
**Status**: Draft  
**Prerequisites**: `specs/004-booking-flow-robustness/`

## Scope

Implementa la navegación de fechas futuras completamente guiada por menú numerado: semana actual → opción 8 "Buscar en otro mes" → selección de mes → selección de semana → selección de día → flujo de hora existente. Solo se muestran meses, semanas, días y horas con disponibilidad real. No requiere texto libre para fechas en este flujo.

## Problema Actual

El sistema solo resuelve fechas si el usuario escribe texto exacto ("el viernes", "10 de junio"). Para fechas futuras más allá de la semana en curso, el usuario debe adivinar el formato correcto y no recibe guía del bot.

```
Usuario: "quiero agendar para el próximo mes"
→ resolve_date_from_spanish_text("para el próximo mes") → None
→ Bot: "¿Para cuándo querés la cita?" ← loop, no resuelve
```

## Nuevos Estados

| Estado | Descripción |
|--------|-------------|
| `booking_current_week` | Mostrando días restantes de la semana actual con disponibilidad |
| `booking_month` | Mostrando lista de meses disponibles para seleccionar |
| `booking_week` | Mostrando semanas del mes seleccionado con disponibilidad |
| `booking_day` | Mostrando días de la semana seleccionada con disponibilidad |

Estos estados se agregan a `BOOKING_FLOW_STATES` en `conversation_states.py`.

## Flujo Completo

### Entrada al flujo de fecha

Cuando el flujo requiere seleccionar fecha (estado `awaiting_date`), en lugar de pedir texto libre mostrar la semana actual:

```
¿Para qué día querés tu cita?

Esta semana:
  1. Lunes 6
  2. Martes 7
  3. Jueves 9
  4. Viernes 10

  8 → Buscar en otro mes
  9 → Volver
  0 → Menú principal
```

Solo aparecen días con disponibilidad real. Si la semana actual no tiene días disponibles, saltar directamente al flujo de mes.

### Estado: booking_month

```
¿En qué mes querés agendar?

  1. Junio 2026
  2. Julio 2026
  3. Agosto 2026

  9 → Volver
  0 → Menú principal
```

Máximo 3 meses futuros (configurable). No incluye el mes actual si ya está en la vista de semana actual. Solo meses con al menos un día disponible.

### Estado: booking_week

```
¿Qué semana de junio?

  1. Semana del 1 al 7   (4 días disponibles)
  2. Semana del 8 al 14  (3 días disponibles)
  3. Semana del 22 al 28 (2 días disponibles)

  9 → Volver
  0 → Menú principal
```

Solo semanas con al menos un día disponible. Semana sin disponibilidad no aparece.

### Estado: booking_day

```
¿Qué día de esa semana?

  1. Lunes 8
  2. Martes 9
  3. Viernes 12

  9 → Volver
  0 → Menú principal
```

Solo días con slots reales. Al seleccionar día → `date` se guarda en `pending_data` → continúa al flujo de hora existente (`awaiting_slot_selection`).

## Integración con Flujo Existente

El nuevo flujo de calendario es la entrada al paso de fecha. Una vez que el usuario selecciona un día, el sistema tiene `date` en `pending_data` y el flujo continúa exactamente igual que hoy:

```
booking_current_week / booking_day
  → pending_data["date"] = "2026-06-08"
  → flujo existente: slot selection → confirmación
```

No se modifican `handle_slot_selection` ni `handle_booking_confirmation`.

## Disponibilidad Real — Reglas Estrictas

- **Nunca** mostrar mes sin días disponibles.
- **Nunca** mostrar semana sin días disponibles.
- **Nunca** mostrar día sin slots reales.
- **Nunca** mostrar hora ocupada o bloqueada.
- Cada pantalla requiere query de disponibilidad en tiempo real antes de renderizar.
- No usar cache para decidir qué mostrar (validación en tiempo real obligatoria).

## Consultas de Disponibilidad Necesarias

| Pantalla | Query requerida |
|----------|----------------|
| Semana actual | `get_available_days_in_range(start, end, service_id)` |
| Lista de meses | Por cada mes: verificar si tiene al menos 1 día con slots |
| Lista de semanas | Por cada semana del mes: verificar días con slots |
| Lista de días | Por cada día de la semana: `get_availability(date, service_id)` |

Nueva función en `db_service.py`: `get_available_days_in_range(business_id, service_id, start_date, end_date) → List[date]`

## Guardián Dentro del Flujo

Dentro de los estados del calendario, el usuario solo puede responder con:
- Número de opción de la lista
- "9" (volver), "0" (menú), "X" (salir)

Cualquier otro input → incrementar contador de intentos (spec 004) → repetir opciones.

## Non-Negotiable Rules

- El flujo de calendario no reemplaza el text parser — si el usuario ya está en un estado con `date` resuelto, no volver al calendario.
- La opción "8 → Buscar en otro mes" solo aparece en `booking_current_week`, no en otros estados.
- El `state_stack` (spec 004) funciona correctamente aquí: "9" en `booking_day` → `booking_week` → `booking_month` → `booking_current_week`.
- Los 3 estados nuevos no interactúan con el NLU/LLM — son 100% deterministas.
- Máximo 3 meses futuros en MVP (hardcoded, configurable en spec posterior).

## Acceptance Tests

- Usuario en `awaiting_date` → ve semana actual con días disponibles numerados.
- Día sin disponibilidad en semana actual → no aparece en la lista.
- Usuario teclea "8" en semana actual → ve lista de meses.
- Mes sin disponibilidad → no aparece en la lista de meses.
- Usuario selecciona mes → ve semanas, solo las que tienen días.
- Semana sin disponibilidad → no aparece.
- Usuario selecciona semana → ve días, solo los que tienen slots.
- Usuario selecciona día → `pending_data["date"]` se guarda → continúa al flujo de hora.
- "9" en `booking_day` → vuelve a `booking_week` con el mes previo en contexto.
- "9" en `booking_week` → vuelve a `booking_month`.
- "9" en `booking_month` → vuelve a `booking_current_week`.
- Input inválido ("hola") en `booking_month` → repite opciones, incrementa contador.

## Implementation Notes (v1 — 2026-05-05)

- Implemented deterministic calendar handlers in `app/handlers/booking_calendar_handler.py`.
- Added `booking_current_week`, `booking_month`, `booking_week`, and `booking_day` to the customer booking state machine.
- Guided service selection now enters the current-week calendar before falling back to month/week/day navigation.
- Calendar states bypass NLU and are covered by `tests/test_booking_calendar_flow.py`.
- Verification: `./scripts/verify-mvp.sh backend-all` passed with 202 tests; `./scripts/verify-mvp.sh frontend` passed.

# Plan Técnico: Robustez del Flujo de Reserva

## Resumen

Corrige dos bugs bloqueantes en el flujo de confirmación, amplía la capa guardián, e implementa mejoras de UX y correctness: navegación back con `state_stack`, sesión resume, contador de intentos, sugerencia de días disponibles, paginación de slots y constraint de doble booking.

## Orden de Ejecución

Los bugs (Phase 1) desbloquean el flujo de confirmación — deben completarse antes de cualquier otra mejora. El resto puede ejecutarse en paralelo por módulo.

## Archivos Modificados

### Phase 1 — Bugs

**`app/utils/date_parse.py`**
- `resolve_date_from_spanish_text()`: cambiar `if t in ("hoy", "today")` por `if re.search(r'\bhoy\b', t)`. Mismo patrón para "mañana" y "pasado mañana".

**`backend/api-backend/app/handlers/booking_handler.py`**
- Bloque `not has_slot_or_time` (~línea 304): agregar `"service_id": service_for_query["id"]` al dict guardado en `pending_data` para `awaiting_slot_selection`.

### Phase 2 — Contexto y Foundation

**`app/services/conversation_manager.py`**
- `_default_context()`: agregar `"state_stack": []` y `"attempts": {}` al dict de contexto por defecto.

### Phase 3 — Guardián

**`app/services/guided_menu_router.py`**
- `_is_abusive()`: ampliar lista con términos locales dominicanos/caribeños.
- `_is_out_of_domain()`: ampliar lista con más categorías fuera de contexto.
- `execute_guided_route()` caso `"abusive"`: mejorar mensaje de respuesta, empático pero firme.
- `execute_guided_route()` caso `"out_of_domain"`: mensaje más claro sobre el propósito del bot.
- `execute_guided_route()` caso `"expired_flow"`: si `pending_data` no vacío, preguntar si continuar en lugar de limpiar directamente. Nuevo estado intermedio `"awaiting_session_resume"`.

### Phase 4 — State Stack

**`app/services/guided_menu_router.py`**
- `execute_guided_route()` caso `"go_back"`: implementar lógica real de pop del `state_stack`. Si stack vacío → `idle` + menú. Si stack no vacío → restaurar estado previo con `pending_data` intacto.

**`app/services/conversation_manager.py`**
- Nueva función `push_state(business_id, phone_number, current_state)`: agrega estado actual al `state_stack`.
- Llamar a `push_state` en `update_context` cuando cambia el campo `state`.

**`app/core/conversation_states.py`**
- Agregar `AWAITING_SESSION_RESUME = "awaiting_session_resume"` al enum `State`.

### Phase 5 — Contador de Intentos

**`app/core/orchestrator.py`**
- Después de que un handler retorna sin avanzar de estado (respuesta de "no entendí"), incrementar `context["attempts"][current_state]`.
- Si `attempts[current_state] >= 3`: limpiar contexto → menú principal + mensaje de ayuda.
- Al avanzar de estado: resetear `attempts[current_state] = 0`.

### Phase 6 — Próximos Días Disponibles

**`app/services/db_service.py`**
- Nueva función `get_next_available_days(business_id, service_id, from_date, limit=3, max_days=14) → List[dict]`: itera desde `from_date + 1` hasta `from_date + max_days`, retorna los primeros `limit` días con slots, incluyendo conteo de slots disponibles.

**`app/handlers/booking_handler.py`**
- En el bloque de "no hay slots para esa fecha": llamar a `get_next_available_days` y formatear respuesta con opciones numeradas. Si no hay días disponibles en 14 días → mensaje genérico actual.

### Phase 7 — Paginación de Slots

**`app/handlers/booking_handler.py`**
- Agregar `"slot_page": 0` a `pending_data` cuando se guardan `available_slots`.
- Nueva función `_paginate_slots(slots, page, page_size=8) → dict`: retorna `{items, page, total_pages, has_prev, has_next}`.
- En `handle_slot_selection`: interceptar "7" y "8" antes del NLU → decrementar/incrementar `pending_data["slot_page"]` → re-renderizar página.
- `_slots_short_list()`: actualizar para mostrar navegación de página cuando aplica.

**`app/handlers/modify_handler.py`**
- Aplicar el mismo patrón de paginación en `_slots_modify_list()`.

### Phase 8 — REPEATABLE READ + Constraint

**`app/models.py`**
- `Appointment.__table_args__`: agregar `UniqueConstraint("service_id", "date", name="uq_appointment_service_datetime")`.

**`app/services/db_service.py`**
- `create_appointment()`: envolver en transacción con `execution_options(isolation_level="REPEATABLE READ")`.
- Capturar `sqlalchemy.exc.IntegrityError`: retornar dict `{"error": "slot_conflict", "message": "Ese horario acaba de ser tomado"}`.

**`app/handlers/booking_handler.py`**
- `handle_booking_confirmation()`: verificar si `create_appointment` retorna error de conflicto → mostrar nuevos slots disponibles.

**Alembic**
- Nueva migración para el constraint.

## Nuevos Estados de Conversación

| Estado | Descripción |
|--------|-------------|
| `awaiting_session_resume` | Esperando respuesta sí/no para continuar sesión expirada |

## Reglas No-Negociables

- Los bugs de Phase 1 se completan antes de todo lo demás.
- `state_stack` máximo 10 elementos — prevenir crecimiento infinito con `state_stack = state_stack[-10:]`.
- El contador de intentos NO se incrementa en estados de confirmación sí/no (solo en estados donde el usuario debe dar información nueva).
- La búsqueda de próximos días usa el mismo `service_id` que está en `pending_data`.
- El constraint de DB es la barrera final — no reemplaza la re-validación previa, la complementa.

## Perfil de Verificación

```bash
cd backend/api-backend && python -m pytest tests/ -v
```

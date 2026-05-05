# Feature Specification: Robustez del Flujo de Reserva

**Feature Branch**: `004-booking-flow-robustness`  
**Created**: 2026-05-05  
**Status**: Draft  
**Prerequisites**: `specs/001-guided-menu-bot/`, `specs/003-owner-actions-phase-2/`

## Scope

Corrige dos bugs activos que rompen el flujo de confirmación, refuerza la capa guardián del bot, implementa navegación back real con `state_stack`, manejo de sesión expirada con opción de continuar, contador de intentos inválidos, sugerencia de próximos días disponibles, paginación de slots y prevención de doble booking con constraint en DB.

## Bugs Activos (Bloqueantes)

### Bug 1 — `date_parse.py`: "para hoy" no resuelve fecha

`resolve_date_from_spanish_text("para hoy")` retorna `None` porque la condición es `t in ("hoy", "today")` — coincidencia exacta. Frases como "para hoy", "hoy a las 3", "reservar hoy" no se reconocen.

**Fix**: reemplazar `if t in ("hoy", "today")` por `if re.search(r'\bhoy\b', t)`. Aplicar el mismo patrón para "mañana" y "pasado mañana".

### Bug 2 — `booking_handler.py`: `service_id` no se persiste en `awaiting_slot_selection`

En el bloque `not has_slot_or_time` (línea ~304), el contexto guardado es `{**pending_data, "available_slots": slots[:8]}` — sin `service_id`. Cuando el usuario confirma, `handle_booking_confirmation` lee `pending_data.get("service_id") → None` y retorna "No pude validar el servicio."

**Fix**: agregar `"service_id": service_for_query["id"]` al dict guardado en ese bloque.

## Mejoras Funcionales

### Guardián — Capa de detección mejorada

Las listas `_is_abusive()` y `_is_out_of_domain()` en `guided_menu_router.py` son insuficientes para el contexto dominicano/latinoamericano. Ampliar con términos locales y mejorar la respuesta para fuera-de-dominio con mensaje empático.

### State Stack — Navegación "9 → Volver" real

Actualmente "9"/"volver" limpia el contexto a `idle` (comentario en código: "Phase 1 fallback"). Implementar `state_stack: []` en el contexto de conversación para push/pop de estados.

**Comportamiento**:
- Al avanzar de estado → push del estado anterior al stack
- Usuario teclea "9" → pop del stack → retorna al estado anterior con pending_data intacto
- Stack vacío + "9" → ir a `idle` + menú principal

### Session Resume — Sesión expirada con opción de continuar

Actualmente `expired_flow` limpia el contexto silenciosamente. Si había un flujo activo al expirar, preguntar al usuario si desea continuar.

**Comportamiento**:
- Flujo expirado + pending_data no vacío → "Tenías una cita a medias para [servicio]. ¿Continuamos donde estabas? (sí / no)"
- "sí" → restaurar contexto previo
- "no" → limpiar a idle + menú principal
- Flujo expirado + pending_data vacío → comportamiento actual (limpiar + menú)

### Contador de Intentos — 3 intentos inválidos → menú principal

Agregar campo `attempts: {}` al contexto. Por cada estado, contar inputs que no producen avance. Después de 3 intentos consecutivos inválidos en el mismo estado → limpiar contexto + mostrar menú con mensaje de ayuda.

### Próximos Días Disponibles — Sugerencia cuando no hay slots

Cuando un día solicitado no tiene slots, en lugar de solo mostrar error, buscar los próximos 3 días con disponibilidad real y ofrecerlos como opciones numeradas.

**Comportamiento**:
```
Usuario: "el lunes"
→ 0 slots disponibles el lunes
→ Bot: "El lunes no tenemos disponibilidad.
        Próximas fechas con horarios:
        1. Martes 12 (3 horarios)
        2. Jueves 14 (5 horarios)
        3. Viernes 15 (2 horarios)
        ¿Cuál te viene bien?"
```

### Paginación de Slots — 7 → anterior / 8 → siguiente

Cuando hay más de 8 slots disponibles, habilitar navegación por páginas. Las teclas 7 y 8 están reservadas globalmente para esta función dentro de estados de selección de slot.

**Reglas**:
- No mostrar página vacía
- Solo mostrar "7 → anterior" si existe página anterior
- Solo mostrar "8 → siguiente" si existe página siguiente
- Selección de slot por número relativo a la página actual

### REPEATABLE READ + Constraint — Prevención de doble booking

`create_appointment` no usa isolation level. Dos usuarios pueden confirmar el mismo slot simultáneamente y ambos pueden ser insertados.

**Fix**:
- Agregar `UniqueConstraint("service_id", "date", name="uq_appointment_service_datetime")` en el modelo `Appointment`
- Ejecutar `create_appointment` dentro de transacción con `REPEATABLE READ`
- Capturar `IntegrityError` → retornar "Ese horario acaba de ser tomado" + nuevos slots disponibles

## Non-Negotiable Rules

- Los 2 bugs se corrigen antes de cualquier otra mejora de esta spec.
- `state_stack` no debe persistir más de 10 niveles (prevenir stack infinito).
- El contador de intentos se reinicia al avanzar de estado exitosamente.
- La búsqueda de próximos días disponibles se limita a 14 días desde la fecha solicitada.
- La paginación preserva el contexto del servicio y fecha seleccionados.
- El constraint de doble booking es la única fuente de verdad — no depender de re-validación previa.

## Acceptance Tests

- "para hoy a las 3" → resuelve fecha como hoy, no pide fecha de nuevo.
- "el viernes" sin hora → slots mostrados incluyen `service_id` en pending_data → "sí" confirma correctamente.
- "vete al diablo" → advertencia suave + menú principal.
- "cómo hago un pastel" → "Este sistema gestiona citas" + menú.
- Usuario en `awaiting_slot_selection` teclea "9" → vuelve a `awaiting_date` con fecha limpiada.
- Flujo expirado con cita a medias → pregunta si continuar → "sí" restaura el flujo.
- 3 inputs inválidos consecutivos en `awaiting_slot_selection` → menú principal.
- Día sin slots → sugiere 3 días próximos con disponibilidad numerados.
- Más de 8 slots → "8 → siguiente" aparece; al teclear 8 muestra página 2.
- Dos usuarios confirman mismo slot simultáneamente → uno recibe error + alternativas.

---

## Implementation Notes (v1 — 2026-05-05)

All 39 tasks completed. Key behavioral differences from the original spec:

### Slot pagination
- Page size: **6 slots per page** (keys 1–6 select slots; key 7 = previous page, key 8 = next page).
- The same pagination logic (`_paginate_slots`, `_slots_short_list`) is shared between `booking_handler.py` and `modify_handler.py` via import.

### Session resume
- Expired flows with non-empty `pending_data` ask the user "¿Continuamos donde estabas?" instead of clearing immediately.
- Additional context saved: `resume_data`, `resume_intent`, `resume_state`.
- A "no" reply clears the flow and shows the main menu.

### State stack (back navigation)
- `update_context()` auto-pushes the previous state on every state transition (except idle → anything).
- Transitions back to `idle` automatically clear `state_stack`.
- The `go_back` route in `guided_menu_router.py` pops from `state_stack`; empty stack → idle + menu.

### Attempt counter
- Tracked in `context["attempts"][state]`. Incremented when the handler returns without advancing state.
- Reset when state advances. Cleared on flow termination.

### Next available days
- Both "no-slot" branches in `booking_handler.py` call `get_next_available_days()`.
- Suggested days stored in `pending_data["suggested_days"]` (list of `{"date": "YYYY-MM-DD"}`).
- User selects 1/2/3 to pick a day; selection resolves at the top of `handle_book_appointment` before the regular date check.

### Double booking (REPEATABLE READ)
- `create_appointment()` sets `REPEATABLE READ` isolation and catches `IntegrityError` → returns `{"error": "slot_conflict"}`.
- `handle_booking_confirmation()` checks for this error and shows fresh slot alternatives.
- `UniqueConstraint("service_id", "date")` added to `Appointment` model; Alembic migration `a1b2c3d4e5f6` created.

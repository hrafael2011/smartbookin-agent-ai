# Spec: Fixes del flujo conversacional de Telegram (botones, horarios pasados, botones usados)

**Fecha**: 2026-08-29
**Estado**: aprobado por el usuario (diseño socializado sección por sección)
**Alcance**: canal Telegram del flujo guiado (WhatsApp sin cambios funcionales)

## Contexto

Tras la migración a Inline Keyboards (commit `5a8a356`), una prueba real en
producción confirmó con la BD de Neon que las citas **sí se guardan** (ids 5 y 6,
status `C`), pero el flujo tiene problemas de percepción y bugs silenciosos:

1. **Horarios ya pasados se ofrecen**: a las 11:45 AM la grilla mostró "9:15 AM".
   El usuario agenda un slot vencido → la cita nace "en el pasado" → invisible en
   "ver mis citas" → parece que no se guardó.
2. **Mezcla de opciones de texto numeradas + botones** en el menú principal (y el
   catálogo de servicios).
3. **Botones de mensajes anteriores siguen funcionando** (o quedan huérfanos sin
   distinguir pantalla actual vs. vieja).
4. Barrida de bugs silenciosos (S1, S2, S3, S6, S10, S12, S16) — ver abajo.

## Alcance (cambios)

### F1 — Nunca ofrecer horarios/fechas pasados (cubre S10)

- **Dónde**: `app/services/db_service.py`, `get_availability()`.
- Después de `build_slots`, filtrar slots cuyo `start_datetime` sea `<= _upcoming_now()`.
  Filtro **incondicional** (aplica a cualquier día): cubre slots vencidos del día
  actual y fechas pasadas por texto libre.
- Efectos correctos en cascada: `get_available_days_in_range` /
  `get_next_available_days` dejan de contar días con solo horas vencidas; la
  revalidación de `handle_booking_confirmation` rechaza horarios que vencieron
  mientras el usuario elegía; owner reschedule y API de appointments tampoco
  ofrecen slots pasados.

### F2 — Solo botones: eliminar texto numerado en pantallas con teclado (cubre S6)

- **Menú principal**: nuevo `guided_menu_short(customer_name, *, returning=False)`
  (saludo + "Elegí una opción:", sin "1) Agendar cita…") y
  `main_menu_reply(prefix="", customer_name="")` en `app/utils/telegram_ui.py`.
  `guided_menu()` (texto numerado puro) se mantiene para WhatsApp y fallbacks sin
  teclado.
- Todos los sitios que hoy hacen `BotReply(guided_menu(...), keyboard=main_menu_keyboard())`
  pasan a `main_menu_reply(...)` / `guided_menu_reply(...)`:
  - `guided_menu_router.py`: `_go_back` (sin stack), stale, `cancel_confirm_*`,
    `resume` no, expired-flow sin pending, `_with_menu` y los puntos que devuelven menú.
  - `booking_handler.py` (confirmación exitosa), `cancel_handler.py` (confirmación
    sí/no), `modify_handler.py` (reagendado exitoso),
    `booking_calendar_handler.py` (sin meses disponibles).
- **Catálogo de servicios** (`business_info_handler.handle_business_services`):
  el texto conserva la información **sin numeración** ("Corte — $600, 30 min",
  una línea por servicio) y las **opciones** viven en botones `service_<id>`
  (2 por fila) + footer. El texto informativo no es una lista de opciones.
- **S6 — "Ver mis citas" con 2+ citas** (`check_handler`): quitar la línea
  *"¿Quieres modificar o cancelar alguna? Solo dime cuál 😊"*; agregar una fila de
  acciones `modify_appt_<id>` / `cancel_appt_<id>` **por cada cita visible**
  (hoy solo con exactamente 1 cita).
- `NO_SERVICES_GENERIC` (`app/services/no_services_nlu.py`): "(opción 5)" → sin
  numeración ("en el menú").

### F3 — Bloquear botones de mensajes anteriores: token por pantalla (cubre S16 en parte)

- **Capa de envío Telegram** (`telegram_inbound.py`): al enviar un `BotReply` con
  teclado, generar `secrets.token_hex(4)`, persistir en contexto
  (`conversation_manager.update_context(..., {"screen_token": token})`) y agregar
  el sufijo `|token` a **cada** `callback_data` del teclado
  (helper `telegram_ui.with_screen_token(rows, token)` y
  `split_callback_token(text) -> (base, token|None)`).
- **Parser**: `parse_inline_callback` extrae el token antes de matchear el patrón
  (tolera callbacks sin token para texto tipeado).
- **Dispatch** (`guided_menu_router._handle_inline_callback`): si el callback trae
  token y no coincide con `context.screen_token` → bloqueado
  ("Esa opción ya no está vigente" + menú fresco con token nuevo). Sin token →
  validación por estado actual (compat con texto tipeado).
- Los callbacks `nav_*`/`menu_*` del footer también llevan token (pertenecen a su
  mensaje). El stale-reply regenera token (es una pantalla nueva).
- Convención documentada en `docs/TELEGRAM_UI_CONVENTION.md`.

### S1 — Idempotencia por toque (crítico)

- `telegram_client.extract_message_from_webhook`: para `callback_query`, usar
  `callback_query.id` (único por toque) como `message_id`/`event_id` de dedupe
  (hoy usa el id del mensaje → el 2º toque en el mismo grid se descarta como
  duplicado).
- **S16**: si `callback_query` no trae `message` (mensaje borrado) → descartar con
  log (evita `chat_id = "None"`).

### S2 — Auto-selección silenciosa del primer servicio (crítico)

- `booking_handler._resolve_service_choice`: guard — texto vacío → `""` (hoy
  `"" in "corte"` es `True` y devuelve el primer servicio).
- Con el guard, el dispatch de `time_*` del router (que llama a
  `handle_book_appointment` con `_raw_user_text: ""`) pregunta el servicio con
  botones cuando `pending_data` no lo tiene (igual que `handle_slot_selection`).

### S3 — Excepciones silenciosas

- `logger.exception` en todos los `except` de `booking_handler.py`,
  `cancel_handler.py` y `check_handler.py` (modify ya los tiene).

### S12 — Paginación unificada

- `booking_handler._paginate_slots` delega en `telegram_ui.paginate_slots` con
  `page_size=12` (la grilla ya usa 12; hoy conviven 6 y 12). Ajustar tests que
  dependan del tamaño de página.

## Convención de callback_data (actualizada)

Los callbacks llevan sufijo de token de pantalla: `<ns>_<payload>|<token>`.
El token es opaco (8 hex), rotado por cada mensaje con teclado; no debe
parsearse semánticamente (solo compararse). El mapeo a WhatsApp (mismo id
semántico, sin token) se documenta: WhatsApp List/Reply ids usan la parte
semántica; la validación de estado aplica igual.

## Fuera de alcance

- WhatsApp Business API (solo diseño 1:1 preparado).
- Deuda arquitectónica de timezone (UTC real en storage) — documentada en TECH_DEBT.md.
- `answer_callback_query` (cosmético, se evalúa después).
- Owner channel.

## Verificación

- Tests TDD por cambio:
  - F1: slots del día vencidos excluidos; slots futuros de mañana conservados;
    fecha pasada → sin slots (reloj congelado vía monkeypatch).
  - F2: menú con teclado sin numeración; catálogo con botones `service_<id>`;
    check multi-cita con botones por cita; NO_SERVICES sin numeración.
  - F3: token en callbacks; token viejo → bloqueado; token actual → ejecuta;
    sin token → validación por estado.
  - S1: extractor devuelve `callback_query.id`; dos toques en el mismo mensaje
    pasan el dedupe; mensaje sin `message` se descarta.
  - S2: `_resolve_service_choice("")` → `""`; flujo time_* sin servicio → pregunta
    con botones.
  - S12: paginación 12 unificada.
- Suite completa en verde; actualizar `docs/TELEGRAM_UI_CONVENTION.md`.

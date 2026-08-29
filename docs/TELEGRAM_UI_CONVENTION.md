# Convención de UI conversacional: Inline Keyboards y callback_data

Referencia para el canal Telegram de SmartBooking AI y para el port futuro a
WhatsApp Business API. Define cómo se construyen los teclados, la convención de
`callback_data` y cómo la lógica de backend procesa cada selección.

> Implementado en `app/utils/telegram_ui.py` (builders), `app/core/response_builder.py`
> (`BotReply`) y `app/services/guided_menu_router.py` (dispatch de callbacks).

## 1. Respuesta del bot: `BotReply`

Toda pantalla del flujo devuelve un `BotReply`, que **es un `str`** (compatibilidad
total con el canal WhatsApp y con las comparaciones de texto) y además lleva un
teclado inline opcional:

```python
BotReply(texto, keyboard=[[{"text": "✅ Confirmar", "callback_data": "confirm_yes"}]])
```

El teclado es una lista de filas; cada fila una lista de botones
`{text, callback_data}`. El canal Telegram serializa esto a
`reply_markup.inline_keyboard` (`telegram_inbound._reply_markup_for`).

## 2. Footer de navegación centralizado

`telegram_ui.build_nav_footer()` devuelve siempre la fila:

```
[🔙 Volver nav_back] [🏠 Menú nav_menu] [❌ Salir nav_exit]
```

**Toda pantalla del flujo concatena el footer al final de su teclado** usando
`telegram_ui.with_footer(rows)`. Única excepción deliberada: el **menú principal**
(pantalla raíz — `nav_back`/`nav_menu` serían no-ops desde allí).

| Callback | Efecto |
|---|---|
| `nav_back` | Pop de `state_stack` → pantalla anterior |
| `nav_menu` | Limpia contexto → menú principal |
| `nav_exit` | Limpia contexto → cierre de la consulta |

## 3. Convención de callback_data

Los ids son **únicos y semánticos**, namespaced por tipo de acción. Nunca se
reutiliza el mismo id para significados distintos entre pantallas (elimina la
sobrecarga de "1 = Corte" vs "1 = viernes" vs "1 = 9:00 AM").

| Namespace | Formato | Ejemplo | Significado |
|---|---|---|---|
| `service_<id>` | `service_3` | Elegir el servicio con id 3 (resuelto por id, no por nombre) |
| `day_<fecha>` | `day_2026-08-29` | Elegir el día (ISO `YYYY-MM-DD`) |
| `time_<fecha>_<hora>` | `time_2026-08-29_09:00` | Elegir horario (hora en **24h**; se muestra en 12h) |
| `slots_page_<n>` | `slots_page_1` | Paginar la grilla de horarios |
| `month_<n>` / `week_<n>` | `month_1` | Calendario: mes / semana (índice 1-3) |
| `month_browse` | — | "Buscar en otro mes" desde la semana actual |
| `menu_<accion>` | `menu_agendar` | Menú principal: `agendar` / `ver_citas` / `cambiar` / `cancelar` / `horarios` |
| `nav_back` / `nav_menu` / `nav_exit` | — | Footer centralizado |
| `confirm_yes` / `confirm_no` | — | Confirmar cita / ver otro horario |
| `cancel_appt_<id>` | `cancel_appt_11` | Cita a cancelar (id real de BD) |
| `cancel_confirm_yes` / `cancel_confirm_no` | — | Confirmar / mantener al cancelar |
| `modify_appt_<id>` | `modify_appt_12` | Cita a modificar (id real de BD) |
| `resume_yes` / `resume_no` | — | Continuar / cerrar sesión vencida |

**Token de pantalla (sufijo `|<token>`)**: cada mensaje con teclado rota un token
opaco (`secrets.token_hex(4)`), persistido en `context.screen_token` por la capa de
envío de Telegram (`telegram_inbound._send_bot_reply`), y lo agrega como sufijo a
cada callback (`time_2026-08-29_09:00|a1b2`). Al recibir un callback, el dispatch
compara el token contra `screen_token`: mismatch = botón de un mensaje anterior =
**bloqueado** ("Esa opción ya no está vigente" + menú fresco). Callbacks sin token
(texto tipeado) usan la validación por estado. La idempotencia de webhook deduplica
por `callback_query.id` (único por toque), no por id del mensaje.

**Validación**: cada callback se despacha **solo si corresponde al paso actual del
flujo** (`_callback_valid_for_state` en `guided_menu_router`). Un callback huérfano
(botón viejo pulsado fuera de contexto) responde "Esa opción ya no está vigente" y
muestra el menú. Los namespaces `service_*` / `cancel_appt_*` / `modify_appt_*`
también se admiten desde `idle` (catálogo de servicios y pantalla "ver mis citas");
sus dispatch validan la propiedad de la cita (`get_customer_appointment`, que solo
devuelve citas activas `P`/`C`).

## 4. Mapa pantalla → teclado

| Pantalla | Botones propios | Footer |
|---|---|---|
| Menú principal | 5 × `menu_*` (1 por fila) | — (raíz) |
| Selección de servicio | `service_<id>` (2 por fila) | ✅ |
| Calendario: semana actual | `day_<fecha>` + `month_browse` | ✅ |
| Calendario: mes / semana / día | `month_<n>` / `week_<n>` / `day_<fecha>` | ✅ |
| Grilla de horarios | `time_<fecha>_<HH:MM>` (3 columnas) + `slots_page_<n>` (◀ Antes / Después ▶) | ✅ |
| Confirmación de cita | `confirm_yes` / `confirm_no` | ✅ |
| Ver mis citas (vacío) | `menu_agendar` (CTA) | ✅ |
| Ver mis citas (con citas) | `modify_appt_<id>` / `cancel_appt_<id>` por cita | ✅ |
| Cancelar / modificar | `cancel_appt_<id>` / `modify_appt_<id>` por cita real | ✅ |
| Confirmar cancelación | `cancel_confirm_yes` / `cancel_confirm_no` | ✅ |
| Horarios y ubicación | — | ✅ |
| Servicios del negocio | `menu_agendar` (CTA) | ✅ |
| Sesión vencida | `resume_yes` / `resume_no` | ✅ |

## 5. Dígitos sueltos y `last_screen`

Los usuarios pueden seguir escribiendo texto. Para evitar que un dígito escrito
tras una pregunta abierta dispare una opción global del menú (bug corregido), los
dígitos 1-5 en contexto `idle` **solo** se interpretan como opciones del menú si la
pantalla visible era el menú principal (`last_screen == "main_menu"`, mantenido por
`conversation_manager.mark_main_menu`). En cualquier otro caso caen al pipeline NLU
(fallback ambiguo → menú con botones).

## 6. Horarios y fechas pasados

`get_availability` nunca ofrece slots con `start_datetime <= _upcoming_now()`
(reloj operativo del negocio estampado como UTC — el convenio wall-clock-as-UTC del
almacenamiento). El filtro es incondicional (aplica a cualquier día): tampoco se
puede agendar en fechas pasadas por texto libre, y los días con solo horas vencidas
dejan de contarse como disponibles en el calendario.

## 7. Port a WhatsApp Business API (futuro)

Cada botón de Telegram mapea 1:1 a un componente de WhatsApp usando el **mismo id**:

| Nº de opciones | Componente WhatsApp | Notas |
|---|---|---|
| ≤ 3 | Reply Buttons | `button_reply.id` = callback_data |
| > 3 | List Message | `list_reply.id` = callback_data; secciones si aplica (ej. días: "Esta semana" / "Próxima semana") |

Reglas para que el dispatch sea compartido sin duplicar código por canal:

1. El `id` de `interactive.list_reply` / `button_reply` **es el mismo string** que
   la parte semántica del `callback_data` de Telegram (ej. `day_2026-08-29`,
   `service_3`) — **sin** el sufijo de token (el token es solo de la capa Telegram;
   la validación de estado aplica igual en WhatsApp).
2. La clasificación de la selección vive en un solo lugar:
   `telegram_ui.parse_inline_callback(text) -> {ns, value, token}`.
3. El routing/estados no mencionan el canal: un webhook de WhatsApp que reciba
   `day_2026-08-29` debe terminar llamando al mismo dispatch que Telegram.
4. `BotReply.text_plain` es el texto alternativo para canales sin teclado: WhatsApp
   envía el menú **numerado** (sin botones), mientras Telegram envía el texto corto
   + teclado. El canal decide qué campo serializar.

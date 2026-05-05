# Contract: Guided Menu Router

## Purpose

Centralizar la decisión conversacional común para WhatsApp y Telegram. Los canales normalizan entrada/salida; este contrato decide si el mensaje se maneja por menú, fallback, flujo activo o IA.

## Public API

```python
@dataclass(frozen=True)
class RouteDecision:
    kind: str
    option: str | None = None
    reason: str = ""
    uses_ai: bool = False
    counts_total: bool = True


def route_guided_message(message_text: str, context: dict) -> RouteDecision:
    ...


async def execute_guided_route(
    business_id: int,
    user_key: str,
    decision: RouteDecision,
    context: dict,
) -> str | None:
    ...
```

## Decision Kinds

- `show_menu`: mostrar menú por saludo, ayuda o comando explícito.
- `menu_option`: ejecutar opción `1` a `5` desde `idle`.
- `direct_shortcut`: texto directo claro que puede entrar a flujo guiado.
- `business_info`: pregunta de horarios/ubicación/servicios que se responde con datos persistidos.
- `ambiguous_fallback`: texto ambiguo que vuelve al menú.
- `out_of_domain`: tema fuera del dominio de citas/negocio.
- `abusive`: grosería o abuso; límite profesional + menú.
- `active_flow`: un flujo activo debe interpretar el mensaje.
- `pass_to_nlu`: requiere IA para interpretación.
- `unsupported`: tipo o contenido no soportado.
- `go_main_menu`: limpiar flujo y mostrar menú principal.
- `go_back`: volver al paso anterior del flujo si existe.
- `exit_flow`: cerrar consulta actual y quedar en `idle`.
- `expired_flow`: cerrar flujo por inactividad y mostrar menú.

## Invariants

- `uses_ai` MUST be `False` for `show_menu`, `menu_option`, `business_info`, `ambiguous_fallback`, `out_of_domain`, `abusive`, and deterministic `active_flow` steps.
- `uses_ai` MAY be `True` only for `direct_shortcut`, `pass_to_nlu`, or active-flow steps that require date/time/language interpretation.
- Numeric options `1` to `5` are global menu only when `context["state"] == "idle"`.
- During active flows, numeric messages belong to the active handler.
- Universal navigation commands have priority before business routing.
- Active flows expire after 30 minutes of user inactivity.
- Expiration clears flow state but preserves customer identity and business/channel binding.
- `execute_guided_route()` MUST NOT send channel messages directly.
- `execute_guided_route()` MAY update `conversation_manager` state/pending data when entering a guided flow.
- Appointment creation/cancel/modify MUST remain inside handlers, never inside the router.

## Channel Integration

After channel-specific identity and business resolution:

1. Fetch context.
2. Call `route_guided_message()`.
3. Call `consume_daily_quota(..., is_ai_message=decision.uses_ai)`.
4. If quota blocks, send quota message and stop.
5. Call `execute_guided_route()`.
6. If it returns text, send channel response and persist assistant message.
7. Otherwise call `run_conversation_turn()`.

## Acceptance Tests

- `hola` in `idle` -> `show_menu`, `uses_ai=False`.
- `1` in `idle` -> `menu_option`, `option="1"`, `uses_ai=False`.
- `1` in `awaiting_slot_selection` -> `active_flow`, not `menu_option`.
- `quiero cita mañana a las 10` in `idle` -> `direct_shortcut` or `pass_to_nlu`, no mutation.
- insult in `idle` -> `abusive`, `uses_ai=False`.
- off-domain question in `idle` -> `out_of_domain`, `uses_ai=False`.
- `0` during active flow -> `go_main_menu`, clears `pending_data`.
- `9` during active flow -> `go_back` if previous step exists, otherwise menu.
- `x` during active flow -> `exit_flow`, clears `pending_data`.
- stale active flow older than 30 minutes -> `expired_flow`, clears flow state.

## Operational Notes

- The router does not own idempotency storage, but channel integration must ensure duplicate channel events do not repeat critical mutations.
- The router must prefer deterministic incomplete-configuration responses over IA when services, schedule, or location are missing.
- Time-sensitive decisions should use the project default timezone `America/Santo_Domingo` until per-business timezone support exists.

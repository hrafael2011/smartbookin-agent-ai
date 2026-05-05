# Implementation Plan: Bot Con Menú Guiado Híbrido

**Branch**: `001-guided-menu-bot` | **Date**: 2026-04-29 | **Spec**: `specs/001-guided-menu-bot/spec.md`  
**Input**: Feature specification for menu-first conversational behavior.

## Summary

Promover el menú guiado de atajo/fallback a estrategia principal del bot. Centralizar resolución de opciones, mantener IA solo como intérprete auxiliar y asegurar que acciones críticas se ejecuten únicamente por handlers determinísticos con estado válido y confirmación explícita.

## Technical Context

**Language/Version**: Python/FastAPI backend actual.  
**Primary Dependencies**: FastAPI, SQLAlchemy, existing handlers, existing `conversation_manager`, OpenAI NLU service.  
**Storage**: Sin cambios de schema; usa `conversation_states` actual.  
**Testing**: pytest backend.  
**Target Platform**: Webhooks WhatsApp y Telegram.  
**Project Type**: Conversational backend feature.  
**Performance Goals**: Cero llamadas IA para menú, saludos, opciones numéricas y confirmaciones cortas.  
**Constraints**: Multi-tenant, channel parity, no mutation without confirmation, 30-minute active-flow timeout.  
**Scale/Scope**: Fase 1 MVP; texto numerado, sin botones obligatorios.

## Constitution Check

- Specs-first: PASS, feature definida en `spec.md`.
- Tenant safety: PASS, no cambia resolución de negocio; debe preservarse.
- Deterministic actions: PASS, IA solo interpreta.
- Guided conversation first: PASS, es el objetivo central.
- Channel parity: PASS, WhatsApp y Telegram deben compartir comportamiento.
- Tests before sensitive changes: REQUIRED antes de tocar routing/handlers.

## Project Structure

### Documentation (this feature)

```text
specs/001-guided-menu-bot/
├── spec.md
├── plan.md
├── research.md
├── quickstart.md
├── contracts/
│   └── guided-menu-router.md
└── tasks.md
```

### Source Code (repository root)

```text
backend/api-backend/app/
├── utils/conversation_routing.py
├── core/orchestrator.py
├── services/telegram_inbound.py
├── main.py
└── handlers/

backend/api-backend/tests/
├── test_orchestrator_e2e.py
├── test_webhook_endpoints_ci.py
└── test_conversation_states.py
```

**Structure Decision**: Mantener lógica conversacional en backend. No tocar frontend ni base de datos para fase 1.

## Implementation Approach

- Crear un módulo de routing guiado con una función de decisión pura y una función async de ejecución. La decisión pura clasifica `show_menu`, `menu_option`, `direct_shortcut`, `out_of_domain`, `abusive`, `pass_to_flow` o `pass_to_nlu`.
- Usar el routing guiado en WhatsApp y Telegram antes de cualquier IA cuando `state == idle`. En flujos activos, permitir solo `menu` explícito como salida segura.
- Mantener active-flow precedence: si `state != idle`, el número pertenece al flujo actual.
- Cambiar fallback de baja confianza para que vuelva a menú o pregunta guiada.
- Añadir detección simple, determinística y conservadora de fuera de dominio/grosería con respuesta breve y menú.
- Mantener NLU para atajos directos y extracción dentro de flujos, pero sin autoridad de mutación.
- Registrar logs ligeros de ruta (`guided_menu`, `guided_option`, `shortcut_nlu`, `fallback_boundary`) para depuración sin guardar datos sensibles adicionales.
- Implementar navegación universal antes de routing de negocio: `0/menu/inicio`, `9/volver/atrás`, `x/salir/terminar/cerrar`.
- Implementar expiración de flujo activo por inactividad de 30 minutos, preferiblemente pasiva al recibir el siguiente mensaje y sin envío proactivo en fase 1.
- Mantener idempotencia defensiva para mensajes/eventos duplicados, especialmente antes de acciones críticas.
- En MVP, la idempotencia usa PostgreSQL en Railway mediante una tabla de eventos procesados; no usar Redis para esta parte para evitar costo operativo adicional.
- Revalidar disponibilidad en el punto exacto de confirmación de cita y tratar conflictos con una respuesta guiada.
- Usar timezone operacional `America/Santo_Domingo` en mensajes de fecha/hora y parsing relativo.

## Routing Contract

El módulo de menú guiado debe exponer un contrato equivalente a:

```text
route_guided_message(message_text, context) -> RouteDecision
execute_guided_route(business_id, user_key, decision, context) -> Optional[str]
```

`RouteDecision` debe incluir:

- `kind`: tipo de ruta.
- `option`: `1` a `5` cuando aplique.
- `reason`: cadena corta para logs/tests.
- `uses_ai`: `false` para rutas determinísticas.
- `counts_total`: `true` para mensajes de usuarios vinculados que deben consumir cuota total.

El contrato no debe enviar mensajes por canal ni conocer WhatsApp/Telegram. Los webhooks siguen siendo responsables de enviar la respuesta.

`kind` debe usar valores cerrados:

- `show_menu`
- `menu_option`
- `direct_shortcut`
- `business_info`
- `ambiguous_fallback`
- `out_of_domain`
- `abusive`
- `active_flow`
- `pass_to_nlu`
- `unsupported`
- `go_main_menu`
- `go_back`
- `exit_flow`
- `expired_flow`

## Channel Flow Order

Para WhatsApp y Telegram, el orden correcto tras resolver negocio/usuario es:

1. Obtener contexto.
2. Aplicar expiración pasiva si el flujo activo superó 30 minutos de inactividad.
3. Llamar `route_guided_message(message_text, context)`.
4. Consumir cuota con `is_ai_message = decision.uses_ai`.
5. Si cuota bloquea, enviar mensaje de límite y terminar.
6. Si `execute_guided_route(...)` devuelve respuesta, enviarla y guardar historial.
7. Si la decisión requiere IA o flujo activo, pasar a `run_conversation_turn(...)`.

Esto evita duplicación de `classify_route()` por canal y preserva que la cuota IA agotada no bloquee menú guiado.

## Navigation Contract

Comandos universales:

- Principal: `0`, `menu`, `menú`, `inicio`, `menú principal`.
- Volver: `9`, `volver`, `atrás`, `atras`.
- Salir: `x`, `salir`, `terminar`, `cerrar`, `cerrar consulta`.

Estado al salir o volver al menú:

- `state = "idle"`
- `current_intent = None`
- `pending_data = {}`
- conservar `customer_id`, `customer_name`, `recent_messages`, `business_id`, `phone_number`.

Para `volver`, fase 1 puede usar un historial simple en `pending_data["navigation_stack"]` o `pending_data["previous_state"]`. Si no hay paso anterior confiable, mostrar menú principal.

## Timeout Policy

Recomendación adoptada: **30 minutos de inactividad para flujos activos**.

Rationale:

- Dialogflow CX conserva datos de sesión por 30 minutos por defecto.
- Rasa usa 60 minutos por defecto para iniciar nueva sesión tras inactividad.
- Botpress permite timeouts configurables y documenta patrones de soporte con expiración corta, incluso 15 minutos.
- WhatsApp tiene una ventana de atención de 24 horas, pero eso regula mensajes free-form del canal; no debe usarse como timeout UX porque dejaría flujos transaccionales abiertos demasiado tiempo.

Implementación fase 1:

- Cierre pasivo al recibir el siguiente mensaje si `last_activity` del flujo activo tiene más de 30 minutos.
- No enviar mensaje proactivo de timeout en fase 1 para evitar complejidad operativa y reglas de canal.
- Al cerrar por timeout, responder: `Cerré la consulta anterior por inactividad. Te dejo el menú principal:`.

## Fallback Copy

- Ambiguo: `No estoy seguro de qué querés hacer. Elegí una opción:`
- Fuera de dominio: `Por ahora puedo ayudarte con citas, servicios, horarios y ubicación del negocio. Elegí una opción:`
- Grosería/abuso: `Estoy aquí para ayudarte con citas del negocio. Si querés continuar, elegí una opción:`

Después de cada frase, incluir el menú numerado vigente.

## Operational Safeguards

- **Idempotencia**: registrar o reconocer `message_id`/evento cuando esté disponible. Si llega un duplicado, responder `ok` sin repetir mutaciones.
- **Persistencia MVP**: usar PostgreSQL en Railway con tabla `processed_channel_events` y constraint único sobre `channel`, `business_id`, `user_key`, `event_id`. La inserción atómica decide si el evento se procesa. Redis queda fuera del MVP para esta necesidad.
- **Concurrencia**: antes de crear una cita, reconsultar disponibilidad del slot seleccionado. Si ya no está libre, volver a mostrar alternativas.
- **Timezone**: interpretar fechas relativas y presentar horarios con `America/Santo_Domingo` hasta que exista timezone por negocio.
- **Configuración incompleta**: si faltan servicios, horarios, ubicación o channel config, responder sin inventar y guiar al menú o al dueño.
- **Errores de proveedores**: fallos de OpenAI, WhatsApp, Telegram o DB deben producir logs claros y respuestas seguras cuando el canal aún permita responder.
- **Auditoría mínima**: loguear acciones críticas con canal, `business_id`, user key, acción, appointment id si existe y resultado.
- **Identidad cross-channel**: Telegram y WhatsApp se tratan como clientes separados en fase 1.
- **Handoff humano**: queda fuera de fase 1; debe entrar como spec/backlog antes de agregarse al menú.

## Definition Of Done

- WhatsApp y Telegram no contienen lógica propia para ejecutar opciones `1` a `5`.
- La decisión de uso de IA viene de `RouteDecision.uses_ai`.
- Los tests prueban rutas determinísticas sin NLU.
- Los tests prueban precedencia de flujo activo sobre menú global.
- Los tests prueban cuota IA agotada vs cuota total agotada.
- Los tests prueban navegación universal y timeout de 30 minutos.
- Los tests o validaciones prueban idempotencia, revalidación de slot y configuración incompleta.
- La implementación agrega migración Alembic `d4e5f6a7b8c9` para idempotencia persistente en PostgreSQL/Railway.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Ninguna prevista | N/A | N/A |

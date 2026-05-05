# Feature Specification: Bot Con Menú Guiado Híbrido

**Feature Branch**: `001-guided-menu-bot`  
**Created**: 2026-04-29  
**Status**: Draft  
**Input**: Convertir el bot a una experiencia menu-first donde la IA interpreta, pero no ejecuta acciones.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Menú Principal Predecible (Priority: P1)

Como cliente del negocio, quiero recibir un menú numerado claro cuando saludo, pido ayuda o escribo algo ambiguo, para saber exactamente qué puedo hacer sin depender de conversación libre.

**Why this priority**: Es la base de la fase guiada y reduce errores de intención.

**Independent Test**: En WhatsApp y Telegram, enviar `hola`, `menu`, `ayuda` o texto ambiguo desde `idle` muestra el menú sin llamar IA.

**Acceptance Scenarios**:

1. **Given** conversación en `idle`, **When** el cliente envía `hola`, **Then** recibe menú numerado.
2. **Given** conversación en `idle`, **When** el cliente envía `menu`, **Then** recibe menú numerado.
3. **Given** conversación en `idle`, **When** el cliente envía un mensaje ambiguo, **Then** recibe menú o pregunta guiada sin acción.

---

### User Story 2 - Acciones Por Opciones Numeradas (Priority: P1)

Como cliente, quiero elegir una opción numérica para agendar, ver, cambiar, cancelar o consultar información, para avanzar por un flujo confiable.

**Why this priority**: Convierte el menú en interfaz principal y no solo en fallback.

**Independent Test**: Desde `idle`, enviar `1`, `2`, `3`, `4` o `5` dispara el flujo correspondiente sin IA.

**Acceptance Scenarios**:

1. **Given** conversación en `idle`, **When** el cliente envía `1`, **Then** el bot inicia agendamiento y muestra servicios.
2. **Given** conversación en `idle`, **When** el cliente envía `2`, **Then** el bot muestra o busca citas activas.
3. **Given** conversación en `idle`, **When** el cliente envía `3`, **Then** el bot inicia cambio de cita.
4. **Given** conversación en `idle`, **When** el cliente envía `4`, **Then** el bot inicia cancelación de cita.
5. **Given** conversación en `idle`, **When** el cliente envía `5`, **Then** el bot responde horarios y ubicación o indica qué dato falta.

---

### User Story 3 - Atajos Naturales Sin Acción Directa (Priority: P2)

Como cliente, quiero poder escribir “quiero cita mañana a las 10” y que el bot entienda mi intención, pero todavía me lleve por pasos guiados antes de crear una cita.

**Why this priority**: Mantiene comodidad sin ceder control a la IA.

**Independent Test**: Enviar un atajo de reserva entra al flujo de agendamiento, conserva datos interpretables y exige selección/confirmación antes de mutar datos.

**Acceptance Scenarios**:

1. **Given** conversación en `idle`, **When** el cliente envía `quiero cita mañana a las 10`, **Then** el bot entra a agendamiento pero no crea cita.
2. **Given** una reserva con datos completos, **When** falta confirmación explícita, **Then** no se crea cita.
3. **Given** confirmación explícita válida, **When** el slot sigue disponible, **Then** el handler determinístico crea la cita.

---

### User Story 4 - Límites Para Groserías Y Fuera De Contexto (Priority: P3)

Como negocio, quiero que el bot responda con límites tranquilos ante groserías o temas fuera de dominio, para mantener una experiencia profesional y no gastar IA innecesaria.

**Why this priority**: Evita conversaciones improductivas y reduce riesgo reputacional.

**Independent Test**: Mensajes ofensivos o fuera del dominio devuelven una respuesta breve con menú, sin acción ni escalada innecesaria.

**Acceptance Scenarios**:

1. **Given** conversación en `idle`, **When** el cliente envía un insulto, **Then** el bot responde que puede ayudar con citas y muestra menú.
2. **Given** conversación en `idle`, **When** el cliente pregunta algo fuera del negocio, **Then** el bot limita el alcance y muestra menú.

---

### User Story 5 - Navegación Universal Y Cierre Por Inactividad (Priority: P1)

Como cliente, quiero poder volver, ir al menú principal o salir en cualquier momento, y quiero que una consulta abandonada se cierre sola, para no quedar atrapado en un flujo viejo.

**Why this priority**: La navegación explícita es una expectativa profesional en bots guiados y evita errores cuando el usuario vuelve horas después.

**Independent Test**: En cualquier estado activo, `0/menu`, `9/volver` y `x/salir` ejecutan navegación segura. Si pasa el timeout de inactividad, el flujo se cierra y el siguiente mensaje inicia desde menú/idle.

**Acceptance Scenarios**:

1. **Given** un flujo activo, **When** el cliente envía `0`, `menu` o `inicio`, **Then** se limpia el flujo actual y se muestra menú principal.
2. **Given** un flujo activo con paso anterior conocido, **When** el cliente envía `9`, `volver` o `atrás`, **Then** vuelve al paso anterior sin ejecutar acciones finales.
3. **Given** un flujo activo, **When** el cliente envía `x`, `salir`, `terminar` o `cerrar`, **Then** se cierra la consulta actual y queda en `idle`.
4. **Given** un flujo activo sin actividad por 30 minutos, **When** el cliente vuelve a escribir, **Then** el bot informa que cerró la consulta anterior y muestra menú principal.

### Edge Cases

- Números enviados dentro de selección de servicios, horarios o citas activas MUST NOT activar el menú global.
- Si no hay servicios configurados, opción `1` MUST responder con el mensaje de negocio sin servicios y no llamar IA.
- Si no hay citas activas, opciones `2`, `3` y `4` MUST responder con estado claro.
- Si IA falla o devuelve baja confianza, el bot MUST volver al menú o a una pregunta guiada.
- Si el cliente pide horarios con texto libre, el bot MAY responder horarios directamente o dirigir a opción `5`, pero MUST NOT inventar datos.
- Si el total daily limit se alcanza, el bot puede bloquear; si solo el límite IA se alcanza, flujos guiados deben seguir disponibles.
- La clasificación de si un mensaje consume cuota IA MUST salir de la decisión del router/orchestrator, no de una heurística duplicada por canal.
- `cancelar` durante un flujo de reserva puede significar abandonar el proceso; `cancelar cita` u opción `4` desde `idle` significa cancelar una cita existente.
- `salir` no debe borrar `customer_id` ni `customer_name`; solo cierra la consulta/flujo actual.
- Si el usuario usa `0/menu` justo antes de confirmar una cita, el sistema debe descartar el borrador sin crear la cita.
- Si WhatsApp o Telegram reenvían el mismo evento, el sistema no debe crear citas duplicadas ni repetir cancelaciones/modificaciones.
- Si dos usuarios intentan confirmar el mismo horario, solo una confirmación debe ganar después de revalidar disponibilidad.
- Si el negocio no tiene servicios, horarios o ubicación configurados, el bot debe decirlo de forma clara y no inventar datos.
- Si falla OpenAI, base de datos, disponibilidad o envío por canal, el bot debe responder con un mensaje seguro cuando sea posible y registrar el error.

## Conversational Policy

La política oficial de decisión para esta fase es:

1. **Active flow first**: si `ConversationState.state != idle`, el mensaje pertenece al flujo activo. Números, `sí/no`, nombres de servicio, fechas y horas se interpretan dentro de ese estado.
2. **Menu first in idle**: si `state == idle`, saludos, `menu`, `ayuda`, opciones `1` a `5`, preguntas de capacidades y mensajes ambiguos se resuelven sin IA cuando sea posible.
3. **IA as interpreter only**: la IA puede clasificar atajos naturales y extraer fecha/hora/servicio, pero su salida no puede mutar datos.
4. **Handlers execute**: crear, cancelar, modificar o confirmar citas solo ocurre en handlers determinísticos.
5. **Professional boundary**: groserías, abuso y fuera de dominio reciben límite breve y menú; no se discuten ni escalan a conversación libre.
6. **Quota after routing decision**: primero se decide si el mensaje requiere IA; luego se consume cuota total y, solo si aplica, cuota IA.
7. **Universal navigation**: `0/menu/inicio`, `9/volver/atrás` y `x/salir/terminar/cerrar` deben funcionar en cualquier flujo donde sea seguro.
8. **Session timeout**: los flujos activos expiran por inactividad; al expirar se limpia `current_intent`, `pending_data` y `state`, conservando datos del cliente.
9. **Operational safety**: retries, duplicated events, concurrent slot selection, missing business configuration, timezone and provider failures must be handled explicitly.

## Behavior Matrix

| Estado | Mensaje del cliente | Resultado esperado | IA |
|---|---|---|---|
| `idle` | `hola`, `buenas`, `ayuda`, `menu` | Mostrar menú numerado | No |
| `idle` | `1` | Iniciar agendamiento y mostrar servicios o no-servicios | No |
| `idle` | `2` | Consultar citas activas | No |
| `idle` | `3` | Iniciar flujo de cambio de cita | No |
| `idle` | `4` | Iniciar flujo de cancelación | No |
| `idle` | `5` | Responder horarios/ubicación desde datos del negocio | No |
| `idle` | `quiero cita mañana a las 10` | Entrar a agendamiento guiado con datos interpretados; no crear cita | Sí, solo interpretación |
| `idle` | `qué horario tienen` | Responder información del negocio o dirigir a opción `5`; no inventar | No preferido |
| `idle` | mensaje ambiguo | Menú o pregunta guiada | No preferido |
| `idle` | insulto o abuso | Límite profesional + menú | No |
| `idle` | fuera de dominio | Alcance del bot + menú | No |
| cualquier estado | `0`, `menu`, `inicio` | Limpiar flujo actual y mostrar menú principal | No |
| cualquier flujo activo | `9`, `volver`, `atrás` | Volver al paso anterior si existe; si no, menú principal | No |
| cualquier flujo activo | `x`, `salir`, `terminar`, `cerrar` | Cerrar consulta, limpiar flujo y quedar en `idle` | No |
| `awaiting_service` | `1`, `2`, nombre de servicio | Elegir servicio dentro del flujo | No preferido |
| `awaiting_date` | `mañana`, `viernes`, fecha | Guardar fecha y seguir flujo | Puede interpretar fecha |
| `awaiting_slot_selection` | `1`, `primero`, hora exacta | Elegir horario de la lista activa | No preferido |
| `awaiting_booking_confirmation` | `sí`, `confirmo`, `ok` | Revalidar disponibilidad y crear cita | No |
| `awaiting_booking_confirmation` | `no`, `otra hora` | Volver a horarios o pedir hora | No |
| `awaiting_cancel_confirmation` | `sí` | Cancelar cita seleccionada | No |
| `awaiting_cancel_confirmation` | `no` | Mantener cita y volver a menú/idle | No |
| flujo activo inactivo 30 min | siguiente mensaje del cliente | Informar cierre por inactividad y mostrar menú/continuar desde `idle` | No |

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema MUST usar menú numerado como experiencia principal en estado `idle`.
- **FR-002**: El sistema MUST resolver opciones `1` a `5` sin llamar IA cuando el contexto está en `idle`.
- **FR-003**: El sistema MUST mantener una única lógica funcional de menú para WhatsApp y Telegram, compartida o cubierta por tests de paridad.
- **FR-004**: La IA MUST limitarse a interpretar intención y datos como fecha, hora o servicio.
- **FR-005**: La IA MUST NOT crear, cancelar, modificar ni confirmar citas.
- **FR-006**: Crear, cancelar o modificar citas MUST requerir handler determinístico, estado válido y confirmación explícita cuando corresponda.
- **FR-007**: Los atajos escritos desde `idle` MUST entrar a flujos guiados, no ejecutar acciones finales.
- **FR-008**: Mensajes ambiguos MUST recibir menú o pregunta guiada.
- **FR-009**: Mensajes groseros o fuera de contexto MUST recibir límite breve y menú.
- **FR-010**: Las selecciones numéricas dentro de flujos activos MUST resolver el paso activo antes que el menú global.
- **FR-011**: El sistema MUST evitar llamadas IA para saludos, ayuda, menú, opciones numéricas, confirmaciones cortas y selecciones numéricas de listas.
- **FR-012**: Las respuestas MUST ser consistentes en WhatsApp y Telegram con texto numerado.
- **FR-013**: El sistema MUST documentar y preservar la precedencia `active flow > idle menu > IA interpretation > handlers execute`.
- **FR-014**: El sistema MUST NOT usar IA para responder datos factuales de negocio si esos datos no están en base de datos o servicios determinísticos.
- **FR-015**: Un comando explícito `menu` durante un flujo activo MUST salir de forma segura del flujo, limpiando `pending_data` cuando no haya una mutación confirmada en progreso.
- **FR-016**: Si un usuario pide una capacidad soportada con texto libre desde `idle`, el sistema SHOULD dirigirlo a la opción guiada equivalente o iniciar el flujo guiado equivalente sin ejecutar acción final.
- **FR-017**: El sistema MUST consumir cuota diaria total para mensajes válidos de usuarios vinculados, pero MUST consumir cuota IA solo cuando la decisión final vaya a invocar NLU/IA.
- **FR-018**: Si la cuota IA está agotada, el sistema MUST mantener disponibles las rutas determinísticas de menú mientras la cuota total no esté agotada.
- **FR-019**: Si la cuota total está agotada, el sistema MUST bloquear nuevas interacciones del chat hasta el siguiente día UTC, incluyendo menú guiado.
- **FR-020**: Todos los mensajes guiados de flujo activo SHOULD incluir opciones de navegación: `9) Volver`, `0) Menú principal`, `X) Salir`, salvo mensajes extremadamente cortos de confirmación donde se aceptan equivalentes por texto.
- **FR-021**: `0`, `menu`, `menú`, `inicio` y `menú principal` MUST volver al menú principal desde cualquier flujo, limpiando borradores no confirmados.
- **FR-022**: `9`, `volver` y `atrás` MUST volver al paso anterior si hay historial de navegación; si no hay historial, MUST mostrar menú principal.
- **FR-023**: `x`, `salir`, `terminar`, `cerrar` y `cerrar consulta` MUST cerrar el flujo actual, limpiar `current_intent` y `pending_data`, conservar datos del cliente y dejar `state=idle`.
- **FR-024**: Un flujo activo MUST expirar tras 30 minutos de inactividad del usuario.
- **FR-025**: Al expirar un flujo por inactividad, el sistema MUST limpiar datos transitorios del flujo y conservar `customer_id`, `customer_name` y el vínculo negocio/canal.
- **FR-026**: La ventana WhatsApp de 24 horas MUST tratarse como restricción de envío de canal, no como timeout UX del flujo guiado.
- **FR-027**: El sistema MUST avoid duplicate critical actions when the same channel event/message is delivered more than once.
- **FR-028**: El sistema MUST revalidar disponibilidad inmediatamente antes de crear una cita confirmada.
- **FR-029**: El sistema MUST usar `America/Santo_Domingo` como timezone operativa por defecto para interpretación de fechas, disponibilidad y mensajes al usuario, salvo configuración futura por negocio.
- **FR-030**: El sistema MUST responder profesionalmente cuando falten servicios, horarios, ubicación o configuración de canal; no debe inventar datos.
- **FR-031**: El sistema MUST registrar logs mínimos de acciones críticas: canal, `business_id`, usuario/canal, acción, resultado y cita afectada cuando exista.
- **FR-032**: El sistema SHOULD tratar clientes de Telegram y WhatsApp como identidades separadas en fase 1, documentando la unificación cross-channel como mejora futura.
- **FR-033**: El sistema SHOULD dejar “hablar con una persona” fuera del menú principal de fase 1, pero registrarlo como backlog de producto.

### Key Entities *(include if feature involves data)*

- **MenuOption**: Acción numerada disponible en `idle`.
- **ConversationState**: Estado activo que decide si un número pertenece al menú global o al flujo actual.
- **NLUResult**: Interpretación auxiliar con intención y entidades, sin autoridad para mutar.
- **GuidedFlow**: Secuencia determinística manejada por handlers existentes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `hola` muestra menú sin llamada IA en WhatsApp y Telegram.
- **SC-002**: `1` en `idle` inicia agendamiento sin llamada IA.
- **SC-003**: `quiero cita mañana a las 10` no crea cita hasta confirmación explícita.
- **SC-004**: Mensajes ambiguos u ofensivos no disparan mutaciones.
- **SC-005**: Tests cubren que números dentro de flujos activos no abren menú global.
- **SC-006**: Las rutas determinísticas reducen llamadas IA para saludos/opciones/confirmaciones a cero.
- **SC-007**: Tests verifican que cuota IA agotada no bloquea `menu` ni opciones `1` a `5`, pero cuota total agotada sí bloquea.
- **SC-008**: Tests verifican `0/menu`, `9/volver` y `x/salir` desde al menos dos estados activos.
- **SC-009**: Tests verifican que un flujo activo con más de 30 minutos de inactividad vuelve a `idle` y no conserva `pending_data`.
- **SC-010**: Tests o validación manual verifican que un mensaje duplicado no duplica una cita confirmada.
- **SC-011**: Tests verifican que la confirmación revalida disponibilidad antes de crear la cita.
- **SC-012**: Tests verifican respuestas seguras para negocio sin servicios/horarios configurados.

## Assumptions

- El menú seguirá siendo texto numerado en fase 1.
- No se agregan botones interactivos como dependencia funcional.
- No se cambia el modelo de datos.
- La implementación partirá del estado actual descrito en `specs/000-project-baseline/`.
- El timeout recomendado para flujos activos es 30 minutos. El TTL global actual de contexto puede seguir existiendo, pero el cierre de flujo guiado debe ser explícito y testeado.
- La unificación de un mismo cliente entre WhatsApp y Telegram queda fuera de fase 1.
- El handoff humano queda como backlog, no como opción del menú principal en esta implementación.

## Implementation Notes

- Baja confianza de IA vuelve al menú guiado y no despacha handlers de mutación.
- Los atajos naturales desde `idle` pueden invocar IA para interpretar datos, pero el flujo conserva confirmación explícita; si una hora es ambigua, el sistema ofrece opciones antes de confirmar.
- La confirmación de reserva revalida disponibilidad justo antes de llamar `create_appointment`; si el horario ya fue tomado, vuelve a selección de horarios.
- WhatsApp y Telegram aplican guard defensivo por `message_id`/evento para ignorar reintentos duplicados dentro del proceso.
- Decisión MVP implementada: la idempotencia persistente usa PostgreSQL en Railway, no Redis, para evitar costo/operación adicional. La tabla `processed_channel_events` usa constraint único por `channel`, `business_id`, `user_key` y `event_id`.
- La interpretación relativa de fechas usa `America/Santo_Domingo` como timezone operacional por defecto.

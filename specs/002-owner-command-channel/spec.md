# Feature Specification: Canal De Comandos Del Dueño

**Feature Branch**: `002-owner-command-channel`  
**Created**: 2026-04-29  
**Status**: Draft  
**Input**: Crear un canal separado para que el dueño consulte agenda, métricas y futuras acciones administrativas del negocio.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Vincular Dueño A Su Canal Seguro (Priority: P1)

Como dueño autenticado, quiero vincular mi cuenta y mi negocio activo a Telegram desde el panel, para consultar información operativa sin mezclarme con el flujo de clientes.

**Why this priority**: Las funciones del dueño tienen más permisos que las del cliente; la identidad y autorización deben estar separadas desde el inicio.

**Independent Test**: Desde el panel, el dueño obtiene un enlace/código de activación para Telegram. Al abrirlo, el sistema vincula `owner_id`, `business_id`, `channel`, `channel_user_id` y marca el canal como activo.

**Acceptance Scenarios**:

1. **Given** un dueño con sesión web válida y un negocio activo, **When** genera enlace de canal del dueño, **Then** el enlace solo sirve para ese owner/business.
2. **Given** un usuario Telegram sin vínculo de dueño, **When** intenta usar comandos administrativos, **Then** el bot rechaza la operación y pide vinculación desde el panel.
3. **Given** un dueño vinculado, **When** envía `/start` o `menu`, **Then** recibe el menú del dueño para su negocio activo.
4. **Given** un cliente usa un enlace Telegram de reservas, **When** abre `/start <token_cliente>`, **Then** entra al flujo de cliente y no al canal del dueño.
5. **Given** un dueño usa enlace administrativo, **When** abre `/start owner_<token>`, **Then** entra al flujo de dueño y no al flujo de cliente.

---

### User Story 2 - Consultar Agenda Del Día (Priority: P1)

Como dueño, quiero consultar la agenda de hoy y mañana desde Telegram, para saber rápidamente qué citas tengo.

**Why this priority**: Es el valor operativo principal y reduce dependencia del panel web.

**Independent Test**: El dueño envía `1` o “agenda de hoy” y recibe una lista ordenada por hora con cliente, servicio y estado.

**Acceptance Scenarios**:

1. **Given** dueño vinculado, **When** selecciona `1) Agenda de hoy`, **Then** recibe citas de hoy en timezone `America/Santo_Domingo`.
2. **Given** dueño vinculado, **When** selecciona `2) Agenda de mañana`, **Then** recibe citas de mañana.
3. **Given** no hay citas para el día, **When** consulta agenda, **Then** recibe un mensaje claro indicando agenda vacía.

---

### User Story 3 - Consultar Métricas Del Día (Priority: P1)

Como dueño, quiero ver métricas de hoy, incluyendo ingresos estimados y realizados, para entender el desempeño del negocio.

**Why this priority**: Las métricas rápidas son útiles y seguras porque son solo lectura.

**Independent Test**: Con citas en estados `P`, `C`, `A`, `D`, el comando de métricas calcula conteos e ingresos correctamente.

**Acceptance Scenarios**:

1. **Given** citas de hoy, **When** el dueño selecciona `4) Métricas de hoy`, **Then** ve total, pendientes, confirmadas, completadas y canceladas.
2. **Given** servicios con precios, **When** calcula ingresos, **Then** `Ingresos estimados = P + C` e `Ingresos realizados = D`.
3. **Given** citas canceladas `A`, **When** calcula ingresos, **Then** las canceladas no suman ingresos.

---

### User Story 4 - Ver Detalle De Cita Sin Mutar (Priority: P2)

Como dueño, quiero seleccionar una cita de la agenda para ver detalle, sin ejecutar acciones administrativas todavía.

**Why this priority**: Permite navegación operativa segura antes de habilitar mutaciones.

**Independent Test**: Al responder con el número de una cita listada, el bot muestra cliente, servicio, hora, estado y opciones de navegación.

**Acceptance Scenarios**:

1. **Given** una agenda con citas numeradas, **When** el dueño envía `2`, **Then** ve detalle de la cita #2.
2. **Given** detalle de cita, **When** el dueño envía `9`, **Then** vuelve a la agenda anterior.

### Edge Cases

- Un dueño no vinculado no puede consultar agenda ni métricas.
- Un dueño vinculado solo puede consultar su negocio activo del MVP.
- Si existe más de un negocio por datos heredados, el canal del dueño debe bloquear configuración automática y pedir resolver desde panel/soporte.
- Si no hay negocio activo, el canal del dueño debe pedir crear/configurar un negocio desde el panel.
- Si faltan servicios o precios, las métricas deben tratar precios faltantes como `0` y mostrar resultado honesto.
- Si falla DB o consulta, responder con mensaje seguro y registrar error.
- Acciones administrativas mutables como cancelar, reagendar, bloquear horario o marcar completada quedan fuera de fase 1 del canal del dueño.

## MVP Business Policy

Durante el MVP, cada owner opera **un solo negocio activo**. Multi-negocio queda fuera del MVP y solo debe habilitarse con planes de pago, límites comerciales y controles de abuso.

Reglas:

- El backend no debe permitir crear más de un negocio activo por owner en MVP.
- El frontend no debe mostrar selector multi-negocio ni botón “Nuevo negocio” si el owner ya tiene un negocio.
- El canal del dueño no debe pedir elegir negocio; opera el único negocio activo.
- Si el sistema detecta múltiples negocios heredados para un owner, debe bloquear creación de binding del dueño y mostrar estado “requiere soporte” en vez de elegir uno automáticamente.

## Owner Menu

Menú MVP recomendado:

```text
Panel rápido - {business_name}

1) Agenda de hoy
2) Agenda de mañana
3) Próximas citas
4) Métricas de hoy
5) Notificaciones

9) Volver
0) Menú principal
X) Salir
```

Notas:

- `5) Notificaciones` en fase 1 puede mostrar estado de notificaciones, no editar configuración avanzada.
- Buscar citas/clientes, bloquear horarios y mutaciones administrativas quedan para fase 2.

## Metrics Definition

Estados actuales:

- `P`: Pending / Pendiente
- `C`: Confirmed / Confirmada
- `A`: Canceled / Cancelada
- `D`: Done / Completada

Métricas de hoy:

- Citas totales: `P + C + A + D`
- Pendientes: `P`
- Confirmadas: `C`
- Completadas: `D`
- Canceladas: `A`
- Ingresos estimados: suma de precios de citas `P + C`
- Ingresos realizados: suma de precios de citas `D`

Canceladas no suman ingresos.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema MUST crear un canal de dueño separado del canal de clientes.
- **FR-002**: El canal inicial del dueño SHOULD ser Telegram para MVP.
- **FR-003**: El dueño MUST vincular el canal desde una sesión autenticada del panel web.
- **FR-004**: El vínculo MUST asociar `owner_id`, `business_id`, `channel`, `channel_user_id`, estado activo y timestamps.
- **FR-005**: El canal del dueño MUST operar solo el negocio activo único del owner durante MVP.
- **FR-006**: El backend MUST impedir o rechazar creación de múltiples negocios activos por owner durante MVP.
- **FR-007**: El frontend MUST ocultar/deshabilitar el flujo de “Nuevo negocio” cuando el owner ya tenga un negocio en MVP.
- **FR-008**: El frontend MUST ocultar selector de negocios múltiples para MVP y tratar multi-negocio como funcionalidad futura.
- **FR-009**: El dueño MUST poder consultar agenda de hoy, agenda de mañana, próximas citas y métricas de hoy.
- **FR-010**: El dueño MUST poder ver detalle de una cita desde una lista numerada sin mutar la cita en fase 1.
- **FR-011**: Métricas MUST calcular ingresos estimados como suma de citas `P + C` e ingresos realizados como suma de citas `D`.
- **FR-012**: El sistema MUST usar `America/Santo_Domingo` para ventanas de día del canal del dueño en MVP.
- **FR-013**: Acciones mutables administrativas MUST requerir nueva spec/fase o estar marcadas como fase 2 con confirmación explícita.
- **FR-014**: El sistema MUST registrar logs mínimos de consultas administrativas y errores del canal del dueño.
- **FR-015**: El canal del dueño MUST soportar navegación `0) Menú principal`, `9) Volver`, `X) Salir` y timeout de 30 minutos.
- **FR-016**: Los tokens/enlaces de activación del dueño MUST tener prefijo o tipo explícito distinto de los enlaces de cliente, por ejemplo `/start owner_<token>`.
- **FR-017**: El webhook Telegram MUST resolver primero el tipo de payload (`owner_` vs cliente) antes de crear bindings.
- **FR-018**: Un `channel_user_id` Telegram activo como dueño MUST NOT poder vincularse simultáneamente como cliente del mismo negocio sin confirmación futura explícita.
- **FR-019**: Si un owner tiene múltiples negocios heredados, el endpoint de activación del dueño MUST rechazar la activación y pedir resolver la cuenta antes de usar el canal.

### Key Entities *(include if feature involves data)*

- **OwnerChannelBinding**: Vínculo seguro entre owner, negocio activo y usuario/canal externo.
- **OwnerCommandSession**: Estado conversacional administrativo, separado del estado de clientes.
- **OwnerDailyMetrics**: Agregación calculada de citas e ingresos del día.
- **OwnerAgendaItem**: Vista numerada de cita para agenda operativa.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un owner vinculado puede recibir agenda de hoy en menos de 5 segundos con datos existentes.
- **SC-002**: Un owner no vinculado no puede consultar datos del negocio.
- **SC-003**: El frontend no permite crear un segundo negocio en MVP desde el botón “Nuevo negocio”.
- **SC-004**: El backend rechaza o bloquea creación de segundo negocio activo para el mismo owner en MVP.
- **SC-005**: Métricas de ingresos calculan correctamente `P + C` como estimado y `D` como realizado.
- **SC-006**: Tests cubren separación entre canal cliente y canal dueño.
- **SC-007**: Tests verifican que `/start owner_<token>` crea binding de dueño y `/start <token_cliente>` conserva binding de cliente.
- **SC-008**: Tests verifican que owners con múltiples negocios heredados no reciben un binding automático.

## Assumptions

- MVP limita cada owner a un negocio activo.
- Multi-negocio se habilitará solo cuando existan planes de pago y límites comerciales.
- Fase 1 del canal del dueño es principalmente de lectura.
- Telegram será el canal inicial de comandos del dueño.
- El panel web sigue siendo la herramienta principal para configuración avanzada.

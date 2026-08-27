# SmartBooking AI — MASTER SPEC (Bloque 1 + 2)

MODE: SPEC-DRIVEN REFINEMENT  
SOURCE OF TRUTH: EXISTING CODE + THIS SPEC  
IMPORTANT: DO NOT CONTRADICT EXISTING CODE WITHOUT JUSTIFICATION  

---

# BLOQUE 1 — CLIENT_CHANNEL

STATUS: CLOSED

---

## STATES

- idle
- awaiting_name
- awaiting_email_optional
- main_menu
- booking_service
- booking_location
- booking_day
- booking_month
- booking_week
- booking_time
- booking_confirmation
- viewing_appointments
- modifying_appointment
- cancelling_appointment
- viewing_locations
- guardrail_redirect
- exit

---

## MENUS

### MAIN_MENU

1. Agendar una cita  
2. Ver mis citas  
3. Cambiar una cita  
4. Cancelar una cita  
5. Horarios y ubicación  
X. Salir  

---

### NAVIGATION

0 → Menú principal  
9 → Volver  
X → Salir  

---

## FLOWS

### BOOKING_FLOW

STEP 1: SELECT_SERVICE  
STEP 2: SELECT_LOCATION  
STEP 3: SELECT_DAY_OR_FUTURE  
STEP 4: SELECT_TIME  
STEP 5: CONFIRM  

---

### SELECT_SERVICE

INPUT: service_id  

RULES:
- service must exist
- service must be active

---

### SELECT_LOCATION

INPUT: location_id  

RULES:
- location must exist
- location must support selected service

---

### SELECT_DAY_OR_FUTURE

LOGIC:

IF current_week:
- show remaining days of current week
- show only days with availability

ADD OPTION:
8 → "Buscar otro mes"

---

### FUTURE_BOOKING_FLOW

STEP 1: SELECT_MONTH  
STEP 2: SELECT_WEEK  
STEP 3: SELECT_DAY  

---

### SELECT_MONTH

RULES:
- exclude current month
- include only future months
- limit by business.plan.max_months

---

### SELECT_WEEK

RULES:
- divide month into weeks
- show only weeks with available days

---

### SELECT_DAY

RULES:
- show only days with availability

---

### SELECT_TIME

LOGIC:
- generate slots based on service.duration + buffer
- apply filtering (appointments, blocks, schedules)
- apply pagination

NAVIGATION:
7 → previous page  
8 → next page  

---

### CONFIRMATION

INPUT:
- service_id
- location_id
- datetime

ACTION:
- validate
- persist appointment

---

### VIEW_APPOINTMENTS

OUTPUT:
- list of appointments

---

### MODIFY_FLOW

STEP:
- select appointment
- select new date
- select new time
- confirm

---

### CANCEL_FLOW

STEP:
- select appointment
- confirm cancellation

---

## RULES

- Menu-driven system (no free text required)
- Always return to main menu after action
- Slots are NOT reserved until confirmation
- Only show valid options to user
- Avoid empty states

---

## VALIDATIONS

BEFORE SHOWING SLOTS:
- within schedule
- not blocked
- service active

BEFORE CONFIRMATION:
- slot still available
- not blocked
- valid datetime
- location supports service

---

## GUARDRAILS

IF input invalid OR obscene:

ACTION:
- redirect to main_menu

MESSAGE:
"Este sistema solo gestiona citas."

---

## REMINDERS

- Immediate confirmation
- Email → 24h before
- WhatsApp → 2h before

---

## DATA DEPENDENCIES

- Business
- Location
- Service
- Schedule
- Appointment
- Customer

---

## STRUCTURE

Business
 └─ Locations
      ├─ Services
      └─ Schedules

---

# BLOQUE 2 — OWNER_CHANNEL

STATUS: CLOSED

---

## STATES

- onboarding
- dashboard
- appointments_view
- services_management
- schedules_management
- locations_management
- customers_view
- settings
- telegram_panel

---

## ONBOARDING

MODE: Hybrid (Web + Telegram)

REQUIRED:
- business_name
- business_type
- email
- whatsapp
- initial_location
- schedules
- services

---

## TELEGRAM_PANEL

### MENU

1. Agenda de hoy  
2. Próximas citas  
3. Bloquear horario  
4. Métricas  
X. Salir  

---

### AGENDA_TODAY

- list appointments

ACTIONS:
- cancel
- reschedule
- mark_completed

---

### UPCOMING

- next 7 days appointments

---

### BLOCK_SCHEDULE

OPTIONS:
- full_day
- partial_day
- custom_range

RULE:
block overrides schedule

---

### METRICS

- citas hoy
- próximas citas
- cancelaciones
- servicio más reservado
- ingresos estimados

---

## WEB_PANEL

MODULES:

- Dashboard
- Appointments
- Services
- Schedules
- Locations
- Customers
- Settings

---

### DASHBOARD

- cards + simple charts

---

### APPOINTMENTS

VIEWS:
- calendar
- list

ACTIONS:
- cancel
- reschedule
- complete

---

### SERVICES

FIELDS:
- name
- duration
- price
- buffer
- active
- order

RULES:
- inactive services not visible to client

---

### SCHEDULES

- weekly schedules
- exceptions
- manual blocks

PRIORITY:
blocks > exceptions > schedules

---

### LOCATIONS

FIELDS:
- name
- address
- phone
- active

RULES:
- soft delete only
- limited by plan

---

### CUSTOMERS

FIELDS:
- name
- phone
- email
- last_appointment
- total_appointments

---

### SETTINGS

- business info
- branding
- reminders
- timezone

---

## BUSINESS RULES

### SLOT_GENERATION

- based on service.duration + buffer

---

### CONFLICTS

- strict blocking
- no overlapping allowed

---

### VALIDATION

- slot available
- within schedule
- not blocked
- service active

---

### SLOT_CONFLICT_RUNTIME

IF slot taken during confirmation:

ACTION:
- reject
- recalculate
- show alternatives

---

## AVAILABILITY

### CURRENT_WEEK

- show remaining days only
- only days with availability

---

### FUTURE_BOOKING

FLOW:
month → week → day → time

RULES:
- limited by plan.max_months
- dynamic loading (no full preload)

---

### SLOT_ENGINE

- generate → filter → paginate

---

## MULTI-TENANT

MODEL:
- shared database
- isolation by business_id

RULE:
ALL queries MUST filter by business_id

---

## AUTHENTICATION

- web: email + password
- telegram: linked via token

---

## TOKEN

- unique per business
- used for:
  - client access
  - telegram linking

---

## PLANS

- basic
- pro
- premium

---

## PLAN LIMITS

- max_locations
- max_months
- feature flags

---

## ENFORCEMENT

- backend enforced only
- no UI-only restrictions

---

## METRICS

- citas hoy
- próximas citas
- cancelaciones
- top servicio
- ingresos estimados

---

## REPORTS

- view only
- no export (MVP)

---

## DATA DEPENDENCIES

- Business
- Location
- Service
- Schedule
- Appointment
- Customer
- Plan

---

## CRITICAL RULES

- No cross-business data access
- No booking without validation
- No slot without availability check
- No schedule override without block priority

---


# BLOQUE 3 — CONVERSATIONAL_ARCHITECTURE

STATUS: CLOSED

---

## ORCHESTRATOR

### Tipo
- Orchestrator híbrido controlado

### Responsabilidades
- Cargar contexto:
  - `business_id`
  - `user_id`
  - `session`
  - `current_state`
  - contexto parcial
- Resolver estado actual
- Aplicar guardrails globales
- Normalizar input
- Activar IA (condicional)
- Delegar al Router
- Manejar errores globales
- Construir respuesta final (formato)
- Persistir estado y contexto
- Logging estructurado

### Restricciones
- No contiene lógica de negocio
- No ejecuta validaciones de dominio
- No define menús

### Pipeline

```python
1. Context Loader
2. State Resolver
3. Guardrails Layer
4. Input Normalizer
5. IA Layer (condicional)
6. State Validation
7. Router Dispatch
8. Handler Execution
9. Response Builder
10. State Persistence
11. Logging


Manejo de errores
Globales: Orchestrator
Negocio: Handlers
Logging
request_id
business_id
user_id
current_state → next_state
input
handler
execution_time
result
error_type
STATE_MACHINE
Tipo
Enum + transiciones validadas
Estados
MAIN_MENU
SELECT_SERVICE
SELECT_LOCATION
SELECT_DAY
SELECT_TIME
CONFIRM_BOOKING
EXIT
FALLBACK
Estado inicial
MAIN_MENU
Transiciones
Definidas en mapa central
Handlers proponen next_state
Orchestrator valida antes de persistir
Navegación global
0 → MAIN_MENU
9 → BACK (stack)
X → EXIT
Back
Uso de state_stack
Push en transición
Pop en 9
Expiración de sesión
Timeout configurable
Al expirar:
limpiar contexto parcial
mantener logs
redirigir a MAIN_MENU
ROUTER
Tipo
Clase desacoplada
Responsabilidad
Resolver handler según current_state
Registro
Central explícito
HANDLER_REGISTRY = {
  MAIN_MENU: MainMenuHandler,
  SELECT_SERVICE: SelectServiceHandler,
  SELECT_LOCATION: SelectLocationHandler,
  SELECT_DAY: SelectDayHandler,
  SELECT_TIME: SelectTimeHandler,
  CONFIRM_BOOKING: ConfirmBookingHandler
}
Resolución
Uso de factory
handler = handler_factory.create(handler_class)
Validación
No valida estado
Asume estado válido
Fallback
Si no existe handler:
retorna FallbackHandler
HANDLERS
Tipo
Clases obligatorias
Contrato
class BaseHandler:
    def handle(self, context, input):
        raise NotImplementedError
Relación
1 STATE → 1 HANDLER
Ejecución
handle()
  → validate()
  → process()
  → build_response()
  → return HandlerResult
Resultado
class HandlerResult:
    next_state: StateEnum
    message: str
    context_updates: dict
    metadata: dict
Contexto
No mutación directa
Retorna context_updates
Validaciones
Dentro del handler
Uso de services/repos
Errores
Retorno controlado
No uso de excepciones para flujo normal
Respuesta
Handler define contenido
Orchestrator aplica formato
GUARDRAILS
Rol IA
Soporte limitado
No controla flujo
Activación
Input no coincide con menú
Input ambiguo
Texto libre
Capacidades
Interpretar intención
Extraer entidades
Sugerir acción
Restricciones
No respuestas libres
No inventar datos
No modificar estados directamente
No ejecutar lógica de negocio
No saltar flujo
Validación IA
Validación estricta:
estado actual
transición válida
datos correctos
Fallback
Volver a menú guiado
EXECUTION_FLOW
Pipeline completo
1. Receive Input
2. Load Context
3. Guardrails
4. Input Normalization
5. IA (condicional)
6. State Validation
7. Router
8. Handler Execution
9. Response Builder
10. State Persistence
11. Logging
IA Flow
Input inválido
  → IA
  → Suggestion
  → Validation
    → OK → Handler
    → Fail → Menu fallback
Concurrencia
Cola por usuario
Procesamiento secuencial
Idempotencia
Basada en message_id
Previene duplicación
STATES
Persistidos en DB
Definidos por enum
Transiciones controladas
No estados dinámicos
FLOWS
Flujo principal
MAIN_MENU
  → SELECT_SERVICE
  → SELECT_LOCATION
  → SELECT_DAY
  → SELECT_TIME
  → CONFIRM_BOOKING
  → MAIN_MENU
Flujo alterno
SELECT_DAY
  → SEARCH_OTHER_MONTH
  → SELECT_WEEK
  → SELECT_DAY
MENUS
Definidos por handlers
Formateados por Orchestrator
Navegación global inyectada
RULES
Sistema menu-first
IA como soporte
Backend stateless
Estado persistido
Multi-tenant obligatorio (business_id)
Pipeline obligatorio
No ejecución directa fuera de Orchestrator
VALIDATIONS
Globales
input vacío
input inválido
estado inválido
sesión inválida
State Machine
transición válida
estado válido
Handler
validación de dominio
disponibilidad
reglas de negocio
IA
validación estructural
validación de transición
DATA DEPENDENCIES
Entrada
webhook payload
message_id
user_id
business_id
input
Session Store
{
  "user_id": "...",
  "business_id": "...",
  "current_state": "...",
  "state_stack": [],
  "context": {}
}
Context
{
  "selected_service": null,
  "selected_location": null,
  "selected_day": null,
  "selected_time": null,
  "last_interaction_at": "...",
  "attempts": {},
  "flags": {}
}
Idempotencia
message_id
response_cache
Logging
request_id
message_id
business_id
user_id
state transition
handler
execution_time
result
error_type

# BLOQUE 4 — SCHEDULING_ENGINESTATUS: CLOSED---## STATES- SLOT_BUILDING- SLOTS_READY- AVAILABILITY_CHECK- AVAILABILITY_FOUND- NO_AVAILABILITY- SLOT_SELECTED- PRE_BOOKING_VALIDATION- BOOKING_CONFIRMED- BOOKING_REJECTED---## FLOWS### SLOT GENERATION
working_hours → generate_slots → evaluate_conflicts → filter_available → paginate → return
### AVAILABILITY CHECK
request_day → generate_slots → filter_available → return_result
### NO AVAILABILITY
selected_day → no_slots → search_next_available_days → show_options
### NEXT AVAILABLE SEARCH
start_day + 1 → check_day → has_slots → collect → stop_at_3_or_limit
### BOOKING FLOW
select_slot → PRE_BOOKING_VALIDATION → create_appointment → BOOKING_CONFIRMED
### CONFLICT FLOW
slot_selected → validate_again → conflict_detected → reject → suggest_alternatives
### CANCELLATION FLOW
cancel_appointment → update_status(cancelled) → invalidate_cache(date) → slot_available
---## RULES- Multi-tenant isolation por `business_id`- Slot_length = `service.duration + buffer`- Buffer configurable por servicio o fallback a ubicación- Slots generados desde `working_hours.start`- Incremento por `slot_length`- No solapamiento entre slots- Slots deben estar completamente dentro de horario laboral- Primer slot del día:  - `today`: `max(now, working_hours.start)`  - futuro: `working_hours.start`- Redondeo basado en secuencia de slots, no en hora actual directa- Slots no disponibles no se muestran al cliente- Slots no se persisten en DB- Fuente de verdad:  - appointments  - blocks  - working_hours  - service_config- Prioridad de disponibilidad:  - blocks > appointments > working_hours- Detección de conflicto:  - `slot.start < event.end AND slot.end > event.start`- Buffer forma parte del slot y bloquea disponibilidad- No generar slots parciales ni recortados- Timezone basado en `location.timezone`- Orden de slots cronológico ascendente- Generación híbrida:  - base_slots opcional  - validación en tiempo real obligatoria- Generación bajo demanda por día- Mostrar solo días con disponibilidad real- Búsqueda de alternativas limitada a 3 días- Rango de búsqueda limitado por `booking_advance_months`- Navegación:  - semana actual → semanas → meses- No mostrar días pasados- No mostrar semanas sin disponibilidad- Cache en DB por día- Cache invalidado por eventos:  - appointment_created  - appointment_cancelled  - block_created  - block_removed  - working_hours_updated  - service_updated- TTL de respaldo para cache- Validación final obligatoria antes de persistir- No confiar en cache ni estado previo- Transacción obligatoria en creación de cita- Isolation level: REPEATABLE READ- Constraint en DB para evitar doble booking- Si conflicto en confirmación:  - rechazar  - recalcular  - sugerir alternativas- Bloqueos tienen prioridad absoluta incluso durante flujo activo- Límites por usuario configurables:  - día  - semana  - mes- Solo cuentan citas:  - pending  - confirmed- Separación mínima entre citas del usuario configurable- Cancelación libera slot inmediatamente- Penalización por cancelación tardía configurable---## VALIDATIONS- `duration > 0`- `buffer >= 0`- `slot_length <= jornada`- `slot.start >= now`- `slot.end <= working_hours.end`- `slot.start < slot.end`- No slots en el pasado- No slots fuera de rango permitido- No slots parciales- No solapamiento con:  - blocks  - appointments- Validación doble:  - antes de mostrar  - antes de confirmar- Validación final incluye:  - conflictos  - horario  - rango- Rechazar si slot ya no disponible- Rechazar si usuario supera límites- Rechazar si no cumple separación mínima- No usar cache para confirmación- No mostrar días sin disponibilidad- No sugerir días fuera de rango- No duplicar días en sugerencias- No mostrar páginas vacías- No permitir navegación inválida---## DATA DEPENDENCIES- business_id- location_id- service_id- user_id- service.duration- service.buffer- location.buffer- working_hours.start- working_hours.end- location.timezone- appointments:  - start_time  - end_time  - status- blocks:  - start_time  - end_time- booking_advance_months- availability_cache_table:  - available_slots_count  - available_slots_preview  - generated_at  - expires_at- booking_limits_config:  - max_per_day  - max_per_week  - max_per_month- min_time_between_user_bookings- late_cancellation_window_minutes- late_cancellation_penalty_type---## SLOT_GENERATION_ENGINE- Generación basada en `slot_length`- Iteración desde `working_hours.start`- Incremento fijo por slot_length- Evaluación de conflictos por slot- Filtrado de slots disponibles- Orden cronológico- Salida paginada---## AVAILABILITY_ENGINE- Cálculo bajo demanda por día- No precálculo masivo- Cache por día en DB- Búsqueda de días disponibles hasta 3 resultados- Sugerencias ordenadas por cercanía---## SCHEDULE_MERGING- Merge lógico entre:  - working_hours  - blocks  - appointments- Resultado:  - disponibilidad final por slot- Prioridad aplicada:  - blocks > appointments > working_hours---## BUFFER_HANDLING- Buffer incluido en slot_length- Buffer bloquea tiempo real- No permitir citas dentro del buffer de otra- No permitir solapamiento parcial con buffer---## BLOCKS_HANDLING- Bloqueos invalidan completamente slots- Aplicación en:  - generación  - validación- Bloqueos tienen prioridad absoluta- Bloqueos afectan flujos activos---## CONFLICT_RESOLUTION- Validación final antes de persistir- Transacción obligatoria- Isolation: REPEATABLE READ- Constraint para evitar doble booking- Rechazo en conflicto- Sugerencias alternativas obligatorias---## PAGINATION- Tamaño configurable (`slots_page_size`)- Navegación:  - 7 (prev)  - 8 (next)- No páginas vacías- Orden cronológico- Solo slots disponibles---## FUTURE_BOOKING- Rango limitado por `booking_advance_months`- Flujo:  - semana actual → semanas → meses- No permitir fechas pasadas- No permitir fuera de rango---## PERFORMANCE_CONSIDERATIONS- Cálculo bajo demanda- Cache por día en DB- Invalidation por eventos- TTL de respaldo- No persistir slots- Preparado para migración a Redis---## ERROR_HANDLING- Slot no disponible:  - mensaje + alternativas- Día sin disponibilidad:  - sugerencias de días cercanos- Límite alcanzado:  - rechazo controlado- Conflicto en confirmación:  - rechazo + recalcular- Bloqueo inesperado:  - rechazo + alternativas- Cancelación tardía:  - aplicar penalización- Navegación inválida:  - ignorar / fallback

Necesito que tomes TODO lo que hemos definido en este chat sobre el BLOQUE 5 (SaaS / Billing) y BLOQUE 6 (Seguridad avanzada) y lo conviertas en un documento en formato Markdown (.md) siguiendo exactamente estas reglas:

OBJETIVO:
Generar un SPEC técnico puro, listo para copiar y pegar en un solo bloque y usar como contexto para Codex / Claude Code.

IMPORTANTE:
- NO resumir
- NO omitir información
- NO cambiar decisiones tomadas
- NO rediseñar nada
- NO explicar
- NO agregar texto narrativo
- TODO debe estar en un solo bloque continuo listo para copiar

FORMATO OBLIGATORIO:

# BLOQUE 5 + 6 — SAAS_BILLING_AND_SECURITY

STATUS: CLOSED

Luego usar exactamente estas secciones:

## STATES
## FLOWS
## RULES
## VALIDATIONS
## DATA DEPENDENCIES

Y DEBE INCLUIR (si aplica):

## PLAN_MODEL
## FEATURE_GATING
## LIMIT_ENFORCEMENT
## SUBSCRIPTION_LIFECYCLE
## PRICING_STRUCTURE
## AUTHENTICATION
## AUTHORIZATION
## TOKEN_MODEL
## TELEGRAM_SECURITY
## RATE_LIMITING
## ABUSE_PREVENTION
## DATA_ISOLATION
## AUDIT_LOGS
## FAILSAFE_MECHANISMS

REGLAS DE FORMATO:

- TODO el resultado debe estar dentro de UN SOLO BLOQUE DE CÓDIGO Markdown
- No dividir en partes
- No usar explicaciones fuera del bloque
- Estilo técnico, directo
- Sin opiniones
- Sin A/B/C
- Solo decisiones finales
- Consistente con bloques 1, 2, 3 y 4

CONTEXTO IMPORTANTE (NO CAMBIAR):

- Multi-tenant por business_id
- Token único por negocio
- Web + Telegram como canales
- Backend valida todas las restricciones
- No implementar pagos aún (solo estructura SaaS)
- Planes definidos: basic, pro, premium
- Restricciones:
  - max_locations
  - max_months
  - feature flags
- Enforcement en backend (no UI)
- Aislamiento total por business_id
- No acceso cruzado entre negocios
- Sistema menu-driven
- Seguridad compatible con orchestrator + router

SEGURIDAD:

- Email + password para web
- Telegram vinculado por token
- Validación de acciones críticas
- Protección contra spam y abuso
- Rate limiting
- Validación de requests

SAAS:

- Plan asignado a business
- Feature gating activo
- Límites duros (hard limits)
- Preparado para futura integración con Stripe
- Upgrade/downgrade estructurado (sin implementación de pagos)

# BLOQUE 7 + 8 — UX_BRANDING_AND_SCALABILITY

STATUS: CLOSED

---

## STATES

- STATE_WELCOME
- STATE_MENU_MAIN
- STATE_SERVICE_SELECTION
- STATE_LOCATION_SELECTION
- STATE_DAY_SELECTION
- STATE_TIME_SELECTION
- STATE_CONFIRMATION
- STATE_POST_CONFIRMATION
- STATE_ERROR
- STATE_INVALID_INPUT
- STATE_NO_AVAILABILITY
- STATE_GUARDRAIL_REDIRECT
- STATE_ONBOARDING_NAME_CAPTURE
- STATE_SESSION_RESUME_PROMPT

---

## FLOWS

### CLIENT_FLOW
Service → Location → Day → Time → Confirm

### ONBOARDING_FLOW
- First interaction:
  - Show welcome + branding + menu
  - Proceed with normal flow
  - Before confirmation:
    - IF user.name == null → request name
    - ELSE → continue

### SESSION_RESUME_FLOW
- IF session expired:
  - Ask user:
    - Continue previous flow
    - Restart flow

### INVALID_INPUT_FLOW
- On invalid input:
  - Show friendly error
  - Repeat options
- After 3 invalid attempts:
  - Offer help or reset to main menu

### NO_AVAILABILITY_FLOW
- IF no slots in current view:
  - Show message
  - Provide option: "Ver otra semana/mes"

### CANCELLATION_FLOW
- Confirm cancellation
- Offer rebooking

### GUARDRAIL_FLOW
- On out-of-scope input:
  - Redirect to main flow
- On inappropriate input:
  - Soft warning + redirect

---

## RULES

- Messaging tone:
  - Cercano, claro y profesional
- Emojis:
  - Uso moderado (máx. 1 por mensaje clave)
- Message length:
  - Corto (1–2 líneas)
- Personalization:
  - Nombre solo en mensajes clave
- Confirmations:
  - Deben incluir:
    - Servicio
    - Ubicación
    - Fecha
    - Hora
    - Nombre del cliente
- Error handling:
  - Empático + solución inmediata
- Suggestions:
  - Solo sugerencias simples (MVP)
- Guardrails:
  - No NLP libre
  - Redirección al flujo
- Bot identity:
  - Asistente del negocio (multi-tenant branding)
- Language:
  - Configurable por tenant (usted / tú)
- Menu system:
  - Menu-first obligatorio
- Navigation:
  - Opción “Volver” en cada paso
  - Comando “Menú principal”
- Session timeout:
  - 15–30 minutos
- State persistence:
  - Preguntar continuar o reiniciar
- Input control:
  - Sin inputs libres innecesarios

---

## VALIDATIONS

- Input validation:
  - Solo opciones válidas del menú
- Retry limit:
  - Máx. 3 intentos inválidos
- Name capture:
  - Requerido antes de confirmar cita
- Session validation:
  - Validar timeout antes de continuar
- Availability validation:
  - No mostrar slots inválidos
- Guardrail validation:
  - Detectar contenido fuera de contexto
  - Detectar contenido inapropiado

---

## DATA DEPENDENCIES

- user_profile:
  - id
  - name
- business_config:
  - name
  - tone
  - greeting
- booking_data:
  - service_id
  - location_id
  - date
  - time
- session:
  - state
  - last_activity
- messaging_config:
  - templates
  - language_mode
- feature_flags:
  - premium_features
- availability_data:
  - slots
  - schedule

---

## MESSAGING_SYSTEM

- Sistema basado en plantillas
- Mensajes cortos y consistentes
- Branding por negocio incluido en mensajes
- Uso de emojis controlado
- Mensajes estructurados por contexto

---

## UX_TONE

- Cercano
- Claro
- Profesional
- No técnico
- No informal excesivo

---

## MESSAGE_TEMPLATES

### WELCOME
- Saludo + branding + instrucción + menú

### CONFIRMATION
- Confirmación + resumen completo
- Incluye:
  - Servicio
  - Ubicación
  - Fecha
  - Hora
  - Nombre

### POST_CONFIRMATION
- Confirmación + mensaje corto adicional

### ERROR
- Mensaje empático + solución

### INVALID_INPUT
- Mensaje + repetición de opciones

### NO_AVAILABILITY
- Mensaje + opción de navegación

### CANCELLATION
- Confirmación + opción de reagendar

### REMINDERS
- 24h antes → Email
- 2h antes → WhatsApp

---

## ERROR_HANDLING

- Mensajes amigables
- Sin errores técnicos visibles
- Repetición de opciones
- Escalamiento controlado tras múltiples errores

---

## MENU_CONSISTENCY

- Menú híbrido:
  - Botones + fallback texto
- Máx. 4 niveles de profundidad
- Navegación consistente:
  - Volver
  - Menú principal
- Opciones siempre visibles

---

## ONBOARDING_UX

- Menú primero
- Captura de nombre posterior
- Nombre persistente
- No solicitar nombre nuevamente si existe

---

## GUARDRAILS_MESSAGES

- Fuera de contexto:
  - Redirección al flujo principal
- Inapropiado:
  - Advertencia suave + redirección
- Sin respuestas abiertas

---

## CHANNEL_EXPERIENCE

### WhatsApp
- Mensajes cortos
- Uso de botones cuando sea posible
- Fallback a texto numerado

### Telegram
- Similar estructura
- Soporte para comandos

---

## MVP_FEATURES

- WhatsApp booking
- Agenda básica
- 1 ubicación
- Recordatorios automáticos
- CRM básico (historial)
- Google Calendar (feature premium opcional lectura)
- Menú guiado completo
- Confirmaciones
- Cancelaciones
- Reagendamiento

---

## POST_MVP_FEATURES

- Pagos (Stripe u otros)
- Web booking
- Integración Instagram
- CRM avanzado
- Automatizaciones extendidas
- Configuración avanzada de recordatorios

---

## PREMIUM_FEATURES

- Google Calendar
- Integraciones externas
- Multi-ubicación avanzada
- Automatizaciones adicionales
- Soporte prioritario

---

## GROWTH_STRATEGY

- Feature-based plans
- Escalabilidad por tenant
- Validación MVP primero
- Expansión progresiva

---

## INTEGRATIONS_FUTURE

- Stripe
- Google Calendar (full sync)
- Instagram DM
- Web booking
- CRM externo

---

## PERFORMANCE_OPTIMIZATION

- Caching selectivo:
  - slots
  - servicios
  - configuración
- Uso de colas:
  - recordatorios
  - emails
  - tareas pesadas

---

## MODULARIZATION

- Modular monolith
- Componentes desacoplados:
  - messaging
  - scheduling
  - auth
  - billing
- Reutilización entre productos SaaS

---

## SCALABILITY_STRATEGY

- Multi-tenant architecture
- Feature flags para evolución
- No microservicios en MVP
- Preparado para expansión sin rediseño
- Separación clara entre:
  - lógica de negocio
  - UX
  - comunicación
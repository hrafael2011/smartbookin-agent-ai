# Feature Specification: Project Baseline

**Feature Branch**: `000-project-baseline`  
**Created**: 2026-04-29  
**Status**: Baseline  
**Input**: Consolidar el estado real de SmartBooking AI para que futuras specs no dependan de documentación histórica contradictoria.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Entender El Producto Actual (Priority: P1)

Un desarrollador o agente nuevo puede leer la baseline y entender qué problema resuelve SmartBooking AI, quiénes lo usan y cuáles módulos existen.

**Why this priority**: Sin una baseline confiable, cada cambio futuro reinterpreta el proyecto desde código suelto o documentos viejos.

**Independent Test**: Una persona nueva puede explicar el producto, canales, stack y flujos principales sin abrir más de tres archivos.

**Acceptance Scenarios**:

1. **Given** una persona nueva en el repo, **When** lee esta spec, **Then** entiende que SmartBooking AI agenda citas para negocios usando panel web, WhatsApp y Telegram.
2. **Given** documentos históricos que mencionan Django, **When** se consulta la baseline, **Then** queda claro que el backend vigente es FastAPI + SQLAlchemy.

---

### User Story 2 - Ubicar La Arquitectura Vigente (Priority: P2)

Un desarrollador puede identificar los límites principales: backend API, frontend admin, canales conversacionales, base de datos, scheduler y servicios externos.

**Why this priority**: Las decisiones nuevas deben respetar límites existentes en vez de duplicar lógica por canal o módulo.

**Independent Test**: El desarrollador puede ubicar los entrypoints relevantes y describir el flujo de una cita desde canal conversacional hasta persistencia.

**Acceptance Scenarios**:

1. **Given** una pregunta sobre webhooks, **When** se revisa la baseline, **Then** se identifica `backend/api-backend/main.py` como entrypoint HTTP principal.
2. **Given** una pregunta sobre UI admin, **When** se revisa la baseline, **Then** se identifica React/Vite como frontend en `frontend/`.

---

### User Story 3 - Tener Una Ruta Local De Operación (Priority: P3)

Un desarrollador puede levantar o validar el proyecto localmente con Docker Compose y conocer los puertos principales.

**Why this priority**: La documentación de implementación debe ser verificable, no solo descriptiva.

**Independent Test**: Con `.env` configurado, Docker Compose debe levantar backend, PostgreSQL, frontend build y Nginx.

**Acceptance Scenarios**:

1. **Given** Docker instalado y variables configuradas, **When** se ejecuta Docker Compose, **Then** el backend queda disponible detrás de Nginx y la API responde.
2. **Given** ngrok configurado, **When** se activa el perfil opcional, **Then** puede exponerse el stack local para webhooks.

### Edge Cases

- Documentos históricos pueden estar desactualizados; esta baseline tiene prioridad sobre `PROJECT_SUMMARY.txt` cuando haya contradicciones.
- El README raíz antiguo menciona “Django API”; eso debe tratarse como rastro histórico mientras no se actualice por completo.
- La disponibilidad real de WhatsApp, Telegram, OpenAI y SMTP depende de `.env`.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: La documentación MUST declarar que el backend vigente es `backend/api-backend` con FastAPI, SQLAlchemy async y Alembic.
- **FR-002**: La documentación MUST declarar que el frontend vigente es React + Vite + TypeScript en `frontend/`.
- **FR-003**: La documentación MUST declarar que PostgreSQL es la base de datos primaria local y de aplicación.
- **FR-004**: La documentación MUST declarar que WhatsApp y Telegram son canales conversacionales soportados.
- **FR-005**: La documentación MUST declarar que OpenAI se usa para NLU/interpretación, no como autoridad para acciones críticas.
- **FR-006**: La documentación MUST listar los módulos principales: auth, businesses, services, customers, appointments, schedules, dashboard, handlers, orchestrator y channel clients.
- **FR-007**: La documentación MUST registrar que futuras funcionalidades deben partir de specs en `specs/`.
- **FR-008**: La documentación MUST mantener el backlog post-MVP separado del alcance actual.

### Key Entities *(include if feature involves data)*

- **Owner**: Dueño que accede al panel y posee negocios.
- **Business**: Negocio multi-tenant con datos de contacto, canal y configuración.
- **Service**: Servicio reservable con duración, precio y estado activo.
- **Customer**: Cliente identificado por teléfono o canal.
- **Appointment**: Cita con fecha, servicio, cliente, negocio y estado.
- **ScheduleRule / ScheduleException / TimeBlock**: Reglas y excepciones de disponibilidad.
- **ConversationState**: Contexto persistido por negocio y usuario/canal.
- **TelegramUserBinding**: Vínculo entre usuario Telegram y negocio.
- **RefreshToken**: Token opaco persistido para renovar sesiones de dueños.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un nuevo colaborador puede encontrar stack, módulos y quickstart en menos de 10 minutos.
- **SC-002**: Las futuras specs pueden referenciar `000-project-baseline` sin repetir toda la arquitectura.
- **SC-003**: Las contradicciones Django/FastAPI quedan resueltas a favor del backend FastAPI actual.
- **SC-004**: El proyecto tiene una constitución versionada en `.specify/memory/constitution.md`.

## Assumptions

- El estado de `PROYECTO_STATUS.md` del 7 de abril de 2026 está más alineado con el código que `PROJECT_SUMMARY.txt`.
- Este paquete no cambia código de producto.
- La baseline documenta el estado actual, no promete que todas las capacidades estén productivamente desplegadas.

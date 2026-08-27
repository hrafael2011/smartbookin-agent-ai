# ADR-003: PostgreSQL sobre MongoDB

- **Estado:** Aceptado
- **Fecha:** 2026-06-26
- **Decidido por:** [Tu nombre]

## Contexto

El dominio de agendamiento de citas involucra entidades fuertemente relacionadas:

- **Owner** → **Business** → **Services, Customers, Appointments**
- **Appointment** depende de **Customer**, **Service**, y **Business**
- Las reglas de negocio requieren integridad referencial: una cita no puede existir sin un servicio y un cliente
- El estado de conversación (ConversationState) necesita consistencia transaccional

Existían dos enfoques para la base de datos:
1. **MongoDB** — base de datos documental NoSQL
2. **PostgreSQL** — base de datos relacional con soporte JSONB

## Decisión

Elegimos **PostgreSQL** con SQLAlchemy async y Alembic para migraciones versionadas.

## Alternativas consideradas

### MongoDB (descartado)

**Ventajas:**
- Schema flexible — fácil de iterar en etapas tempranas
- Documentos anidados — una cita con todos sus datos en un solo documento
- Escalado horizontal más sencillo

**Desventajas:**
- Sin integridad referencial nativa — riesgo de datos huérfanos (citas sin cliente, servicios sin negocio)
- Transacciones multi-documento limitadas (no soportadas en configuraciones sharded)
- Las consultas de disponibilidad (join entre horarios, excepciones, servicios) son más complejas
- Los estados de conversación (FSM) se benefician de consistencia transaccional (atomicidad en actualizaciones de estado)

### PostgreSQL (elegido)

**Ventajas:**
- Integridad referencial con FK constraints — nunca hay citas huérfanas
- Transacciones ACID — crítico para FSM de conversación (consistencia entre estado y acción)
- Alembic para migraciones versionadas con rollback
- JSONB para datos flexibles (estado de conversación, payloads de webhook, metadatos)
- Rendimiento predecible para el volumen esperado (cientos, no millones de citas)

**Desventajas:**
- Migraciones de schema necesarias para cada cambio de modelo (mitigado por Alembic)
- Menos flexible que MongoDB para datos no estructurados
- El escalado horizontal es más complejo (requiere sharding manual)

## Consecuencias

- **Positivo:** Integridad referencial garantizada — nunca hay citas sin cliente o servicio
- **Positivo:** Transacciones ACID para el FSM — el estado de conversación y la acción se actualizan atómicamente
- **Positivo:** ConversationState almacenado como JSONB dentro de schema relacional — lo mejor de ambos mundos
- **Negativo:** Las migraciones de schema son un paso extra en cada cambio de modelo
- **Negativo:** El esquema relacional es más rígido para prototipado rápido

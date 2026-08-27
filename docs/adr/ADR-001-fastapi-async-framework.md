# ADR-001: FastAPI como Framework Backend

- **Estado:** Aceptado
- **Fecha:** 2026-06-26
- **Decidido por:** [Tu nombre]

## Contexto

El proyecto requiere un backend que soporte:
- Webhooks asíncronos de WhatsApp Cloud API y Telegram Bot API sin bloquear el event loop
- Múltiples llamadas concurrentes a APIs externas (OpenAI, Meta, Telegram)
- Documentación de API auto-generada y accesible
- Tipado y validación robusta de datos en runtime
- ORM con soporte async para queries no bloqueantes a PostgreSQL

Se evaluaron frameworks para Python que cubrieran estos requisitos desde la arquitectura inicial.

## Decisión

Elegimos **FastAPI** con SQLAlchemy async, Alembic para migraciones, y Pydantic v2 para validación.

## Alternativas consideradas

### Django REST + Django Channels (descartado)

**Ventajas:**
- Ecosistema maduro con muchos paquetes third-party
- Admin panel built-in
- ORM probado y documentado

**Desventajas:**
- Async en Django es un "add-on" (Channels, ASGI) — no es nativo del framework
- Django ORM es sincrónico — las queries bloquean el event loop en handlers async
- Documentación de API requiere configurar herramientas externas (drf-spectacular, drf-yasg)
- Overhead de configuración para webhooks vs FastAPI que los maneja de forma nativa
- Más código boilerplate para lograr lo mismo

### FastAPI (elegido)

**Ventajas:**
- Async nativo con `async def` — webhooks y llamadas concurrentes sin bloqueo
- SQLAlchemy 2 async — queries no bloqueantes a PostgreSQL
- OpenAPI auto-generado (Swagger + ReDoc) sin configuración adicional
- Validación nativa con Pydantic v2 — request/response tipados en runtime
- Performance superior para I/O bound (llamadas a WhatsApp, Telegram, OpenAI)
- Menos código boilerplate — decoradores intuitivos, inyección de dependencias nativa

**Desventajas:**
- Sin admin panel built-in (reemplazado por frontend React custom)
- Ecosistema más pequeño que Django (menos paquetes third-party)
- Curva de aprendizaje para desarrolladores acostumbrados a Django

## Consecuencias

- **Positivo:** Webhooks de WhatsApp y Telegram completamente asíncronos desde el día uno
- **Positivo:** Documentación de API auto-generada en `/docs` y `/redoc`
- **Positivo:** Tipo seguro — Pydantic valida request/response en runtime
- **Positivo:** Las pruebas de API se benefician de OpenAPI para generar clients de test
- **Negativo:** Sin admin panel out-of-the-box — se construyó frontend React personalizado

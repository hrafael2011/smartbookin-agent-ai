# Research: Canal De Comandos Del Dueño

## Decision: Telegram first for owner command channel

**Decision**: Implementar el canal del dueño primero en Telegram.

**Rationale**: Telegram facilita deep links, callbacks, pruebas internas y sesiones de comandos sin depender tanto de la ventana de 24h de WhatsApp.

**Alternatives considered**:

- WhatsApp first: útil para notificaciones, pero más restrictivo para comandos administrativos.
- Both channels from day one: más superficie de riesgo y duplicación para MVP.

## Decision: One business per owner during MVP

**Decision**: Bloquear multi-negocio en MVP.

**Rationale**: Multi-negocio sin planes de pago permite abuso de recursos: más canales, más webhooks, más citas, más agenda, más tokens y más carga operativa.

**Alternatives considered**:

- Permitir multi-negocio gratis: rechazado por riesgo comercial y técnico.
- Permitir multi-negocio oculto solo en backend: rechazado porque el frontend ya expone selector/botón y produciría inconsistencias.

## Decision: Read-only owner phase 1

**Decision**: Fase 1 del canal del dueño será consulta y métricas, no mutación administrativa.

**Rationale**: El dueño tiene permisos poderosos. Primero se valida identidad, binding, agenda, métricas y navegación.

**Alternatives considered**:

- Incluir cancelar/reagendar/bloquear desde el inicio: rechazado por riesgo y necesidad de auditoría/confirmación más amplia.

## Decision: Separate owner binding

**Decision**: Crear `OwnerChannelBinding` o entidad equivalente.

**Rationale**: `TelegramUserBinding` actual modela cliente→negocio. El dueño necesita `owner_id`, `business_id`, rol, canal y estado activo.

**Alternatives considered**:

- Reutilizar `TelegramUserBinding`: rechazado porque mezcla permisos y roles.

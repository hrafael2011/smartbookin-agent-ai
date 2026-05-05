# Contract: Owner Command Channel

## Owner Binding

Entidad propuesta:

```text
OwnerChannelBinding
- id
- owner_id
- business_id
- channel
- channel_user_id
- role
- is_active
- created_at
- last_used_at
```

Constraints MVP:

- `owner_id` debe pertenecer al `business_id`.
- Un owner solo puede operar un negocio activo.
- `channel + channel_user_id` activo no debe mapear a múltiples owners.
- No reutilizar `TelegramUserBinding` de clientes para permisos de dueño.
- Owner activation payload MUST use an explicit prefix such as `owner_<token>` to avoid collision with customer booking links.
- If an owner has multiple inherited businesses, activation MUST fail safely until support resolves the active business.

## Owner Menu

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

## Read Models

### Agenda Item

```text
- appointment_id
- local_time
- customer_name
- customer_phone
- service_name
- status
- price
```

### Daily Metrics

```text
- total_appointments
- pending
- confirmed
- completed
- cancelled
- estimated_revenue
- realized_revenue
```

## Security Rules

- All owner commands require active owner binding.
- All queries must verify `business.owner_id == owner_id`.
- Telegram `/start` payloads must be classified before resolving tokens: `owner_` payloads use owner activation; unprefixed payloads use customer business invite.
- Phase 1 commands are read-only.
- Mutating commands require a future spec and explicit confirmation.
- Logs must include `owner_id`, `business_id`, `channel`, `channel_user_id`, command, result and timestamp.

## Frontend Contract

During MVP:

- `Sidebar.tsx` must not show “Nuevo negocio” if `businesses.length >= 1`.
- `Sidebar.tsx` must not expose multi-business selector as a product feature.
- `BusinessOnboarding.tsx` remains available only for owners with zero businesses.
- `businessStore.createBusiness()` should surface backend rejection clearly if the owner already has a business.
- Future multi-business UI requires paid-plan spec.

# Plan Técnico: Acciones Administrativas Del Dueño - Fase 2

## Resumen

Extiende el canal del dueño Telegram (spec 002) con acciones mutables: cancelar, marcar como completada y reagendar citas desde el detalle de agenda, más bloquear horarios desde el menú principal y el toggle real de notificaciones. Toda mutación pasa por confirmación explícita del dueño antes de escribir en base de datos.

## Menú Principal Actualizado

```
Panel rápido - <business>

1) Agenda de hoy
2) Agenda de mañana
3) Próximas citas
4) Métricas de hoy
5) Notificaciones          ← toggle real de Business.daily_notification_enabled
6) Bloquear horario        ← nuevo

9) Volver
0) Menú principal
X) Salir
```

## Acciones desde Detalle de Cita

Solo para citas con estado P (pendiente) o C (confirmada):

```
C) Cancelar esta cita
M) Marcar como completada
R) Reagendar
```

Citas canceladas (A) o completadas (D) no muestran estas opciones.

## Nuevos Estados de Conversación del Owner

| Estado | Descripción |
|--------|-------------|
| `owner_cancel_confirm` | Esperando sí/no para confirmar cancelación |
| `owner_complete_confirm` | Esperando sí/no para confirmar completar |
| `owner_reschedule_ask_date` | Esperando nueva fecha para reagendar |
| `owner_reschedule_slots` | Mostrando slots disponibles, esperando selección |
| `owner_reschedule_confirm` | Esperando sí/no para confirmar el nuevo slot |
| `owner_block_ask_date` | Esperando fecha para bloquear |
| `owner_block_ask_start` | Esperando hora inicio del bloqueo |
| `owner_block_ask_end` | Esperando hora fin del bloqueo |
| `owner_block_confirm` | Esperando sí/no para confirmar el bloqueo |

## Archivos Nuevos o Modificados

- **`app/services/owner_mutations.py`** (nuevo): validaciones de ownership/estado y llamadas a db_service. Funciones: `owner_cancel_appointment`, `owner_complete_appointment`, `owner_reschedule_appointment`, `owner_block_timeslot`. Retorna `MutationResult(ok, error)`.
- **`app/services/db_service.py`** (adición): `get_appointment_for_owner`, `mark_appointment_done`, `get_active_appointments_in_window`, `create_time_block`, `toggle_business_notifications`.
- **`app/services/owner_read_models.py`** (modificación): `format_appointment_detail` muestra C/M/R solo para estados activos.
- **`app/services/owner_command_router.py`** (modificación): nuevos estados, routing, y ejecutores de flujos. `_FLOW_STATES` lista los estados que producen `flow_input`.
- **`tests/test_owner_actions_phase2.py`** (nuevo): 45 tests cubriendo routing, formato, flujos completos y unit tests de mutations.

## Reglas No-Negociables

- Confirmación explícita (`sí/no`) antes de toda mutación.
- Bloquear horario falla si hay citas activas (P/C) que solapan.
- Solo P/C aceptan cancelar, completar o reagendar.
- Reagendar revalida disponibilidad en tiempo real.
- Respuestas ambiguas ("no entendí") no ejecutan acciones.
- Todo flujo respeta timeout de 30 minutos y navegación 9/0/X.
- WhatsApp owner commands fuera de scope hasta spec separada.

## Perfil de Verificación

```bash
./scripts/verify-mvp.sh backend-owner
```

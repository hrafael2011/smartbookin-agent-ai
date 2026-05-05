# Feature Specification: Acciones Administrativas Del Dueño - Fase 2

**Feature Branch**: `003-owner-actions-phase-2`  
**Created**: 2026-04-30  
**Status**: Draft / Future  
**Input**: Registrar acciones mutables futuras para el canal del dueño antes de implementarlas.

## Scope

Esta spec futura habilitará acciones administrativas desde el canal del dueño, partiendo del canal Telegram ya vinculado en `specs/002-owner-command-channel/`.

## Candidate Actions

- Marcar una cita como completada.
- Cancelar una cita.
- Reagendar una cita.
- Bloquear un horario.
- Activar/desactivar notificaciones operativas.

## Non-Negotiable Rules

- Toda acción mutable requiere confirmación explícita antes de escribir en base de datos.
- El bot debe mostrar resumen de impacto: cita, cliente, servicio, fecha/hora y cambio solicitado.
- La IA puede interpretar intención/datos, pero no ejecuta acciones.
- Los handlers determinísticos ejecutan la acción después de validar owner, negocio y estado.
- Cada acción debe ser idempotente o segura ante mensajes duplicados.
- Debe existir navegación `9) Volver`, `0) Menú principal`, `X) Salir` y timeout de 30 minutos.
- WhatsApp owner commands quedan fuera hasta una spec separada.

## Future Acceptance Tests

- Cancelar cita requiere confirmación `sí, cancelar`.
- Reagendar cita requiere elegir nuevo horario disponible y confirmar.
- Marcar completada no aplica a citas canceladas.
- Bloquear horario no permite solapar citas activas.
- Mensajes ambiguos o groseros no ejecutan acciones.

# Costos de WhatsApp Business API — modelo para SmartBooking

Meta cobra **por plantilla entregada** (no por conversación ni por mensaje de
servicio dentro de la ventana). El precio varía por **categoría** de la plantilla
y por **país** del destinatario.

## Recordatorios (plantilla Utility)

- Rango aproximado **LATAM Utility**: **~$0.02–0.05 USD** por mensaje entregado.
- SmartBooking envía **2 recordatorios por cita** (24h y 2h antes), ambos como
  plantilla de Utilidad con botones (confirmar/reprogramar/cancelar).

### Cambio de tarifas — 1 de octubre de 2026

A partir de esa fecha Meta empieza a cobrar **también los mensajes de servicio
salientes y las plantillas Utility dentro de la ventana de 24h** (hasta ahora
gratuitos en esa ventana). Consecuencia directa: **prácticamente todos los
recordatorios automáticos tendrán costo**, haya ventana abierta o no.

## Ejemplo de cálculo (por negocio)

| Citas/día | Recordatorios/mes | Costo estimado/mes (LATAM) |
|---|---|---|
| 10 | ~600 (2 × 10 × 30) | ~$12–30 USD |
| 30 | ~1,800 | ~$36–90 USD |

Nota: los reintentos de recordatorios fallidos también cuentan como envío si la
plantilla se entrega. Los `statuses` de Meta (sent/failed) se loguean en el
webhook (`wa_status_update`) para auditar entregas reales.

## Consideraciones para el pricing a negocios clientes

1. El límite de **250 contactos/día por WABA** (sin verificación de negocio) limita
   cuántos recordatorios puede enviar un negocio — no es costo pero sí tope operativo.
2. La **verificación de negocio** (Meta Business Manager + documentación) salta al
   esquema 2026 de **100K mensajes/día** y suele mejorar tarifas por volumen.
3. Con el cambio de octubre 2026, el costo de recordatorios es predecible:
   **2 × tarifa Utility por cita** — base limpia para cobrar al negocio (p. ej.
   por cita o por recordatorio) o absorberlo en el plan.

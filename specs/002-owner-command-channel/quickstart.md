# Quickstart: Canal De Comandos Del Dueño

## Validación Manual Esperada

1. Iniciar sesión como owner en el panel.
2. Confirmar que solo existe un negocio activo.
3. Abrir `/telegram`, sección **Canal del dueño**.
4. Validar que el panel llama `GET /api/businesses/{business_id}/owner-telegram`.
5. Copiar `deep_link` o abrir el enlace devuelto.
6. Abrir Telegram con el enlace.
7. Confirmar que el payload usa `/start owner_<token>`.
8. Enviar `/start` nuevamente.

Ruta alternativa por API:

```bash
curl -H "Authorization: Bearer <access_token>" \
  http://localhost:8000/api/businesses/<business_id>/owner-telegram
```

Respuesta esperada:

```text
Panel rápido - Barbería Excelencia

1) Agenda de hoy
2) Agenda de mañana
3) Próximas citas
4) Métricas de hoy
5) Notificaciones

9) Volver
0) Menú principal
X) Salir
```

## Comandos Esperados

- `1` o `agenda de hoy`: lista citas de hoy en `America/Santo_Domingo`.
- `2` o `agenda de mañana`: lista citas de mañana.
- `3` o `próximas citas`: lista próximas citas activas.
- `4` o `métricas`: muestra conteos e ingresos del día.
- Número dentro de una agenda listada: abre detalle de cita sin mutar datos.
- `9`: vuelve al menú anterior o al menú principal si no hay pila específica.
- `0` o `menu`: vuelve al menú principal.
- `x` o `salir`: cierra el panel rápido.

## Validación Automática

```bash
./scripts/verify-mvp.sh backend-owner
./scripts/verify-mvp.sh frontend
```

## Métricas De Hoy

Con citas de prueba:

- `P`: RD$ 500
- `C`: RD$ 700
- `D`: RD$ 300
- `A`: RD$ 900

Resultado esperado:

```text
Ingreso estimado: RD$ 1,200
Ingreso realizado: RD$ 300
```

La cita cancelada no suma ingresos. La cita completada cuenta como ingreso realizado, no como ingreso estimado.

## Frontend MVP Limit

Cuando el owner ya tiene un negocio:

- No debe aparecer botón “Nuevo negocio”.
- No debe aparecer selector de múltiples negocios.
- Si por datos heredados hay más de un negocio, mostrar estado de soporte/configuración requerida.

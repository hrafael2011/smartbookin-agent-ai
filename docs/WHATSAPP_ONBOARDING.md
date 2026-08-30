# Onboarding WhatsApp — conectar el número de un negocio (piloto manual)

Cada negocio cliente aporta **su propio número de WhatsApp** como su propia WABA
(WhatsApp Business Account) dentro de la Meta App del desarrollador. El bot
responde a los mensajes de ese número con la configuración del negocio.

## Flujo manual (piloto)

1. **Crear la WABA del negocio** en Meta Business Manager:
   - Entrar a https://business.facebook.com/ → Configuración → Cuentas de WhatsApp.
   - Crear cuenta / agregar número (los casos especiales están más abajo).
2. **Copiar los IDs** desde Meta Business Manager → WhatsApp → Configuración:
   - **Phone number ID** (identifica el número).
   - **WABA ID** (identifica la cuenta de negocio).
3. **Pegarlos en SmartBooking**: Configuración del negocio → card "WhatsApp Business" → guardar.
   El backend valida que no estén registrados a otro negocio (409 si ya existen).
4. **Configurar el webhook en la app de Meta** (una vez por app, apunta a todos los números):
   - URL: `https://<railway>/webhooks/whatsapp`
   - Verificación: `META_VERIFY_TOKEN` del entorno.
5. **Probar**: enviar un WhatsApp real al número → el bot debe responder con el menú.
   Registrar el `phone_number_id` del webhook entrante (log `wa_route`) para confirmar
   que la resolución de tenant funciona.

## Casos según el estado del número

| Estado del número | Qué hacer |
|---|---|
| **Nuevo** (nunca usado en WhatsApp) | Flujo directo, sin fricción. |
| **Activo en WhatsApp App / Business App** | Se migra a la Cloud API conservando historial; puede usarse **Coexistence** para que el negocio siga usando la app móvil en paralelo mientras el bot opera por API. |
| **Conectado a otro proveedor/BSP** | El negocio debe pedir a su proveedor la **liberación/desvinculación** del número primero (Meta no permite un número en dos WABAs). No hay "botón mágico" — es manual en el panel del proveedor. |

## Después del onboarding (operativo)

- **Aprobar la plantilla de recordatorios** (una vez por WABA): en Business Manager →
  Gestión de mensajes → Plantillas de mensajes → crear `appointment_reminder`
  (categoría **Utility**). La aprobación en modo prueba es inmediata; en producción
  puede tardar horas/días. Sin plantilla aprobada, los recordatorios fallan (131026).
- **Límite de mensajería**: cada WABA sin verificación arranca en **250 contactos
  únicos/día iniciados por el negocio** — los recordatorios (2 por cita) cuentan.
  Con verificación de negocio el esquema 2026 salta directo a 100K/día.
- **Token**: el `META_WABA_TOKEN` debe ser un System User token de la Meta App con
  scopes `whatsapp_business_messaging` **y** `whatsapp_business_management`
  (este último es necesario para plantillas y `subscribed_apps`).

## Futuro: Embedded Signup automatizado

Pendiente (post-piloto): flujo OAuth/JS de Meta que crea la WABA dentro de la app,
callback que recibe `waba_id`/`phone_number_id`, suscripción de la app a los webhooks
de la WABA (`POST /{waba_id}/subscribed_apps`) y prueba real de entrega antes de
marcar el tenant como listo.

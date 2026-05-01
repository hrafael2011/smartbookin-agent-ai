# Revisión QA (enfoque tester senior) — SmartBooking AI

**Fecha:** 2026-04-30  
**Alcance:** backend conversacional/API, seguridad básica de webhooks, coherencia con specs, calidad de pruebas y frontend (lint/build/E2E).  
**Nota:** Este documento es un **informe de revisión**, no sustituye pentesting ni auditoría de cumplimiento.

---

## Resumen ejecutivo

- **Automatizado verde:** suite de `pytest` en `backend/api-backend` (**102 passed**).  
- **Frontend:** `npm run lint` y `npm run build` **OK**.  
- **E2E (Playwright):** en el entorno de revisión los tests **no llegaron a un resultado estable** (arranque de `webServer` / ejecución de Chromium); **hace falta confirmar en CI o máquina local** con `npm run test:e2e` tras `npx playwright install chromium`.  
- Los riesgos más relevantes para producción están en **webhook de Telegram sin autenticación de origen**, **respuestas de error que pueden filtrar detalles internos**, y **valores por defecto inseguros si `.env` no está bien cerrado** (JWT / verificación de email).

---

## Verificación realizada

| Ámbito | Comando / acción | Resultado |
|--------|------------------|-----------|
| Backend | `python -m pytest` (desde `backend/api-backend`) | 102 passed |
| Frontend | `npm run lint`, `npm run build` | OK |
| E2E | `npm run test:e2e` | No concluyente en revisión (ver arriba) |

---

## Hallazgos (por severidad)

### Alta

1. **Webhook `POST /webhooks/telegram` sin validación de origen (token secreto)**  
   - **Qué:** Meta WhatsApp valida firma HMAC (`X-Hub-Signature-256`). El endpoint de Telegram acepta el cuerpo JSON sin comprobar un **secret** configurado vía `setWebhook` (header `X-Telegram-Bot-Api-Secret-Token`) ni IP allowlist.  
   - **Riesgo:** Cualquier actor que pueda alcanzar la URL pública puede **inyectar actualizaciones sintéticas** (spam, consumo de cuota, ruido en logs, confusión operativa). El impacto real depende de exposición en Internet y de si los bindings permiten efectos colaterales.  
   - **Referencia:** `backend/api-backend/main.py` (`telegram_webhook`).  
   - **Recomendación:** Configurar y verificar el **secret token** del webhook de Telegram; rechazar requests sin coincidencia. Documentar en despliegue.

2. **Filtración de información en respuestas de error de webhooks**  
   - **Qué:** En excepciones, se devuelve el mensaje de error al cliente (`str(e)`), p. ej. en Telegram y WhatsApp.  
   - **Riesgo:** Detalles de stack/DB/config pueden exponerse a quien dispare el webhook.  
   - **Referencia:** `backend/api-backend/main.py`, `backend/api-backend/app/services/telegram_inbound.py`.  
   - **Recomendación:** Responder cuerpo genérico (`{"status":"error"}`) y registrar el detalle solo en logs/Sentry.

3. **Secreto JWT por defecto en código**  
   - **Qué:** `JWT_SECRET_KEY` cae en un valor por defecto si no está en entorno.  
   - **Riesgo:** Tokens firmados predecibles en despliegues mal configurados.  
   - **Referencia:** `backend/api-backend/app/core/security.py`.  
   - **Recomendación:** En producción, **fallar al arranque** si falta `JWT_SECRET_KEY` (o exigir longitud mínima).

### Media

4. **Rate limit HTTP global en memoria del proceso**  
   - **Qué:** Middleware usa diccionario en RAM por IP.  
   - **Riesgo:** Con **varios workers** o réplicas, el límite no es global; fácil de evadir; además se reinicia al redeploy.  
   - **Referencia:** `backend/api-backend/main.py` (`rate_limit_middleware`).  
   - **Recomendación:** Redis (ya usado en otras partes) o proxy (Nginx/Cloudflare).

5. **Cuotas diarias con fallback a archivo**  
   - **Qué:** Sin Redis, contadores usan archivo bajo `/tmp` (según `RATE_LIMIT_STATE_FILE`).  
   - **Riesgo:** Condiciones de carrera entre procesos; límites inexactos bajo concurrencia.  
   - **Referencia:** `backend/api-backend/app/services/rate_limit_async.py`.

6. **`AUTO_VERIFY_EMAIL` por defecto habilitado**  
   - **Qué:** Valor por defecto trata como verdadero si el env no fuerza lo contrario (según lectura de `config.py`).  
   - **Riesgo:** Cuentas “verificadas” sin email real en entornos mal configurados.  
   - **Referencia:** `backend/api-backend/app/config.py`.  
   - **Recomendación:** Default **false** fuera de desarrollo, o exigir explícito en prod.

7. **Brecha funcional vs spec `001-guided-menu-bot` — “Volver” (`9`)**  
   - **Qué:** La spec (FR-022) pide volver al **paso anterior** cuando hay historial. La implementación actual indica explícitamente fallback: **limpia flujo y muestra menú principal**.  
   - **Referencia:** `backend/api-backend/app/services/guided_menu_router.py` (`go_back`).  
   - **Recomendación:** Aceptar como **deuda documentada** o implementar pila de pasos + pruebas de regresión.

8. **Copy de onboarding Telegram vs política menu-first**  
   - **Qué:** Tras vincular negocio, el mensaje de bienvenida sigue enfatizando **lenguaje natural** en lugar del menú numerado como interfaz principal.  
   - **Riesgo:** UX inconsistente con `specs/001-guided-menu-bot` y con tests que esperan menú sin IA en saludos.  
   - **Referencia:** `backend/api-backend/app/services/telegram_inbound.py` (`_send_welcome_for_business`).

### Baja / mantenibilidad

9. **Uso de `print()` en rutas críticas**  
   - **Qué:** Errores en webhooks y parsers usan `print` en lugar de logger estructurado.  
   - **Impacto:** Observabilidad y filtrado en producción más difíciles.  
   - **Referencia:** `main.py`, `telegram_inbound.py`, `telegram_client.py`, `whatsapp_client.py`.

10. **Nombres/config heredados (“Agent Service”, `DJANGO_API_BASE_URL`)**  
    - **Impacto:** Confusión para nuevos desarrolladores y para operaciones (no es fallo funcional por sí solo).  
    - **Referencia:** `backend/api-backend/main.py`, `backend/api-backend/app/config.py`.

11. **Identidad “from” en Telegram = `chat.id`**  
    - **Qué:** El extractor usa el id del chat como `from`. En chats privados suele alinearse con el usuario; en **grupos** el modelo de negocio multi-tenant por binding puede no ser el deseado.  
    - **Referencia:** `backend/api-backend/app/services/telegram_client.py`.  
    - **Recomendación:** Si el producto es solo 1:1, **rechazar** mensajes de grupos o documentar el comportamiento.

12. **Frontend sin tests unitarios en `package.json`**  
    - **Qué:** Solo `lint`, `build` y Playwright E2E.  
    - **Impacto:** Regresiones en lógica de UI/store requieren E2E o prueba manual.

---

## Coherencia especificación ↔ implementación (puntos a socializar)

| Tema | Spec / constitución | Estado en código |
|------|---------------------|----------------|
| Menú guiado primero en `idle` | `001-guided-menu-bot` | Cubierto en gran parte por `guided_menu_router` + tests |
| IA solo interpreta, no muta | Constitución + `001` | Orquestador y handlers mantienen el modelo; revisar mensajes que aún invitan a NLU libre (bienvenida Telegram) |
| `9` vuelve al paso anterior | FR-022 | **No cumplido** (fallback a menú) |
| Idempotencia de eventos | Constitución | Implementada vía DB + fallback memoria (`idempotency.py`) |
| Paridad WhatsApp / Telegram | Constitución | Misma ruta guiada + cuota; validación de origen **asimétrica** (WhatsApp firma / Telegram no) |

---

## Recomendaciones de prueba (siguiente iteración)

1. **Contrato de webhook Telegram:** tests que fallen si falta header de secreto cuando esté configurado.  
2. **E2E:** ejecutar en CI con `CI=true`, un solo worker, artefactos de trace en fallo.  
3. **Carga mínima:** dos workers + mismo evento duplicado → una sola mutación (idempotencia).  
4. **Regresión copy:** assertion de que bienvenida Telegram incluye menú numerado o enlace explícito a `menu`.  
5. **Frontend:** introducir Vitest/React Testing Library para stores y rutas críticas (login, negocio único).

---

## Conclusión

El proyecto muestra **buena disciplina de pruebas backend** (orquestador, menú guiado, idempotencia, webhooks mockeados) y **build estable del frontend**. Los temas que conviene **priorizar en reunión** son: **endurecimiento del webhook de Telegram**, **manejo de errores sin filtrar**, **secretos y flags por defecto en producción**, y **alinear “volver” + copy de bienvenida** con la spec activa del bot guiado.

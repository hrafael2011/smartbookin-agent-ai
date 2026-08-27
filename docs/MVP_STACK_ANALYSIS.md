# Pila mínima viable — Análisis de sobreingeniería del MVP

**Fecha:** 2026-08-27
**Alcance:** qué sustituir en el stack actual de SmartBooking AI para un MVP de bajo tráfico, con foco en costos y en que los servicios no estén encendidos 24/7.

## Veredicto en una frase

El MVP necesita **3 cambios, no un rewrite**: frontend a Vercel, base de datos a Neon free, backend a Railway con sleep. Nginx, los 4 contenedores de estáticos, Redis y el scheduler en proceso desaparecen. Costo objetivo: **~$5–10/mes** (vs ~$15–30 de VPS + Docker siempre encendido), sin tocar el ORM, el FSM ni los handlers.

---

## 1. Lo que sobra hoy

| Pieza | Por qué sobra | Sustituto | Acción |
|---|---|---|---|
| `nginx` + `frontend-build` + `webroot` + `staticfiles` | 4 contenedores solo para servir una SPA estática | **Vercel** (CDN, HTTPS, $0; ya hay config en `.vercel/`) | Quitar |
| Postgres en contenedor propio | Mantener una VM de Docker encendida para ~10–50 citas/día | **Neon free** (Postgres real, autosuspend 5 min, wake ~0.5 s, 0.5 GB, 100 CU-h/mes) | Migrar |
| APScheduler en proceso (`app/core/scheduler.py`) | Obliga a que el proceso esté vivo 24/7 (recordatorios, expiración waitlist, reportes) | **Cron externo** (Railway cron / GitHub Actions) que dispara endpoints autenticados | Mover |
| Redis | Solo rate limiting (`app/services/rate_limit_async.py`) con fallback en memoria ya implementado; no guarda conversaciones | Rate limiter en memoria (1 instancia, tráfico MVP) | Quitar |
| Verificación de email (SMTP) | No aporta al flujo de agendar | Dejar código, desactivar requisito en MVP | Postergar |
| Gunicorn multi-worker | 1 worker sobra para MVP | `--workers 1` | Simplificar |
| Sentry | Solo config, free tier | Mantener | Mantener |
| FSM + NLU + GPT-4o-mini + idempotencia + JWT | Es el producto, no infraestructura | — | Mantener |

## 2. La base de datos: PostgreSQL gana sin pelear

| Candidato | Veredicto | Razones |
|---|---|---|
| **PostgreSQL en Neon free** | ✅ Elegido | $0 real, autosuspend (no consume cómputo dormido), **cero cambios de código**. 0.5 GB = miles de citas. Migrar = cambiar `DATABASE_URL`. |
| **SQLite en producción** | 🟡 Plan C | Viable a baja escala (WAL, single-writer), pero: `SET TRANSACTION ISOLATION LEVEL REPEATABLE READ` (`db_service.py:288`) no existe en SQLite → quitar código; async + aiosqlite tiene quirks; en serverless no hay disco compartido; y el ahorro frente a Neon es **$0**. No vale los días de cambios. |
| **MongoDB** | ❌ Descartado | ADR-003 ya lo decidió: dominio relacional, FK críticas, FSM con consistencia transaccional. Reescribir `db_service` y el cálculo de disponibilidad es lo contrario del objetivo. |

**Descartados también:** Render free Postgres (se **borra a los 30 días**) y Supabase free (pausa la instancia tras ~1 semana inactiva). Neon es el único free tier pensado para producción ligera.

## 3. Servidor dormido × webhooks: la única tensión real

**WhatsApp Cloud API exige responder el webhook con HTTP 200 en ~5 s.** Si el servicio duerme y tarda más, Meta reintenta con backoff hasta ~7 días. No hay dead-letter queue.

La buena noticia: **el sistema ya está blindado para esto**. La idempotencia por `event_id` (spec 001) existe exactamente para entrega at-least-once. Peor caso real: el primer webhook despierta el servicio, Meta reintenta, la segunda entrega cae en instancia caliente → sin pérdida, solo unos segundos de retraso.

| Plataforma | Sleep | Wake | Veredicto |
|---|---|---|---|
| **Railway** | ~10 min sin tráfico, deja de facturar cómputo | Cold boot (no destruye contenedor) | ✅ Elegido |
| Render free | 15 min | 30–60 s → retry storm con Meta | ❌ Descartado |
| Fly.io | Autostop de máquinas | ~1 s | Alternativa válida |
| VPS (Hetzner ~€4–5) | — | — | Plan B, cero sorpresas |

**Telegram** admite `getUpdates` por polling (un cron puede procesarlo sin webhook). **WhatsApp es el canal que dicta la arquitectura.**

## 4. Arquitectura: antes y después

```
HOY (docker compose, 7 servicios):
  api-backend · postgres · frontend-build · nginx · webroot · staticfiles · ngrok(dev)

OBJETIVO (2 servicios gestionados + 1 cron):
  Vercel (SPA, $0) ← → Railway (FastAPI, duerme, $5) → Neon (Postgres, duerme, $0)
                                              ↷ Cron externo (recordatorios, $0)
```

Nginx deja de existir: Vercel sirve la SPA por CDN y Railway expone el backend con HTTPS nativo.

## 5. Costos estimados

| Componente | Proveedor | Mensual |
|---|---|---|
| Frontend (SPA) | Vercel | $0 |
| Base de datos | Neon free | $0 |
| Backend | Railway Hobby (crédito $5, per-second billing) | ~$5 |
| NLU (GPT-4o-mini) | OpenAI (solo fallback; menú guiado cubre la mayoría) | ~$1–5 |
| Cron | Railway cron / GH Actions | $0 |
| **Total** | | **~$6–10** |

Variante **$0 total**: API en funciones serverless + Neon + cron de GitHub Actions. Requiere más refactor (rate limiter por instancia, pool por función). Fase posterior, no punto de partida.

## 6. Plan de acción

1. **Frontend a Vercel (1–2 días)** — desplegar `npm run build`; borrar nginx, frontend-build, webroot y staticfiles del compose.
2. **DB a Neon (1 día)** — dump/restore del Postgres local, ejecutar migraciones pendientes, cambiar `DATABASE_URL`, correr los 203 tests.
3. **Backend a Railway + cron (1–2 días)** — deploy con `workers=1`; mover jobs de APScheduler a cron externo; borrar contenedor `postgres`; ngrok solo para dev.
4. **Prueba de frío de webhooks (medio día)** — dormir 30 min, enviar mensaje WhatsApp y Telegram, verificar procesamiento único. Si WhatsApp duele → instancia mínima o plan B (VPS).
5. **Podas opcionales** — desactivar verificación email, quitar Redis del rate limiter, evaluar Sentry.

**Postergado a v1.1+ (Phase 6 ya documentado):** pagos, límites comerciales, multi-negocio, roles, auditoría avanzada, CI/CD completo.

## 7. Riesgos y absorción

- **Latencia del primer webhook tras inactividad** → retries de Meta + idempotencia: retraso de segundos, nunca pérdida.
- **0.5 GB Neon** → cientos de miles de citas; subir de plan es un clic.
- **Rate limiting por instancia** (sin Redis) → idéntico al actual con 1 instancia; reevaluar al escalar.
- **100 CU-h/mes Neon** (~13 h activas/día a 0.25 CU) → holgado para el tráfico esperado; poner alerta de uso.

## Fuentes (agosto 2026)

- [Neon — free plan, límites y autosuspend](https://neon.com/guides/neon-vs-supabase-free-plan)
- [Neon — cuotas del free plan (docs oficiales)](https://github.com/neondatabase/website/blob/main/content/faqs/free-plan-limits-and-quotas.md)
- [Railway pricing 2026](https://dev.to/david_viejo_4d48fdfa7cfff/railway-pricing-2026-what-it-actually-costs-23ad)
- [Render — free tier y cold starts](https://render.com/articles/platforms-with-a-real-free-tier-for-developers-in-2026)
- [WhatsApp webhooks: timeouts, retries e idempotencia](https://hookdeck.com/webhooks/platforms/guide-to-whatsapp-webhooks-features-and-best-practices)

# Worklog — Registro de tareas y fixes

**Propósito:** toda tarea, fix o cambio de infraestructura que se haga en este repo
**debe quedar anotado aquí**. Es el punto de verdad para que otra sesión (humano o
agente) sepa qué se hizo, qué falta y por qué.

## Convención (obligatoria)

1. **Antes de empezar** una tarea: búscala en la sección *Backlog*. Si existe, cambia su estado.
2. **Al terminar** una tarea: añade una entrada en *Registro de cambios* (más reciente arriba).
3. Cada entrada debe responder: **qué** cambió, **dónde** (archivo/servicio/variable),
   **por qué**, y **cómo se verificó**. Si no se pudo verificar, decirlo explícitamente.
4. Si una tarea se difiere, va al *Backlog* con el motivo y la fecha — nunca se borra.
5. Los cambios de infraestructura (Railway, Vercel, Neon) se anotan igual que los de código.

Estados: `PENDIENTE` · `EN CURSO` · `HECHO` · `DIFERIDO` · `DESCARTADO`

---

## Inventario de infraestructura (referencia rápida)

| Recurso | Identificador | Notas |
|---|---|---|
| Railway · proyecto | `smartbooking-ai` · `a7faa948-1b61-46e0-a0e4-001d68621971` | entorno `production` = `46e1ecd7-4c20-4804-aa1c-aafc12f4a6ba` |
| Railway · servicio backend | `smartbooking-ai` · `4cb7dbe4-5695-44a9-bfef-3dfd39c090dc` | FastAPI, root `/backend/api-backend`, Serverless ON |
| Railway · servicio cron | `reminders-cron` · `79a8984e-86df-4f2d-a82d-58e2edf067f9` | `alpine:latest`, `*/15 * * * *` |
| Neon · proyecto | `hidden-flower-89025402` (nombre: **smartbooking**) | branch `production`, BD `neondb` |
| Vercel · proyecto | `smartbookin-agent-ai` · `prj_dkWTfgeRvTm8pfEh7IEJ8TiSesGa` | plan Hobby, SPA Vite |
| GitHub | `hrafael2011/smartbookin-agent-ai` | Railway y Vercel despliegan de aquí |

---

## Backlog

### ⚠️ Bloqueante — pendiente de commit

| # | Tarea | Estado | Notas |
|---|-------|--------|-------|
| 0 | **Commitear los cambios de `backend/`** | PENDIENTE | El deploy activo se subió con `railway deployment up` (código local), **NO desde git**. El próximo deploy que dispare GitHub desde `main` **reproduce el crash del 2026-10-04**. Ver esa entrada |

### Producción

| # | Tarea | Estado | Notas |
|---|-------|--------|-------|
| 1 | `VITE_API_URL` en Vercel → URL real del backend | HECHO | Configurado por el usuario; verificado en el bundle y con CORS |
| 2 | Cron externo para recordatorios 24h/2h | HECHO | Servicio `reminders-cron`, cada 15 min. Verificado end-to-end |
| 3 | WhatsApp en producción | DIFERIDO | Decisión del usuario: lo verifica él después |
| 4 | Serverless (App Sleeping) en Railway | HECHO | Ahorro ~$0.65/mes neto |
| 5 | Parar el servicio si el MVP se pausa | PENDIENTE | Decisión del usuario. Ahorro real ~$0.22/mes |
| 6 | `AI_ENABLED=false` explícito en Railway | HECHO | Estaba off solo por default del código |
| 7 | Sentry: activar o asumir ceguera ante errores | PENDIENTE | `SENTRY_DSN` ausente → $0 de costo, cero monitoreo |
| 8 | Verificar migraciones Alembic aplicadas en Neon | HECHO | `alembic_version = f5b6ae5f0595` = head |

### Higiene

| # | Tarea | Estado | Notas |
|---|-------|--------|-------|
| 9 | Renombrar proyecto Neon `hidden-flower-89025402` | HECHO | Ahora se llama `smartbooking` |
| 10 | Borrar filas obsoletas de `apscheduler_jobs` | HECHO | 3 filas de junio borradas; tabla en 0 |
| 11 | Quitar `REDIS_URL` de `.env`/`.env.example` | HECHO | Verificado: ningún código lo lee |
| 12 | Limpiar bloque Django/Celery en `docker-compose.yml` | DESCARTADO | Ya estaba limpio. El plan estaba obsoleto |
| 13 | Actualizar docs que describen infra inexistente | PENDIENTE | `MVP_STACK_ANALYSIS.md`, `README.md`, `PROYECTO_STATUS.md` |
| 14 | Pinear dependencias del backend | HECHO | Topes de versión mayor añadidos a `requirements.txt` |

### Deuda conocida (no bloquea)

- **#3 WhatsApp:** falta `META_WABA_TOKEN` y `META_APP_SECRET`. El commit `794bb88`
  (multi-tenant interactivo) está desplegado pero no puede funcionar:
  `validate_signature()` devuelve `False` sin `app_secret` y el webhook responde 403
  (fail-closed, o sea seguro). Ver `docs/WHATSAPP_ONBOARDING.md` y `WHATSAPP_COSTING.md`.
- **500 transitorio en el primer request tras dormir Neon.** Con el contenedor frío y
  Neon suspendido, la primera query puede fallar con 500; el reintento funciona. Ocurre
  porque el pool de conexiones mantiene handles muertos. Mitigación pendiente de decidir
  (`pool_pre_ping=True` en `create_async_engine` sería lo natural).
- **Secretos expuestos el 2026-10-04:** `DATABASE_URL`, `JWT_SECRET_KEY`,
  `TELEGRAM_BOT_TOKEN`, `INTERNAL_CRON_TOKEN` y `META_VERIFY_TOKEN` quedaron en el
  transcript de la sesión. Rotación pendiente de decisión del usuario.

---

## Registro de cambios

<!-- Nuevas entradas arriba. Formato: fecha — título, luego qué/dónde/por qué/verificación -->

### 2026-10-04 — Cron de recordatorios + higiene autorizada

**Qué / Dónde:**
- **Nuevo servicio `reminders-cron`** en Railway (`79a8984e-86df-4f2d-a82d-58e2edf067f9`):
  imagen `alpine:latest`, cron `*/15 * * * *`, variables `CRON_URL` (plana) y
  `CRON_TOKEN` (variable de referencia → `${{smartbooking-ai.INTERNAL_CRON_TOKEN}}`,
  para no duplicar el secreto). Start command:
  `sh -c 'wget -O- --header="Authorization: Bearer $CRON_TOKEN" --post-data="" "$CRON_URL"; rc=$?; echo "EXIT=$rc"; exit $rc'`
- **`apscheduler_jobs`**: borradas las 3 filas obsoletas (`reminders_job`,
  `waitlist_job`, `agenda_job`, de junio). Tabla en 0 filas.
- **`requirements.txt`**: topes de versión mayor en las 20 dependencias.
- **`VITE_API_URL`**: configurada por el usuario en Vercel.

**Por qué:** los recordatorios 24h/2h no se enviaban (`CRON_EXTERNAL=true` sin cron);
el resto es la higiene autorizada por el usuario.

**Verificación:**
- Cron: ejecución real a las 15:45:14 → `{"status":"ok","job":"reminders"}` con `EXIT=0`,
  y Neon despertó (`last_active` 15:40:59) ⇒ la query llegó a la base.
- Vercel: el bundle desplegado ahora contiene `https://smartbooking-ai-production.up.railway.app/api`
  y el host muerto `9cce` ya no aparece.
- CORS: preflight `OPTIONS` desde `https://smartbookin-agent-ai.vercel.app` → 200 con
  `access-control-allow-origin` correcto; `POST /api/auth/token` → 401 con el header.
- Deps pineadas: deploy `d9652b09` → `SUCCESS`; `/`, `/docs` en 200 y login 401 consistente.

**Aprendizajes operativos (importantes para la próxima):**
1. **Todo cambio de variable en Railway dispara un redeploy.** Con dependencias sin
   pinear, eso equivale a un cambio de dependencias. Ver el incidente de abajo.
2. **Los ajustes de servicio se hornean al crear el deployment.** `sleep_application`,
   `start_command` y `cron_schedule` no aplican hasta que se **redespliega**. Me pasó con
   el cron: el contenedor arrancaba pero ignoraba el start command hasta hacer
   `railway redeploy --from-source`.
3. **Railway exige un intervalo mínimo de 5 minutos** en cron schedules.
4. Para diagnosticar un cron, **no usar `wget -q`**: silencia el error y el fallo es
   invisible. Y ojo: un **401 no toca la base de datos**, así que "Neon sin actividad"
   no distingue entre "no llegó la petición" y "llegó y falló la auth".

---

### 2026-10-04 — 🔴 Incidente: caída de producción por redeploy + fix de dependencias

**Qué:** al activar `AI_ENABLED=false` (tarea #6) Railway disparó un redeploy. El
contenedor **crasheó al arrancar** y el backend quedó en 502 durante ~14 minutos.
Se arregló y se restauró el servicio.

**Diagnóstico:** el build pasaba; el crash era en el arranque. La causa raíz es que
**`requirements.txt` no tenía versiones fijas**: al reconstruir la imagen se
resolvieron versiones nuevas que rompieron dos cosas encadenadas.

1. **`greenlet` desapareció.** SQLAlchemy ≥2.1 ya no lo instala por defecto (solo vía
   el extra `[asyncio]`). Sin él, `alembic upgrade head` —que corre en el `CMD` del
   Dockerfile— muere con `ModuleNotFoundError: No module named 'greenlet'`.
2. **Al arreglar eso, apareció `psycopg`.** SQLAlchemy ≥2.1 resuelve la URL
   `postgresql://` al dialecto **psycopg3**, que no está instalado.
   Agravante: [scheduler.py:10](backend/api-backend/app/core/scheduler.py#L10) hacía
   `DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")`, un **no-op**,
   porque `DATABASE_URL` llega sin `+asyncpg` (ese sufijo lo añade
   `app/core/database.py:31` y solo para el engine async). Y como `main.py:38`
   importa `app.core.scheduler`, el `SQLAlchemyJobStore` se construye **siempre**,
   incluso con `CRON_EXTERNAL=true`.

**Dónde:**
- `backend/api-backend/requirements.txt` → `sqlalchemy[asyncio]` + `greenlet`
- `backend/api-backend/app/core/scheduler.py` → fuerza `postgresql+psycopg2://`

**Por qué importa:** era una **rotura latente**, no algo introducido por el cambio.
Cualquier rebuild de la imagen la habría expuesto. El redeploy solo la adelantó.

**Verificación:** deploy `f7a4de09` → `SUCCESS`; `/` y `/docs` en 200;
`POST /api/auth/token` → 401; `POST /internal/jobs/reminders` sin token → 401.

**Cómo se desplegó:** con `railway deployment up` (sube el código local), **no desde
git** — de ahí la tarea bloqueante #0.

---

### 2026-10-04 — Auditoría de infraestructura y costos (solo lectura)

**Qué:** inventario y medición de los tres proveedores de este proyecto.
**Dónde:** Railway, Vercel, Neon + probes HTTP + consultas SQL de lectura.
**Por qué:** optimización de gastos solicitada por el usuario.

**Hallazgos:**
- Backend ~$0.97/mes corriendo 24/7 con **cero tráfico HTTP** y **cero queries a BD por 15 días**.
- Frontend de producción **roto**: bundle apuntaba a `smartbooking-production-9cce.up.railway.app` (`404 Application not found`).
- Recordatorios **no se envían**: `CRON_EXTERNAL=true` sin cron externo.
- WhatsApp **inerte**: faltan `META_WABA_TOKEN` y `META_APP_SECRET`.
- Sentry **nunca inicializado**: `SENTRY_DSN` ausente.
- Última cita creada: **2026-08-29** (36 días sin actividad de negocio).

**Verificado:** `railway usage` (soft $8 / hard $15, uso $2.88, estimado $5.22);
Vercel `billing.plan = "hobby"`; Neon free tier.

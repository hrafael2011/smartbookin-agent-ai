# Quickstart: SmartBooking AI Baseline

## Requisitos

- Docker y Docker Compose.
- Variables en `.env` en la raíz del repo.
- Credenciales externas solo si se probarán canales reales: OpenAI, Meta WhatsApp, Telegram, SMTP, ngrok.

## Levantar Stack Local

```bash
docker compose up --build
```

Servicios relevantes (puertos por defecto en [docker-compose.yml](/docker-compose.yml)):

- Backend FastAPI (directo): `http://localhost:8000`
- OpenAPI (Swagger): `http://localhost:8000/docs` (también vía Nginx en `/docs`)
- Nginx (SPA + proxy `/api` y `/webhooks`): `http://localhost:8080`
- PostgreSQL local: host `localhost`, puerto `5435`

Si Docker falla con **port is already allocated** en `8000` u `8080`, definí en `.env` del repo:

- `API_BACKEND_HOST_PORT` (ej. `18008`)
- `NGINX_HOST_PORT` (ej. `18080`)

y volvé a levantar el stack.

## Webhooks Locales Con Ngrok

Requisitos en `.env` en la raíz:

- `AUTO_TOKEN_NGROK` (token de [ngrok](https://dashboard.ngrok.com/))
- `TELEGRAM_BOT_TOKEN` si vas a ejecutar `./scripts/telegram-webhook-sync.sh`

Todo en uno (stack + túnel + registro de webhook de Telegram):

```bash
./scripts/dev-stack-with-ngrok.sh
```

O manual:

```bash
docker compose up -d --build
docker compose --profile ngrok up -d
./scripts/telegram-webhook-sync.sh
```

El perfil ngrok expone Nginx, por lo que rutas como `/api` y `/webhooks/*` pasan por el proxy. Inspector del túnel: `http://127.0.0.1:4040`.

## Tests Útiles

Backend:

```bash
cd backend/api-backend
pytest
```

Frontend:

```bash
cd frontend
npm run lint
npm run build
npm run test:e2e
```

Verificación por perfiles:

```bash
./scripts/verify-mvp.sh backend-unit
./scripts/verify-mvp.sh backend-conversation
./scripts/verify-mvp.sh frontend
./scripts/verify-mvp.sh all
```

## Notas

- Si `.env` no tiene credenciales reales, las pruebas de integración con canales externos no aplican.
- La documentación histórica puede mencionar Django; para decisiones nuevas usar `specs/000-project-baseline/`.

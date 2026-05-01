# SmartBooking AI

Sistema de agendamiento inteligente para negocios de citas, con panel web administrativo y canales conversacionales por WhatsApp y Telegram.

## Fuente De Verdad

Este proyecto usa **GitHub Spec Kit** y desarrollo guiado por especificaciones.

Leer primero:

- `.specify/memory/constitution.md` — principios no negociables del proyecto.
- `specs/000-project-baseline/` — baseline del sistema actual.
- `specs/001-guided-menu-bot/` — próxima fase: bot con menú guiado híbrido.

Los documentos antiguos pueden contener historia del proyecto. Si contradicen `specs/000-project-baseline/`, la baseline tiene prioridad.

## Stack Actual

- Backend: FastAPI, SQLAlchemy async, Alembic, PostgreSQL.
- Frontend: React, Vite, TypeScript, Zustand, React Query, TailwindCSS.
- Canales: WhatsApp Cloud API y Telegram Bot API.
- IA: OpenAI para NLU/interpretación.
- Infra local: Docker Compose, Nginx, PostgreSQL, ngrok opcional.

## Entorno Local

```bash
docker compose up --build
```

Accesos principales (por defecto; si hay choque de puertos, ver `API_BACKEND_HOST_PORT` / `NGINX_HOST_PORT` en `.env`):

- Backend FastAPI: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- App vía Nginx: `http://localhost:8080`
- PostgreSQL local: `localhost:5435`

Más detalles (incluye ngrok y Telegram) en `specs/000-project-baseline/quickstart.md`.

## Flujo De Desarrollo

1. Definir o actualizar spec en `specs/`.
2. Crear o actualizar plan técnico.
3. Generar tasks.
4. Implementar desde tasks.
5. Validar con tests y actualizar documentación si cambia comportamiento.

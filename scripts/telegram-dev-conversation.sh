#!/usr/bin/env bash
# Ejecuta la herramienta de conversación simulada dentro del contenedor api-backend
# (misma DB y .env que producción local). Uso:
#   ./scripts/telegram-dev-conversation.sh in-process --reset --log-nlu --messages "/start TOKEN" "Ana"
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
docker compose exec -T api-backend python3 tools/telegram_conversation_dev.py "$@"

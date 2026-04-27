#!/usr/bin/env bash
# Levanta Postgres + API + front (Nginx) + contenedor ngrok y registra el webhook de Telegram.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

docker compose up -d --build
docker compose --profile ngrok up -d

echo "Esperando a que ngrok exponga la API en :4040..."
sleep 4
exec "$ROOT/scripts/telegram-webhook-sync.sh"

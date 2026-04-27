#!/usr/bin/env bash
# Configura el webhook de Telegram para apuntar a tu API detrás de ngrok.
#
# 1) Levantá la API en el puerto 8000 (uvicorn o docker compose con 8000 expuesto).
# 2) En otra terminal: ngrok http 8000
# 3) Copiá la URL https (ej. https://abc123.ngrok-free.app)
# 4) Ejecutá:
#    export TELEGRAM_BOT_TOKEN="tu_token"
#    ./scripts/dev-ngrok-telegram.sh https://abc123.ngrok-free.app
#
# Opcional: añadí la misma URL base a ALLOWED_ORIGINS en .env si el front
# llama al API desde otro origen (CORS).

set -euo pipefail
BASE="${1:-${NGROK_HTTPS_URL:-}}"
if [[ -z "${TELEGRAM_BOT_TOKEN:-}" ]]; then
  echo "Definí TELEGRAM_BOT_TOKEN (ej. en .env: source .env 2>/dev/null || true)"
  exit 1
fi
if [[ -z "$BASE" ]]; then
  echo "Uso: $0 https://TU_TUNEL.ngrok-free.app"
  echo "Variables: NGROK_HTTPS_URL o primer argumento."
  exit 1
fi
BASE="${BASE%/}"
WH_URL="${BASE}/webhooks/telegram"

echo "Registrando webhook: $WH_URL"
curl -sS -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
  --data-urlencode "url=${WH_URL}"

echo ""
echo ""
curl -sS "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getWebhookInfo" | python3 -m json.tool

#!/usr/bin/env bash
# Lee la URL HTTPS del túnel ngrok (API local :4040) y registra el webhook de Telegram.
# Requisitos: ngrok corriendo (p. ej. docker compose --profile ngrok up -d) y TELEGRAM_BOT_TOKEN en .env

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# Evitar source .env completo (líneas con espacios/caracteres raros)
if [[ -f "$ROOT/.env" ]]; then
  line="$(grep -E '^[[:space:]]*TELEGRAM_BOT_TOKEN=' "$ROOT/.env" | head -1 || true)"
  if [[ -n "$line" ]]; then
    TELEGRAM_BOT_TOKEN="${line#*=}"
    TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN#"${TELEGRAM_BOT_TOKEN%%[![:space:]]*}"}"
    TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN%"${TELEGRAM_BOT_TOKEN##*[![:space:]]}"}"
    TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN//\"/}"
  fi
fi

if [[ -z "${TELEGRAM_BOT_TOKEN:-}" ]]; then
  echo "Error: definí TELEGRAM_BOT_TOKEN en la raíz del repo (.env)"
  exit 1
fi

T=""
for _ in $(seq 1 45); do
  T="$(curl -fsS "http://127.0.0.1:4040/api/tunnels" 2>/dev/null | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    for tun in d.get('tunnels', []):
        u = tun.get('public_url') or ''
        if u.startswith('https://'):
            print(u)
            raise SystemExit(0)
except SystemExit:
    raise
except Exception:
    pass
" 2>/dev/null || true)"
  if [[ -n "$T" ]]; then
    break
  fi
  sleep 1
done

if [[ -z "$T" ]]; then
  echo "No se obtuvo URL del túnel en http://127.0.0.1:4040/api/tunnels"
  echo "Levantá ngrok, por ejemplo:"
  echo "  cd \"$ROOT\" && docker compose --profile ngrok up -d"
  exit 1
fi

BASE="${T%/}"
WH="${BASE}/webhooks/telegram"
echo "URL pública: $BASE"
echo "Registrando webhook Telegram → $WH"
curl -sS -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
  --data-urlencode "url=${WH}"
echo ""
echo ""
curl -sS "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getWebhookInfo" | python3 -m json.tool
echo ""
echo "Listo. Panel y API por el mismo host:"
echo "  $BASE/"
echo "  $BASE/docs   (OpenAPI / Swagger)"
echo "  $BASE/api/... (rutas REST bajo /api)"

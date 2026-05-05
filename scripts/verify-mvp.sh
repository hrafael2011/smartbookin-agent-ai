#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE="${1:-help}"

run_backend_tests() {
  (
    cd "$ROOT_DIR/backend/api-backend"
    if [ -x ".venv/bin/python" ]; then
      PYTHON_BIN=".venv/bin/python"
    elif [ -x "venv/bin/python" ]; then
      PYTHON_BIN="venv/bin/python"
    else
      PYTHON_BIN="python3"
    fi
    "$PYTHON_BIN" -m pytest "$@"
  )
}

run_frontend() {
  (
    cd "$ROOT_DIR/frontend"
    npm run lint
    npm run build
  )
}

run_e2e() {
  (
    cd "$ROOT_DIR/frontend"
    npm run test:e2e
  )
}

case "$PROFILE" in
  backend-unit)
    run_backend_tests \
      tests/test_time_parser.py \
      tests/test_schedule_logic.py \
      tests/test_state_machine.py \
      tests/test_sliding_window_limiter.py \
      tests/test_refresh_token_hash.py \
      tests/test_security_tokens.py \
      tests/test_channel_phone.py
    ;;
  backend-conversation)
    run_backend_tests \
      tests/test_orchestrator_e2e.py \
      tests/test_orchestrator_dates.py \
      tests/test_conversation_states.py \
      tests/test_booking_calendar_flow.py \
      tests/test_booking_confirmation_flow.py \
      tests/test_cancel_handler.py \
      tests/test_modify_slot_select.py \
      tests/test_telegram_display_name.py \
      tests/test_telegram_invite_token.py \
      tests/test_guided_menu_router.py \
      tests/test_idempotency.py \
      tests/test_webhook_endpoints_ci.py
    ;;
  backend-api)
    run_backend_tests \
      tests/test_security_tokens.py \
      tests/test_refresh_token_hash.py \
      tests/test_business_mvp_limit.py \
      tests/test_idempotency.py \
      tests/test_webhook_endpoints_ci.py \
      tests/test_schedule_logic.py
    ;;
  backend-owner)
    run_backend_tests \
      tests/test_webhook_endpoints_ci.py \
      tests/test_telegram_invite_token.py \
      tests/test_business_mvp_limit.py \
      tests/test_owner_channel_binding.py \
      tests/test_owner_command_router.py
    ;;
  backend-all)
    run_backend_tests
    ;;
  frontend)
    run_frontend
    ;;
  e2e)
    run_e2e
    ;;
  all)
    "$0" backend-all
    "$0" frontend
    "$0" e2e
    ;;
  help|--help|-h)
    cat <<'EOF'
Usage: ./scripts/verify-mvp.sh <profile>

Profiles:
  backend-unit           Pure backend unit tests
  backend-conversation   Orchestrator, handlers and webhook routing tests
  backend-api            Auth/security/API-oriented smoke tests
  backend-owner          Owner-channel related tests (expands as feature lands)
  backend-all            Full backend pytest suite
  frontend               Frontend lint + build
  e2e                    Playwright E2E
  all                    backend-all + frontend + e2e
EOF
    ;;
  *)
    echo "Unknown profile: $PROFILE" >&2
    echo "Run ./scripts/verify-mvp.sh help for options." >&2
    exit 2
    ;;
esac

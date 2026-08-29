"""Rate limits en memoria/archivo (Redis eliminado en fase 4 del MVP)."""
import json
import logging
import os
from datetime import datetime, timezone

from app.config import config
from app.core.sliding_window_limiter import SlidingWindowLimiter

logger = logging.getLogger(__name__)

_resend_memory = SlidingWindowLimiter(max_events=8, window_seconds=3600)
_tg_invite_memory = SlidingWindowLimiter(max_events=40, window_seconds=900)
_daily_memory = {}
_daily_file_path = os.getenv("RATE_LIMIT_STATE_FILE", "/tmp/smartbooking_daily_quotas.json")


async def allow_resend_verification(ip: str) -> bool:
    return _resend_memory.is_allowed(f"ip:{ip}")


async def allow_telegram_invite_fail(telegram_user_id: str) -> bool:
    return _tg_invite_memory.is_allowed(telegram_user_id)


def _today_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _mem_daily_increment(key: str) -> int:
    # Limpieza básica de días viejos.
    today = _today_key()
    stale = [k for k in _daily_memory if f":{today}:" not in k]
    for k in stale[:200]:
        _daily_memory.pop(k, None)
    _daily_memory[key] = int(_daily_memory.get(key, 0)) + 1
    return _daily_memory[key]


def _file_daily_increment(key: str) -> int:
    """
    Fallback persistente local cuando no hay Redis.
    Evita que el contador diario se pierda al reiniciar el proceso.
    """
    try:
        data = {}
        if os.path.exists(_daily_file_path):
            with open(_daily_file_path, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
        today = _today_key()
        data = {k: v for k, v in data.items() if f":{today}:" in k}
        data[key] = int(data.get(key, 0)) + 1
        os.makedirs(os.path.dirname(_daily_file_path), exist_ok=True)
        with open(_daily_file_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        return int(data[key])
    except Exception:
        return _mem_daily_increment(key)


async def consume_daily_quota(
    *,
    business_id: int,
    user_channel_id: str,
    is_ai_message: bool,
) -> dict:
    """
    Cuenta consumo diario por cliente-negocio.
    - total: cualquier mensaje del cliente
    - ai: sólo cuando el mensaje requiere NLU/IA
    """
    # Defensa del interruptor: sin IA activa ningún mensaje consume cuota de IA,
    # aunque un call-site futuro olvide gatear uses_ai en el router.
    is_ai_message = is_ai_message and config.ai_enabled
    if config.DISABLE_USAGE_LIMITS:
        return {"allowed": True, "total_count": None, "ai_count": None}

    day = _today_key()
    prefix = f"rl:tg_daily:{day}:b{business_id}:u{user_channel_id}"
    total_key = f"{prefix}:total"
    ai_key = f"{prefix}:ai"

    total_count = _file_daily_increment(total_key)
    if total_count > config.TG_DAILY_TOTAL_LIMIT:
        return {
            "allowed": False,
            "message": (
                "Hoy alcanzaste el límite de interacciones de este chat. "
                "Podés volver a intentar mañana. 🙏"
            ),
        }

    if not is_ai_message:
        return {"allowed": True, "total_count": total_count, "ai_count": None}

    ai_count = _file_daily_increment(ai_key)
    if ai_count > config.TG_DAILY_AI_LIMIT:
        return {
            "allowed": False,
            "message": (
                "Hoy llegaste al límite de consultas avanzadas. "
                "Podés usar el menú guiado (1-5) o volver mañana."
            ),
        }

    return {"allowed": True, "total_count": total_count, "ai_count": ai_count}

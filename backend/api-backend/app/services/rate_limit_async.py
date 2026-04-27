"""Rate limits: Redis (REDIS_URL) si está disponible; si no, memoria (por proceso)."""
import json
import logging
import os
import time
import secrets
from datetime import datetime, timezone

from app.config import config
from app.core.sliding_window_limiter import SlidingWindowLimiter

logger = logging.getLogger(__name__)

_resend_memory = SlidingWindowLimiter(max_events=8, window_seconds=3600)
_tg_invite_memory = SlidingWindowLimiter(max_events=40, window_seconds=900)
_daily_memory = {}
_daily_file_path = os.getenv("RATE_LIMIT_STATE_FILE", "/tmp/smartbooking_daily_quotas.json")

_redis_client = None


def _get_redis():
    global _redis_client
    if not config.REDIS_URL:
        return None
    if _redis_client is None:
        try:
            import redis.asyncio as redis_async

            _redis_client = redis_async.from_url(
                config.REDIS_URL,
                decode_responses=True,
            )
        except Exception as e:
            logger.warning("No se pudo inicializar Redis para rate limit: %s", e)
            return None
    return _redis_client


async def _sliding_redis_allow(key: str, max_events: int, window_sec: int):
    """None = Redis no disponible o error (usar fallback)."""
    r = _get_redis()
    if r is None:
        return None
    try:
        now = time.time()
        await r.zremrangebyscore(key, "-inf", now - window_sec)
        n = await r.zcard(key)
        if n >= max_events:
            return False
        member = f"{now}:{secrets.token_hex(8)}"
        await r.zadd(key, {member: now})
        await r.expire(key, int(window_sec) + 120)
        return True
    except Exception as e:
        logger.warning("Redis rate limit error, usando memoria: %s", e)
        return None


async def allow_resend_verification(ip: str) -> bool:
    rkey = f"rl:resend:{ip}"
    ok = await _sliding_redis_allow(rkey, 8, 3600)
    if ok is not None:
        return ok
    return _resend_memory.is_allowed(f"ip:{ip}")


async def allow_telegram_invite_fail(telegram_user_id: str) -> bool:
    rkey = f"rl:tg_inv_fail:{telegram_user_id}"
    ok = await _sliding_redis_allow(rkey, 40, 900)
    if ok is not None:
        return ok
    return _tg_invite_memory.is_allowed(telegram_user_id)


def _today_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


async def _redis_daily_increment(key: str):
    r = _get_redis()
    if r is None:
        return None
    try:
        n = await r.incr(key)
        ttl = await r.ttl(key)
        if ttl < 0:
            # 26h para cubrir desfases entre workers sin caer en persistencia indefinida.
            await r.expire(key, 26 * 3600)
        return int(n)
    except Exception as e:
        logger.warning("Redis daily counter error, usando memoria: %s", e)
        return None


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
    if config.DISABLE_USAGE_LIMITS:
        return {"allowed": True, "total_count": None, "ai_count": None}

    day = _today_key()
    prefix = f"rl:tg_daily:{day}:b{business_id}:u{user_channel_id}"
    total_key = f"{prefix}:total"
    ai_key = f"{prefix}:ai"

    redis_total = await _redis_daily_increment(total_key)
    total_count = redis_total if redis_total is not None else _file_daily_increment(total_key)
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

    redis_ai = await _redis_daily_increment(ai_key)
    ai_count = redis_ai if redis_ai is not None else _file_daily_increment(ai_key)
    if ai_count > config.TG_DAILY_AI_LIMIT:
        return {
            "allowed": False,
            "message": (
                "Hoy llegaste al límite de consultas avanzadas. "
                "Podés usar el menú guiado (1-5) o volver mañana."
            ),
        }

    return {"allowed": True, "total_count": total_count, "ai_count": ai_count}

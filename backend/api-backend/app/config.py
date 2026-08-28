"""
Configuración del Agent Service
"""
import os
from dotenv import load_dotenv

load_dotenv()


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    return value.lower() in ("1", "true", "yes")


class Config:
    """Configuración centralizada"""

    # OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = "gpt-4o-mini"  # Modelo optimizado para costo/rendimiento
    OPENAI_TEMPERATURE = 0.3  # Menos creativo, más preciso
    OPENAI_MAX_TOKENS = 500
    OPENAI_TIMEOUT = 10  # segundos

    # Redis eliminado en fase 4 del MVP: los rate limits viven en memoria/archivo
    CONVERSATION_TTL = 3600  # 1 hora en segundos

    # Django API
    DJANGO_API_BASE_URL = os.getenv("DJANGO_API_BASE_URL", "http://web-backend:8000")
    DJANGO_API_TIMEOUT = 30  # segundos

    # Meta WhatsApp
    META_WABA_TOKEN = os.getenv("META_WABA_TOKEN")
    META_APP_SECRET = os.getenv("META_APP_SECRET")
    META_VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN")
    META_PHONE_NUMBER_ID = os.getenv("META_PHONE_NUMBER_ID", "YOUR_PHONE_NUMBER_ID")
    META_API_VERSION = "v21.0"
    META_API_BASE_URL = f"https://graph.facebook.com/{META_API_VERSION}"

    # Telegram Bot (un solo bot multi-tenant; username sin @ para deep links)
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_API_BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
    TELEGRAM_BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "").lstrip("@")

    # Registro: si false (MVP), el registro activa la cuenta directamente
    # (reemplaza al antiguo AUTO_VERIFY_EMAIL, invertido)
    REQUIRE_EMAIL_VERIFICATION = _bool_env("REQUIRE_EMAIL_VERIFICATION", False)

    # ── Flags de poda MVP (fase 1): false = función diferida post-MVP ──
    # Canal de comandos del owner en Telegram (el dueño usa el panel web)
    OWNER_CHANNEL_ENABLED = _bool_env("OWNER_CHANNEL_ENABLED", False)
    # Waitlist con auto-oferta (cancelar solo cancela; sin job de expiración)
    WAITLIST_ENABLED = _bool_env("WAITLIST_ENABLED", False)

    # Sentry & Monitoring
    SENTRY_DSN = os.getenv("SENTRY_DSN")
    
    # CORS & Security
    ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")

    # Business ID mapping (número de WhatsApp -> business_id)
    # En producción esto vendría de la base de datos
    WHATSAPP_BUSINESS_MAPPING = {
        "18095551234": 1,
    }

    # Configuración de NLU
    MAX_CONTEXT_MESSAGES = 10  # Máximo de mensajes en contexto
    CONFIDENCE_THRESHOLD = 0.7  # Umbral de confianza para procesar intent

    # Rate limiting
    RATE_LIMIT_PER_MINUTE = 10  # Máximo 10 mensajes por minuto por usuario
    TG_DAILY_TOTAL_LIMIT = _int_env("TG_DAILY_TOTAL_LIMIT", 40)
    TG_DAILY_AI_LIMIT = _int_env("TG_DAILY_AI_LIMIT", 12)
    # true = sin cuota diaria (Telegram/WhatsApp) ni tope HTTP por IP (pruebas locales)
    DISABLE_USAGE_LIMITS = os.getenv("DISABLE_USAGE_LIMITS", "").lower() in (
        "1",
        "true",
        "yes",
    )

    # SMTP (verificación de correo)
    SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
    SMTP_PORT = _int_env("SMTP_PORT", 587)
    SMTP_USER = os.getenv("SMTP_USER", "").strip()
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").strip()
    SMTP_FROM = os.getenv("SMTP_FROM", "noreply@localhost").strip()
    SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() in ("1", "true", "yes")

    # URL del front para enlaces en correos (sin barra final)
    FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173").rstrip("/")

    # ── Cron externo (fase 4 MVP) ──
    # true = sin APScheduler en proceso; los jobs los dispara el cron externo (Railway)
    CRON_EXTERNAL = _bool_env("CRON_EXTERNAL", False)
    # Token para los endpoints internos /internal/jobs/* (Bearer)
    INTERNAL_CRON_TOKEN = os.getenv("INTERNAL_CRON_TOKEN", "").strip()
    # Zona horaria del negocio (scheduler y fechas locales)
    TIMEZONE = os.getenv("TIMEZONE", "America/Santo_Domingo")


config = Config()

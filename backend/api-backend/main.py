"""
Agent Service - NLU con GPT-4o-mini para WhatsApp Bot
"""
import logging
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException

import sentry_sdk
from fastapi.middleware.cors import CORSMiddleware
from app.config import config
from app.api import (
    auth,
    owners,
    businesses,
    services,
    customers,
    appointments,
    schedules,
    dashboard,
)
from app.services import db_service, whatsapp_client, conversation_manager
from app.services.background_tasks import (
    generate_daily_agenda,
    process_appointment_reminders,
    process_waitlist_expiration,
)
from app.services.telegram_inbound import process_telegram_update
from app.core.orchestrator import run_conversation_turn
from app.services.rate_limit_async import consume_daily_quota
from app.services.guided_menu_router import (
    execute_guided_route,
    route_guided_message,
)
from app.services.idempotency import should_process_channel_event
from app.core.scheduler import start_scheduler, shutdown_scheduler, scheduler

logger = logging.getLogger(__name__)

# Sentry initialization
if config.SENTRY_DSN:
    sentry_sdk.init(
        dsn=config.SENTRY_DSN,
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
    )

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start APScheduler and add jobs
    start_scheduler()
    
    # Run reminders every 30 minutes
    scheduler.add_job(process_appointment_reminders, 'interval', minutes=30, id='reminders_job', replace_existing=True)
    
    # Run waitlist expiration every hour
    scheduler.add_job(process_waitlist_expiration, 'interval', minutes=60, id='waitlist_job', replace_existing=True)
    
    # Run agenda generation daily at 8:00 AM
    scheduler.add_job(generate_daily_agenda, 'cron', hour=8, minute=0, id='agenda_job', replace_existing=True)
    
    yield
    
    # Shutdown: Stop scheduler
    shutdown_scheduler()

app = FastAPI(title="SmartBooking AI - Agent Service", lifespan=lifespan)

# Simple Rate Limiting State
# { "ip_address": [timestamp1, timestamp2, ...] }
rate_limit_records = {}
RATE_LIMIT_MAX_REQUESTS = 60  # 60 requests
RATE_LIMIT_WINDOW = 60        # per 60 seconds

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if config.DISABLE_USAGE_LIMITS:
        return await call_next(request)
    client_ip = request.client.host
    now = time.time()
    
    # Get current requests for this IP
    requests = rate_limit_records.get(client_ip, [])
    
    # Filter out old requests outside the window
    requests = [t for t in requests if now - t < RATE_LIMIT_WINDOW]
    
    if len(requests) >= RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")
    
    # Add current request
    requests.append(now)
    rate_limit_records[client_ip] = requests
    
    response = await call_next(request)
    return response

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Health check"""
    return {"status": "ok", "service": "api-backend"}


@app.get("/api", include_in_schema=False)
@app.get("/api/", include_in_schema=False)
async def api_root():
    """Evita 404 al abrir /api o /api/ en el navegador o al probar el túnel."""
    return {
        "service": "SmartBooking API",
        "docs": "/docs",
        "redoc": "/redoc",
        "openapi_json": "/openapi.json",
        "health": "/",
    }


app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(owners.router, prefix="/api/owners", tags=["Owners"])
app.include_router(businesses.router, prefix="/api/businesses", tags=["Businesses"])
app.include_router(services.router, prefix="/api/businesses", tags=["Services"])
app.include_router(customers.router, prefix="/api/businesses", tags=["Customers"])
app.include_router(appointments.router, prefix="/api/businesses", tags=["Appointments"])
app.include_router(schedules.router, prefix="/api", tags=["Schedules"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])


@app.get("/webhooks/whatsapp/verify")
async def verify_webhook(request: Request):
    """
    Verificación de webhook de Meta (GET)
    Meta envía: ?hub.mode=subscribe&hub.verify_token=...&hub.challenge=...
    """
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == config.META_VERIFY_TOKEN:
        return int(challenge)

    raise HTTPException(status_code=403, detail="Verification failed")


@app.post("/webhooks/telegram")
async def telegram_webhook(request: Request):
    """Webhook Telegram: un solo bot, tenant por vínculo usuario↔negocio."""
    try:
        payload = await request.json()
        return await process_telegram_update(payload)
    except Exception as e:
        print(f"Error en webhook telegram: {e}")
        return {"status": "error", "message": str(e)}


@app.post("/webhooks/whatsapp")
async def whatsapp_webhook(request: Request):
    """
    Webhook principal para recibir mensajes de WhatsApp

    Flow:
    1. Validar firma Meta
    2. Extraer mensaje
    3. Obtener contexto de conversación
    4. Procesar con NLU
    5. Ejecutar handler según intent
    6. Enviar respuesta por WhatsApp
    7. Guardar en contexto
    """
    try:
        # 1. Validar firma de Meta
        body = await request.body()
        signature = request.headers.get("X-Hub-Signature-256", "")

        if not whatsapp_client.validate_signature(body, signature):
            raise HTTPException(status_code=403, detail="Invalid signature")

        # 2. Parsear payload
        payload = await request.json()

        # 3. Extraer mensaje
        message_data = whatsapp_client.extract_message_from_webhook(payload)

        if not message_data:
            # No es un mensaje válido o es un status update
            return {"status": "ok"}

        phone_number = message_data["from"]
        message_text = message_data["text"]
        message_id = message_data["message_id"]

        # Marcar como leído
        await whatsapp_client.mark_as_read(
            message_id, message_data["business_phone_number_id"]
        )

        # 4. Mapear phone_number_id a business_id dinámicamente
        phone_number_id = message_data["business_phone_number_id"]
        business_info = await db_service.get_business_by_phone_id(phone_number_id)
        
        if not business_info:
            print(f"Business not found for phone_number_id: {phone_number_id}")
            return {"status": "error", "message": "Business not found"}
            
        business_id = business_info["id"]

        if not await should_process_channel_event(
            channel="whatsapp",
            business_id=business_id,
            user_key=phone_number,
            event_id=message_id,
        ):
            return {"status": "ok"}

        # 4. Obtener contexto y decidir ruta guiada antes de contar cuota IA.
        context = await conversation_manager.get_context(business_id, phone_number)
        decision = route_guided_message(message_text, context)

        quota = await consume_daily_quota(
            business_id=business_id,
            user_channel_id=phone_number,
            is_ai_message=decision.uses_ai,
        )
        if not quota["allowed"]:
            await whatsapp_client.send_text_message(to=phone_number, message=quota["message"])
            return {"status": "ok"}

        resp = await execute_guided_route(business_id, phone_number, decision, context)
        if resp:
            logger.info(
                "wa_route guided_router kind=%s business=%s user=%s",
                decision.kind,
                business_id,
                phone_number,
            )
            await conversation_manager.save_message(
                business_id, phone_number, "user", message_text
            )
            await whatsapp_client.send_text_message(to=phone_number, message=resp)
            await conversation_manager.save_message(
                business_id, phone_number, "assistant", resp
            )
            return {"status": "ok"}

        # 6–11. Turno conversacional unificado (orchestrator)
        logger.info(
            "wa_route pass_through kind=%s uses_ai=%s business=%s user=%s",
            decision.kind,
            decision.uses_ai,
            business_id,
            phone_number,
        )
        response_text = await run_conversation_turn(business_id, phone_number, message_text)
        logger.info("wa_route ai_pipeline business=%s user=%s", business_id, phone_number)
        await whatsapp_client.send_text_message(to=phone_number, message=response_text)
        return {"status": "ok"}

    except Exception as e:
        print(f"Error en webhook: {e}")
        return {"status": "error", "message": str(e)}

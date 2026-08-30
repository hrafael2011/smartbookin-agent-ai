import html
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy.future import select
from app.core.database import AsyncSessionLocal
from app.models import Appointment, Customer, Service, WaitlistEntry, Business
from app.services import db_service
from app.services.telegram_client import telegram_client
from app.services.whatsapp_client import WhatsAppAPIError, whatsapp_client
from app.utils.channel_phone import normalize_channel_phone
from app.utils.date_parse import format_date_human_es

logger = logging.getLogger(__name__)

REMINDER_CADENCE_MINUTES = 15


def _reminder_windows(now: datetime) -> dict:
    """Ventanas de 24h y 2h (ancho = cadencia ±15 min) en el convenio wall-clock-as-UTC."""
    return {
        "start_24h": now + timedelta(hours=23, minutes=60 - REMINDER_CADENCE_MINUTES),
        "end_24h": now + timedelta(hours=24, minutes=REMINDER_CADENCE_MINUTES),
        "start_2h": now + timedelta(hours=1, minutes=60 - REMINDER_CADENCE_MINUTES),
        "end_2h": now + timedelta(hours=2, minutes=REMINDER_CADENCE_MINUTES),
    }

async def process_appointment_reminders():
    """Send 24h and 2h reminders (precisión ±15 min, convenio wall-clock-as-UTC)."""
    logger.info("Running appointment reminders job...")
    now = db_service._upcoming_now()
    windows = _reminder_windows(now)

    async with AsyncSessionLocal() as db:
        # 24h reminders
        await _send_window_reminders(db, windows["start_24h"], windows["end_24h"], "24h", "reminder_24h_sent")
        # 2h reminders
        await _send_window_reminders(db, windows["start_2h"], windows["end_2h"], "2h", "reminder_2h_sent")


async def _send_window_reminders(db, window_start, window_end, label, flag_attr):
    result = await db.execute(
        select(Appointment, Customer, Service, Business)
        .join(Customer, Appointment.customer_id == Customer.id, isouter=True)
        .join(Service, Appointment.service_id == Service.id, isouter=True)
        .join(Business, Appointment.business_id == Business.id, isouter=True)
        .filter(
            Appointment.status.in_(["P", "C"]),
            Appointment.date >= window_start,
            Appointment.date <= window_end,
            getattr(Appointment, flag_attr) == False,
        )
    )
    for appt, customer, service, business in result.all():
        phone = (customer.phone_number if customer else "") or ""
        if phone.startswith("tg:"):
            chat_id = phone[3:]
            message = (
                "📅 <b>Recordatorio de tu cita</b>\n\n"
                f"📍 {html.escape((business.name if business else '') or 'Negocio')}\n"
                f"✂️ {html.escape(service.name if service else 'Servicio')}\n"
                f"📅 {format_date_human_es(appt.date.strftime('%Y-%m-%d'))}\n"
                f"⏰ {appt.date.strftime('%I:%M %p').lstrip('0')}\n"
            )
            if business and business.address:
                message += f"    {html.escape(business.address)}\n"
            await _attempt_send(
                db, appt, flag_attr, label, chat_id,
                lambda: telegram_client.send_text_message(chat_id=chat_id, message=message),
            )
        elif phone:
            await _send_whatsapp_reminder(db, appt, customer, service, business, label, flag_attr, phone)
        else:
            logger.info("reminder_skip_no_phone business=%s appt=%s", appt.business_id, appt.id)


async def _attempt_send(db, appt, flag_attr, label, chat_desc, send_fn):
    """Envío por fila con savepoint: fallo → se revierte solo esa fila y se
    reintenta en la próxima pasada; el flag solo se marca si el envío llega bien.
    (Un rollback full expiraría todas las filas cargadas y el siguiente acceso a
    customer.phone_number lanzaría MissingGreenlet, matando el job.)"""
    try:
        async with db.begin_nested():
            await send_fn()
            setattr(appt, flag_attr, True)
    except WhatsAppAPIError as e:
        if e.code == 133010:
            # Número no registrado en WhatsApp: nunca llegará; marcar el flag
            # para no reintentar eternamente cada 15 min.
            setattr(appt, flag_attr, True)
            logger.info("reminder_wa_unregistered appt=%s phone=%s", appt.id, chat_desc)
            try:
                await db.commit()
            except Exception:
                logger.exception("reminder_send_failed kind=%s appt=%s chat=%s", label, appt.id, chat_desc)
                try:
                    await db.rollback()
                except Exception:
                    pass
            return
        logger.warning("reminder_wa_api_error code=%s appt=%s phone=%s", e.code, appt.id, chat_desc)
        return
    except Exception:
        logger.exception("reminder_send_failed kind=%s appt=%s chat=%s", label, appt.id, chat_desc)
        return
    try:
        await db.commit()
    except Exception:
        # Fallo fuera del savepoint (commit): la sesión queda comprometida;
        # rollback full + return, y el resto de la corrida se reintenta en la
        # próxima pasada de 15 min — sin pérdida permanente.
        logger.exception("reminder_send_failed kind=%s appt=%s chat=%s", label, appt.id, chat_desc)
        try:
            await db.rollback()
        except Exception:
            pass
        return
    logger.info(
        "reminder_sent kind=%s appt=%s chat=%s business=%s",
        label, appt.id, chat_desc, appt.business_id,
    )


async def _send_whatsapp_reminder(db, appt, customer, service, business, label, flag_attr, phone):
    """Recordatorio por plantilla de Utilidad aprobada (canal principal del producto)."""
    waba = getattr(business, "whatsapp_phone_number_id", None) if business else None
    if not waba:
        logger.info("reminder_skip_no_waba business=%s appt=%s phone=%s", appt.business_id, appt.id, phone[:20])
        return
    to = normalize_channel_phone(phone)
    config_json = getattr(business, "config_json", None) or {}
    template_name = config_json.get("wa_template") or "appointment_reminder"
    params = [
        getattr(customer, "name", "") or "" if customer else "",
        service.name if service else "Servicio",
        format_date_human_es(appt.date.strftime("%Y-%m-%d")),
        appt.date.strftime("%I:%M %p").lstrip("0"),
        (business.name if business else "") or "Negocio",
        (business.address if business else "") or "",
    ]
    await _attempt_send(
        db, appt, flag_attr, label, to,
        lambda: whatsapp_client.send_template_message(
            to=to,
            template_name=template_name,
            language_code="es",
            body_parameters=params,
            button_payloads={
                0: f"reminder_ack_{appt.id}",
                1: f"modify_appt_{appt.id}",
                2: f"cancel_appt_{appt.id}",
            },
            phone_number_id=waba,
        ),
    )

async def process_waitlist_expiration():
    """Expire waitlist entries that haven't been fulfilled"""
    logger.info("Running waitlist expiration job...")
    async with AsyncSessionLocal() as db:
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(WaitlistEntry).filter(
                WaitlistEntry.status == "waiting",
                WaitlistEntry.date < now
            )
        )
        expired_entries = result.scalars().all()
        for entry in expired_entries:
            entry.status = "expired"
        
        if expired_entries:
            await db.commit()
            logger.info(f"Expired {len(expired_entries)} waitlist entries.")

async def generate_daily_agenda():
    """Generate and send daily agenda to business owners"""
    logger.info("Running daily agenda generation job...")
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Business).filter(Business.daily_notification_enabled == True))
        businesses = result.scalars().all()
        # Logic to fetch today's appointments and send via WhatsApp/Email to the owner.

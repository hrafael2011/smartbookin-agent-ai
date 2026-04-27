"""Webhook Telegram: un solo bot, tenant por vínculo usuario↔negocio."""
import logging
import re
from typing import Optional

from app.handlers.cancel_handler import handle_cancel_appointment
from app.handlers.check_handler import handle_check_appointment
from app.handlers.modify_handler import handle_modify_appointment
from app.handlers.business_info_handler import handle_business_info
from app.services import db_service
from app.services.conversation_manager import conversation_manager
from app.services.telegram_client import telegram_client
from app.services.telegram_link_service import (
    clear_user_binding,
    get_binding_business_id,
    mark_first_telegram_contact,
    resolve_invite_token,
    set_user_binding,
    tg_chat_key,
)
from app.utils.conversation_routing import (
    classify_route,
    guided_menu,
    is_affirmative,
    is_reserved_customer_display_name,
    parse_menu_choice,
)
from app.services.no_services_nlu import NO_SERVICES_GENERIC
from app.core.orchestrator import run_conversation_turn

logger = logging.getLogger(__name__)

async def _reply_invalid_invite_attempt(chat_id: str, telegram_user_id: str) -> None:
    from app.services.rate_limit_async import allow_telegram_invite_fail

    if not await allow_telegram_invite_fail(telegram_user_id):
        await telegram_client.send_text_message(
            chat_id=chat_id,
            message=(
                "Demasiados intentos con códigos inválidos. "
                "Esperá unos minutos y volvé a intentar."
            ),
        )
        return
    await telegram_client.send_text_message(
        chat_id=chat_id,
        message="El enlace o código no es válido. Pedile al negocio uno nuevo.",
    )


def _command_base(text: str) -> str:
    if not text:
        return ""
    first = text.strip().split()[0]
    return first.split("@", 1)[0].lower()


async def _send_welcome_for_business(business_id: int, chat_id: str) -> None:
    info = await db_service.get_business(business_id)
    name = info.get("name") or "el negocio"
    msg = (
        f"¡Hola! Estás en el chat de <b>{name}</b>.\n\n"
        "Podés pedir turnos, consultar o cancelar citas con lenguaje natural."
    )
    await telegram_client.send_text_message(chat_id=chat_id, message=msg)
    user_key = tg_chat_key(chat_id)
    await _after_welcome_onboarding(business_id, user_key, chat_id)


async def _after_welcome_onboarding(business_id: int, user_key: str, chat_id: str) -> None:
    """Tras la bienvenida: si ya hay nombre en BD, sincroniza contexto; si no, pide nombre."""
    cust = await db_service.get_customer_by_channel(business_id, user_key)
    if cust and cust.get("name") and str(cust["name"]).strip():
        nm = str(cust["name"]).strip()
        if is_reserved_customer_display_name(nm):
            await conversation_manager.update_context(
                business_id, user_key, {"state": "awaiting_telegram_display_name"}
            )
            await telegram_client.send_text_message(
                chat_id=chat_id,
                message=(
                    "Para dirigirme bien, ¿me escribís cómo querés que te llame? "
                    "Puede ser solo tu nombre o como preferís (hasta cuatro palabras)."
                ),
            )
            return
        await conversation_manager.set_customer_info(
            business_id, user_key, cust["id"], nm
        )
        await conversation_manager.update_context(business_id, user_key, {"state": "idle"})
        await telegram_client.send_text_message(
            chat_id=chat_id,
            message=guided_menu(nm, returning=True),
        )
        return
    await conversation_manager.update_context(
        business_id, user_key, {"state": "awaiting_telegram_display_name"}
    )
    await telegram_client.send_text_message(
        chat_id=chat_id,
        message=(
            "Para continuar con gusto, ¿me podría compartir su nombre, por favor? "
            "Puede escribir solo su nombre o como prefiere que le llame 😊"
        ),
    )


def _is_plausible_display_name(text: str) -> bool:
    t = text.strip()
    if len(t) < 2 or len(t) > 80:
        return False
    if len(t.split()) > 4:
        return False
    if _CODE_LIKE.match(t):
        return False
    if t.startswith("/"):
        return False
    if is_reserved_customer_display_name(t):
        return False
    return True


async def _handle_guided_menu_choice(
    business_id: int,
    user_key: str,
    message_text: str,
    context: dict,
) -> Optional[str]:
    choice = parse_menu_choice(message_text)
    if not choice:
        return None

    if choice == "menu":
        return guided_menu(context.get("customer_name") or "")

    if choice == "1":
        services = await db_service.get_business_services(business_id)
        if not services:
            return NO_SERVICES_GENERIC
        services_text = "\n".join(
            [f"  • {s['name']} (${s['price']}, {s['duration_minutes']} min)" for s in services]
        )
        await conversation_manager.update_context(
            business_id,
            user_key,
            {"current_intent": "book_appointment", "state": "awaiting_service", "pending_data": {}},
        )
        return f"Perfecto. ¿Qué servicio querés reservar?\n\n{services_text}"

    if choice == "2":
        return await handle_check_appointment({}, context)

    if choice == "3":
        await conversation_manager.update_context(
            business_id,
            user_key,
            {"current_intent": "modify_appointment", "state": "awaiting_appointment_selection_modify"},
        )
        return "Perfecto. Decime qué cita querés cambiar y te ayudo."

    if choice == "4":
        await conversation_manager.update_context(
            business_id,
            user_key,
            {"current_intent": "cancel_appointment", "state": "awaiting_appointment_selection"},
        )
        return "Entendido. Decime cuál cita querés cancelar."

    # choice == "5"
    return await handle_business_info(business_id)


async def _handle_telegram_display_name_capture(
    business_id: int, user_key: str, message_text: str
) -> str:
    if not _is_plausible_display_name(message_text):
        return (
            "No pude tomar eso como nombre. Escribí cómo querés que te llame "
            "(por ejemplo <b>María</b> o <b>Juan Pérez</b>), hasta cuatro palabras."
        )
    display = message_text.strip().title()
    result = await db_service.find_or_create_customer(business_id, user_key, display)
    customer = result["customer"]
    await conversation_manager.set_customer_info(
        business_id, user_key, customer["id"], customer["name"] or display
    )
    await conversation_manager.update_context(business_id, user_key, {"state": "idle"})
    nm = customer["name"] or display
    return (
        f"¡Gracias, <b>{nm}</b>! Ya te tengo presente. "
        "Decime qué necesitás: turno, consulta de citas o lo que prefieras."
    )


async def _run_nlu_pipeline(business_id: int, user_key: str, message_text: str) -> str:
    return await run_conversation_turn(business_id, user_key, message_text)


# Códigos de invitación reales son ~24+ chars (secrets.token_urlsafe). Mínimo 16 evita
# rechazar nombres de 8 letras (ej. "Hendrick") que antes coincidían con {8,48}.
_CODE_LIKE = re.compile(r"^[A-Za-z0-9_-]{16,48}$")


async def process_telegram_update(payload: dict) -> dict:
    try:
        message_data = telegram_client.extract_message_from_webhook(payload)
        if not message_data:
            logger.info(
                "telegram update ignorado (sin texto/callback/edit): keys=%s",
                list(payload.keys()) if isinstance(payload, dict) else type(payload),
            )
            return {"status": "ok"}

        chat_id = message_data["from"]
        telegram_user_id = chat_id
        raw_text = message_data.get("text") or ""
        message_text = raw_text
        if message_data.get("type") == "interactive" and message_data.get("button_payload"):
            message_text = str(message_data.get("button_payload") or "")

        cmd = _command_base(raw_text)

        if cmd in ("/cambiar", "/switch"):
            user_key = tg_chat_key(chat_id)
            await conversation_manager.delete_all_contexts_for_phone_number(user_key)
            await clear_user_binding(telegram_user_id)
            await telegram_client.send_text_message(
                chat_id=chat_id,
                message=(
                    "Listo. Enviá el <b>código</b> del negocio o abrí el enlace "
                    "con el botón <b>Iniciar</b> que te compartieron."
                ),
            )
            return {"status": "ok"}

        if cmd == "/start":
            parts = raw_text.strip().split(maxsplit=1)
            arg = parts[1].strip() if len(parts) > 1 else ""
            if arg:
                bid = await resolve_invite_token(arg)
                if bid:
                    await set_user_binding(telegram_user_id, bid)
                    await mark_first_telegram_contact(bid)
                    await _send_welcome_for_business(bid, chat_id)
                else:
                    await _reply_invalid_invite_attempt(chat_id, telegram_user_id)
            else:
                # Telegram a menudo manda solo "/start" (sin payload) al reabrir el chat;
                # si ya hay vínculo, repetimos bienvenida en lugar de pedir el enlace otra vez.
                existing_bid = await get_binding_business_id(telegram_user_id)
                if existing_bid is not None:
                    await _send_welcome_for_business(existing_bid, chat_id)
                else:
                    await telegram_client.send_text_message(
                        chat_id=chat_id,
                        message=(
                            "¡Hola! Para hablar con un negocio necesitás su enlace o código.\n\n"
                            "Si ya lo tenés, tocá <b>Iniciar</b> en el enlace o escribí el código aquí."
                        ),
                    )
            return {"status": "ok"}

        business_id: Optional[int] = await get_binding_business_id(telegram_user_id)
        user_key = tg_chat_key(chat_id)

        if business_id is not None:
            ctx_onb = await conversation_manager.get_context(business_id, user_key)
            if ctx_onb.get("state") == "awaiting_telegram_display_name":
                cust_sync = await db_service.get_customer_by_channel(business_id, user_key)
                if cust_sync and cust_sync.get("name") and str(cust_sync["name"]).strip():
                    await conversation_manager.set_customer_info(
                        business_id,
                        user_key,
                        cust_sync["id"],
                        str(cust_sync["name"]).strip(),
                    )
                    await conversation_manager.update_context(
                        business_id, user_key, {"state": "idle"}
                    )
                    ctx_onb = await conversation_manager.get_context(business_id, user_key)
            if ctx_onb.get("state") == "awaiting_telegram_display_name":
                text_in = (raw_text or "").strip()
                if text_in and _command_base(raw_text) not in ("/start", "/cambiar", "/switch"):
                    resp = await _handle_telegram_display_name_capture(
                        business_id, user_key, text_in
                    )
                    await conversation_manager.save_message(
                        business_id, user_key, "user", text_in
                    )
                    await conversation_manager.save_message(
                        business_id, user_key, "assistant", resp
                    )
                    await telegram_client.send_text_message(chat_id=chat_id, message=resp)
                    return {"status": "ok"}

        if business_id is not None and not (message_text or "").strip():
            await telegram_client.send_text_message(
                chat_id=chat_id,
                message="Por ahora solo puedo leer mensajes de texto. Escribime en texto, por favor.",
            )
            return {"status": "ok"}

        if business_id is not None:
            from app.services.rate_limit_async import consume_daily_quota

            quota = await consume_daily_quota(
                business_id=business_id,
                user_channel_id=telegram_user_id,
                is_ai_message=classify_route(message_text) == "ai",
            )
            if not quota["allowed"]:
                logger.info(
                    "tg_quota_blocked business=%s user=%s",
                    business_id,
                    telegram_user_id,
                )
                await telegram_client.send_text_message(
                    chat_id=chat_id,
                    message=quota["message"],
                )
                return {"status": "ok"}

            ctx = await conversation_manager.get_context(business_id, user_key)
            last_assistant = ""
            for msg in reversed(ctx.get("recent_messages", [])):
                if msg.get("role") == "assistant":
                    last_assistant = str(msg.get("content") or "").lower()
                    break
            if (
                ctx.get("state", "idle") == "idle"
                and is_affirmative(message_text)
                and ("agendar una" in last_assistant or "agendar" in last_assistant)
            ):
                guided = await _handle_guided_menu_choice(
                    business_id, user_key, "1", ctx
                )
                if guided:
                    logger.info("tg_route yes_to_booking business=%s user=%s", business_id, telegram_user_id)
                    await telegram_client.send_text_message(chat_id=chat_id, message=guided)
                    return {"status": "ok"}
            # Importante: si hay un flujo activo, no consumir números como menú global.
            if ctx.get("state", "idle") == "idle":
                guided = await _handle_guided_menu_choice(
                    business_id, user_key, message_text, ctx
                )
                if guided:
                    logger.info("tg_route guided_menu_choice business=%s user=%s", business_id, telegram_user_id)
                    await telegram_client.send_text_message(chat_id=chat_id, message=guided)
                    return {"status": "ok"}
            if classify_route(message_text) == "menu" and ctx.get("state", "idle") == "idle":
                logger.info("tg_route guided_menu_random business=%s user=%s", business_id, telegram_user_id)
                await telegram_client.send_text_message(
                    chat_id=chat_id,
                    message=guided_menu(ctx.get("customer_name") or ""),
                )
                return {"status": "ok"}

        if business_id is None:
            candidate = raw_text.strip()
            if _CODE_LIKE.match(candidate):
                bid = await resolve_invite_token(candidate)
                if bid:
                    await set_user_binding(telegram_user_id, bid)
                    await mark_first_telegram_contact(bid)
                    await _send_welcome_for_business(bid, chat_id)
                    return {"status": "ok"}
                await _reply_invalid_invite_attempt(chat_id, telegram_user_id)
                return {"status": "ok"}
            await telegram_client.send_text_message(
                chat_id=chat_id,
                message=(
                    "Todavía no estás vinculado a un negocio. "
                    "Usá el enlace que te compartieron o escribí el código del local.\n\n"
                    "Para cambiar de negocio más tarde: /cambiar"
                ),
            )
            return {"status": "ok"}

        response_text = await _run_nlu_pipeline(business_id, user_key, message_text)
        logger.info("tg_route ai_pipeline business=%s user=%s", business_id, telegram_user_id)
        await telegram_client.send_text_message(chat_id=chat_id, message=response_text)
        return {"status": "ok"}

    except Exception as e:
        print(f"Error en telegram_inbound: {e}")
        return {"status": "error", "message": str(e)}

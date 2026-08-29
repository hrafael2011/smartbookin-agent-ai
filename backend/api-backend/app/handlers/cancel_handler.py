"""
Handler para el intent cancel_appointment
"""
import logging
import re
from datetime import datetime
from typing import Dict
from app.core.response_builder import BotReply
from app.services import db_service
from app.services.conversation_manager import conversation_manager
from app.utils import telegram_ui
from app.utils.conversation_routing import (
    is_affirmative,
    is_negative_reply,
    parse_menu_choice,
)

logger = logging.getLogger(__name__)


def _wants_menu(text: str) -> bool:
    t = str(text or "").strip().lower()
    if parse_menu_choice(t) == "menu":
        return True
    return any(
        phrase in t
        for phrase in (
            "menu de inicio",
            "menú de inicio",
            "menu inicial",
            "menú inicial",
            "mostrar menu",
            "mostrar menú",
            "ver menu",
            "ver menú",
            "menu principal",
            "menú principal",
            "quiero el menu",
            "quiero el menú",
            "muestres el menu",
            "muestres el menú",
        )
    )


def _wants_exit_cancel_selection(text: str) -> bool:
    t = str(text or "").strip().lower()
    if is_negative_reply(t):
        return True
    return any(
        phrase in t
        for phrase in (
            "ninguna",
            "ninguno",
            "ninguna cita",
            "por el momento ninguna",
            "por ahora ninguna",
            "ya no quiero cancelar",
            "no quiero cancelar",
            "mejor no",
            "dejalo así",
            "déjalo así",
            "olvidalo",
            "olvídalo",
        )
    )


async def handle_cancel_appointment(nlu_result: Dict, context: Dict) -> str:
    """
    Maneja la cancelación de citas

    Flow:
    1. Obtener citas futuras del cliente
    2. Si tiene solo 1, confirmar cancelación
    3. Si tiene múltiples, pedir que elija cuál
    4. Cancelar la cita (la waitlist con auto-oferta está diferida post-MVP, flag WAITLIST_ENABLED)

    Args:
        nlu_result: Resultado del NLU Engine
        context: Contexto de conversación

    Returns:
        Mensaje de respuesta
    """
    business_id = context["business_id"]
    phone_number = context["phone_number"]
    customer_id = context.get("customer_id")
    customer_name = context.get("customer_name", "Cliente")
    pending_data = context.get("pending_data", {})
    current_state = context.get("state", "idle")

    if not customer_id:
        return BotReply(
            "No tienes citas registradas para cancelar.",
            keyboard=telegram_ui.with_footer([]),
        )

    try:
        # Obtener citas futuras
        appointments = await db_service.get_customer_appointments(
            customer_id=customer_id,
            upcoming=True
        )

        if not appointments:
            return BotReply(
                "No tienes citas próximas para cancelar. ¿Te gustaría agendar una?",
                keyboard=telegram_ui.with_footer(
                    [[{"text": "📅 Agendar cita", "callback_data": "menu_agendar"}]]
                ),
            )

        # Caso 1: Solo tiene 1 cita
        if len(appointments) == 1:
            appt = appointments[0]

            # Verificar si ya estamos esperando confirmación
            if current_state == "awaiting_cancel_confirmation":
                raw = (nlu_result.get("_raw_user_text") or "").strip()
                t = raw.lower()

                wants_no = is_negative_reply(raw)
                wants_yes = (not wants_no) and (
                    is_affirmative(raw)
                    or (
                        len(t) <= 36
                        and any(
                            w in t
                            for w in (
                                "confirmo",
                                "confirmar",
                                "dale",
                                "ok",
                                "yes",
                                "claro",
                                "adelante",
                            )
                        )
                    )
                )

                if wants_no:
                    await conversation_manager.clear_pending_data(business_id, phone_number)
                    await conversation_manager.mark_main_menu(business_id, phone_number)
                    return telegram_ui.main_menu_reply("Entendido, tu cita se mantiene.", customer_name)

                if wants_yes:
                    await db_service.cancel_appointment(
                        appointment_id=appt["id"],
                        notes="Cancelado por el cliente vía Telegram",
                    )
                    logger.info(
                        "appointment_cancelled business=%s user=%s customer=%s appointment=%s",
                        business_id,
                        phone_number,
                        customer_id,
                        appt["id"],
                    )

                    await conversation_manager.clear_pending_data(business_id, phone_number)
                    await conversation_manager.mark_main_menu(business_id, phone_number)

                    return telegram_ui.main_menu_reply("✅ Tu cita ha sido cancelada exitosamente.", customer_name)

                return BotReply(
                    "No entendí. Tocá <b>✅ Sí, cancelar</b> o <b>❌ No, mantener</b>.",
                    keyboard=telegram_ui.with_footer(telegram_ui.cancel_confirm_buttons()),
                )

            # Primera vez, pedir confirmación
            start_at = datetime.fromisoformat(appt['start_at'].replace('Z', '+00:00'))
            date_str = start_at.strftime("%A %d de %B")
            time_str = start_at.strftime("%I:%M %p")
            service_name = appt.get('service_name', 'Servicio')

            # Guardar en pending_data
            await conversation_manager.update_context(
                business_id,
                phone_number,
                {
                    "current_intent": "cancel_appointment",
                    "state": "awaiting_cancel_confirmation",
                    "pending_data": {"appointment_id": appt['id']}
                }
            )

            return BotReply(
                f"Tu cita:\n"
                f"📅 {date_str}\n"
                f"⏰ {time_str}\n"
                f"✂️ {service_name}\n\n"
                "¿Confirmás que querés cancelarla?",
                keyboard=telegram_ui.with_footer(telegram_ui.cancel_confirm_buttons()),
            )

        # Caso 2: Tiene múltiples citas, debe elegir
        if current_state == "awaiting_appointment_selection":
            # El cliente seleccionó una cita
            selection = nlu_result.get("entities", {}).get("appointment_number")

            try:
                raw = (nlu_result.get("_raw_user_text") or "").strip()
                if _wants_menu(raw):
                    await conversation_manager.clear_pending_data(business_id, phone_number)
                    await conversation_manager.mark_main_menu(business_id, phone_number)
                    return telegram_ui.guided_menu_reply(customer_name)
                if _wants_exit_cancel_selection(raw):
                    await conversation_manager.clear_pending_data(business_id, phone_number)
                    return BotReply(
                        "Perfecto, no cancelé ninguna cita. ¿Necesitás algo más?",
                        keyboard=telegram_ui.with_footer([]),
                    )

                index = None
                if isinstance(selection, str) and selection.isdigit():
                    index = int(selection) - 1
                elif isinstance(selection, int):
                    index = selection - 1
                elif raw.isdigit():
                    index = int(raw) - 1
                else:
                    m = re.search(r"\b([1-9])\b", raw)
                    if m:
                        index = int(m.group(1)) - 1
                    else:
                        return BotReply(
                            "No entendí cuál cita querés cancelar. Elegí una de la lista:",
                            keyboard=telegram_ui.with_footer(
                                telegram_ui.appointment_buttons(appointments, prefix="cancel_appt")
                            ),
                        )

                if 0 <= index < len(appointments):
                    selected_appt = appointments[index]

                    # Pedir confirmación
                    start_at = datetime.fromisoformat(selected_appt['start_at'].replace('Z', '+00:00'))
                    date_str = start_at.strftime("%A %d de %B")
                    time_str = start_at.strftime("%I:%M %p")
                    service_name = selected_appt.get('service_name', 'Servicio')

                    # Guardar en pending_data
                    await conversation_manager.update_context(
                        business_id,
                        phone_number,
                        {
                            "current_intent": "cancel_appointment",
                            "state": "awaiting_cancel_confirmation",
                            "pending_data": {"appointment_id": selected_appt['id']}
                        }
                    )

                    return BotReply(
                        f"Vas a cancelar:\n"
                        f"📅 {date_str}\n"
                        f"⏰ {time_str}\n"
                        f"✂️ {service_name}\n\n"
                        "¿Confirmás la cancelación?",
                        keyboard=telegram_ui.with_footer(telegram_ui.cancel_confirm_buttons()),
                    )

                else:
                    return BotReply(
                        "Elegí una cita de la lista para cancelar:",
                        keyboard=telegram_ui.with_footer(
                            telegram_ui.appointment_buttons(appointments, prefix="cancel_appt")
                        ),
                    )

            except Exception as e:
                return BotReply(
                    "No entendí cuál cita querés cancelar. Elegí una de la lista:",
                    keyboard=telegram_ui.with_footer(
                        telegram_ui.appointment_buttons(appointments, prefix="cancel_appt")
                    ),
                )

        # Primera vez con múltiples citas, listar como botones
        lines = [f"Tienes {len(appointments)} citas próximas. ¿Cuál querés cancelar?"]

        # Guardar estado
        await conversation_manager.update_context(
            business_id,
            phone_number,
            {
                "current_intent": "cancel_appointment",
                "state": "awaiting_appointment_selection",
                "pending_data": {"appointments": [a['id'] for a in appointments]}
            }
        )

        return BotReply(
            "\n".join(lines),
            keyboard=telegram_ui.with_footer(
                telegram_ui.appointment_buttons(appointments[:5], prefix="cancel_appt")
            ),
        )

    except Exception:
        logger.exception("cancel_flow_failed business=%s user=%s customer=%s", business_id, phone_number, customer_id)
        return BotReply(
            "Hubo un problema procesando tu solicitud. Por favor intenta de nuevo.",
            keyboard=telegram_ui.with_footer([]),
        )

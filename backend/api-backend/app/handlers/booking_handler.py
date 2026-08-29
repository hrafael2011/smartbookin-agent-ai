"""
Handler para el intent book_appointment
"""
import logging
import re
from datetime import date as date_type, timedelta
from typing import Dict, List
from app.core.response_builder import BotReply
from app.services import db_service
from app.services.conversation_manager import conversation_manager
from app.utils import telegram_ui
from app.utils.date_parse import format_date_human_es
from app.utils.time_parser import (
    filter_slots_by_hhmm_range,
    parse_time_candidates,
    pick_exact_slot,
    slot_hhmm,
    sort_slots_by_requested_time,
)

logger = logging.getLogger(__name__)


_SLOTS_PAGE_SIZE = 12


def _paginate_slots(slots: List[Dict], page: int, page_size: int = _SLOTS_PAGE_SIZE) -> Dict:
    return telegram_ui.paginate_slots(slots, page=page, page_size=page_size)


def render_slots_reply(pending_data: Dict, page: int = 0, header: str = "") -> BotReply:
    """Grilla de horarios (3 columnas, paginada) + footer de navegación."""
    slots = pending_data.get("available_slots") or []
    date_str = str(pending_data.get("date") or "")
    rows = telegram_ui.with_footer(
        telegram_ui.time_grid_buttons(slots, date_str, page=page)
    )
    date_show = format_date_human_es(date_str) if date_str else ""
    text = header or f"Para el <b>{date_show}</b> tenemos estos horarios:"
    return BotReply(f"{text}\n\n¿Cuál preferís?", keyboard=rows)


def _service_menu_text(services: List[Dict]) -> str:
    lines = []
    for i, s in enumerate(services, 1):
        lines.append(f"  {i}. {s['name']} (${s['price']}, {s['duration_minutes']} min)")
    return "\n".join(lines)


def _resolve_service_choice(services: List[Dict], raw_text: str, entity_service: str = "") -> str:
    txt = str(raw_text or "").strip().lower()
    if not txt:
        return ""
    if txt.isdigit():
        idx = int(txt) - 1
        if 0 <= idx < len(services):
            return services[idx]["name"]

    # Intentar extraer número dentro de texto (ej: "opción 1")
    m = re.search(r"\b([1-9]\d?)\b", txt)
    if m:
        idx = int(m.group(1)) - 1
        if 0 <= idx < len(services):
            return services[idx]["name"]

    candidate = str(entity_service or txt).lower()
    for s in services:
        if s["name"].lower() in candidate or candidate in s["name"].lower():
            return s["name"]
    return ""


def _suggested_days_text(days: List[Dict]) -> str:
    return "\n".join(
        f"  {i}. {format_date_human_es(d['date'])}"
        for i, d in enumerate(days, 1)
    )


def _looks_like_availability_question(nlu_result: Dict) -> bool:
    text = str(nlu_result.get("raw_understanding") or "").lower()
    keys = ("horario", "horarios", "disponible", "disponibilidad", "qué tienes", "que tienes")
    return any(k in text for k in keys)


def _resolve_slot_selection(available_slots: List[Dict], raw_text: str, time_entity: str = "") -> Dict | None:
    text = str(raw_text or "").strip().lower()
    candidate_time = str(time_entity or "").strip()

    if candidate_time:
        for slot in available_slots:
            if candidate_time in str(slot.get("start_datetime") or "") or candidate_time in str(
                slot.get("start_time") or ""
            ):
                return slot

    exact_slot = pick_exact_slot(available_slots, candidate_time or text, allow_bare_hour=False)
    if exact_slot:
        return exact_slot

    for slot in available_slots:
        start_time = str(slot.get("start_time") or "").lower()
        if start_time and start_time in text:
            return slot

    ordinals = {
        "primero": 0,
        "primer": 0,
        "primera": 0,
        "segundo": 1,
        "segunda": 1,
        "tercero": 2,
        "tercera": 2,
        "cuarto": 3,
        "cuarta": 3,
        "quinto": 4,
        "quinta": 4,
        "sexto": 5,
        "sexta": 5,
        "séptimo": 6,
        "septimo": 6,
        "séptima": 6,
        "septima": 6,
        "octavo": 7,
        "octava": 7,
        "último": -1,
        "ultimo": -1,
    }
    for word, index in ordinals.items():
        if word in text:
            if index == -1 and available_slots:
                return available_slots[-1]
            if 0 <= index < len(available_slots):
                return available_slots[index]

    number_match = re.search(
        r"\b(?:opci[oó]n|n[uú]mero|numero|num|#)\s*(\d{1,2})\b",
        text,
    )
    if number_match:
        idx = int(number_match.group(1)) - 1
        if 0 <= idx < len(available_slots):
            return available_slots[idx]

    plain_numbers = re.findall(r"\b(\d{1,2})\b", text)
    if plain_numbers:
        # Si el texto menciona una hora explícita, ya fue intentada arriba; acá tomamos el número
        # como opción de lista para frases tipo "me quedo con la 4".
        idx = int(plain_numbers[0]) - 1
        if 0 <= idx < len(available_slots):
            return available_slots[idx]

    return None


def _build_confirmation_text(
    customer_name: str,
    service_name: str,
    date_str: str,
    slot: Dict,
) -> BotReply:
    who = customer_name or "cliente"
    hour = slot.get("start_time", "")
    date_show = format_date_human_es(date_str) if date_str else ""
    return BotReply(
        f"Perfecto, <b>{who}</b>. La hora <b>{hour}</b> está disponible.\n\n"
        "Resumen de la cita:\n"
        f"✂️ Servicio: {service_name}\n"
        f"📅 Fecha: {date_show}\n"
        f"⏰ Hora: {hour}\n\n"
        "¿Confirmo esta cita?",
        keyboard=telegram_ui.with_footer(telegram_ui.confirm_booking_buttons()),
    )


async def handle_book_appointment(nlu_result: Dict, context: Dict) -> str:
    """
    Maneja el flujo de agendar una cita

    Args:
        nlu_result: Resultado del NLU Engine
        context: Contexto de conversación

    Returns:
        Mensaje de respuesta para el cliente
    """
    business_id = context["business_id"]
    phone_number = context["phone_number"]
    customer_id = context.get("customer_id")
    raw_user_text = str(
        nlu_result.get("_raw_user_text")
        or nlu_result.get("raw_understanding")
        or ""
    )
    entities = dict(nlu_result.get("entities", {}) or {})
    # Evitar falsos positivos de hora (ej. "opción 1" no es "1:00 AM").
    if entities.get("time") and not parse_time_candidates(raw_user_text, allow_bare_hour=False):
        entities.pop("time", None)
    missing = nlu_result.get("missing", [])
    pending_data = context.get("pending_data", {})

    # 1. Verificar si el cliente existe
    if not customer_id:
        # Recuperar cliente por canal por si se perdió contexto (evita pedir nombre repetido).
        existing = await db_service.get_customer_by_channel(business_id, phone_number)
        if existing:
            customer_id = existing["id"]
            existing_name = existing.get("name") or context.get("customer_name")
            await conversation_manager.set_customer_info(
                business_id, phone_number, customer_id, existing_name or "Cliente"
            )

        # Cliente nuevo, ya debería tener nombre desde el greeting
        customer_name = context.get("customer_name")

        if not customer_name:
            # Pedir nombre
            await conversation_manager.update_context(
                business_id,
                phone_number,
                {
                    "current_intent": "book_appointment",
                    "state": "awaiting_name",
                    "pending_data": entities,
                },
            )
            return "Para continuar con gusto, ¿me podría compartir su nombre, por favor? 😊"

        # Crear cliente
        result = await db_service.find_or_create_customer(
            business_id=business_id, phone=phone_number, name=customer_name
        )

        customer = result["customer"]
        customer_id = customer["id"]

        # Guardar en contexto
        await conversation_manager.set_customer_info(
            business_id, phone_number, customer_id, customer_name
        )

    # 2. Merge pending_data con entities nuevos (sin auto-resolver servicio por historial)
    old_date = pending_data.get("date")
    pending_data.update(entities)
    pending_data.pop("suggested_service", None)
    if old_date and pending_data.get("date") and old_date != pending_data.get("date"):
        pending_data.pop("time", None)
        pending_data.pop("time_daypart_range", None)
        pending_data.pop("available_slots", None)
        pending_data.pop("selected_slot", None)

    # T023: Suggested day selection — user picks "1", "2" or "3" from offered alternatives
    if pending_data.get("suggested_days") and not pending_data.get("date"):
        txt = str(raw_user_text or "").strip()
        m = re.search(r"\b([123])\b", txt)
        if m:
            idx = int(m.group(1)) - 1
            suggested = pending_data.get("suggested_days", [])
            if 0 <= idx < len(suggested):
                pending_data["date"] = suggested[idx]["date"]
                pending_data.pop("suggested_days", None)

    # Resolver servicio desde el texto aunque aún no haya fecha (evita perder "Corte" al pedir el día)
    if not pending_data.get("service"):
        services_early = await db_service.get_business_services(business_id)
        sn_early = _resolve_service_choice(
            services_early,
            raw_user_text,
            str(entities.get("service") or ""),
        )
        if sn_early:
            pending_data["service"] = sn_early

    # 3. Fecha primero
    if not pending_data.get("date"):
        if pending_data.get("service"):
            services_for_calendar = await db_service.get_business_services(business_id)
            service_for_calendar = next(
                (
                    s
                    for s in services_for_calendar
                    if s["name"].lower() in str(pending_data["service"]).lower()
                ),
                None,
            )
            if service_for_calendar:
                from app.handlers.booking_calendar_handler import handle_booking_current_week

                pending_data["service_id"] = service_for_calendar["id"]
                return await handle_booking_current_week(
                    business_id,
                    phone_number,
                    service_for_calendar["id"],
                    {**context, "pending_data": pending_data},
                    reset_stack=True,
                )
        await conversation_manager.update_context(
            business_id,
            phone_number,
            {
                "current_intent": "book_appointment",
                "state": "awaiting_date",
                "pending_data": pending_data,
            },
        )
        return "¿Para cuándo te gustaría la cita? (Ej: mañana, viernes, 5 de diciembre)"

    # 4. Horarios segundo: si no hay slot ni hora elegida, mostrar lista disponible
    has_slot_or_time = bool(pending_data.get("selected_slot")) or bool(
        pending_data.get("time")
    ) or bool(pending_data.get("time_daypart_range"))

    if not has_slot_or_time:
        services_all = await db_service.get_business_services(business_id)
        if not services_all:
            from app.services.no_services_nlu import NO_SERVICES_GENERIC
            return BotReply(NO_SERVICES_GENERIC, keyboard=telegram_ui.with_footer([]))

        # Para MVP: usar el servicio conocido si existe, si no el primero de la lista
        service_for_query = None
        if pending_data.get("service"):
            service_for_query = next(
                (s for s in services_all if s["name"].lower() in str(pending_data["service"]).lower()),
                None,
            )
        if not service_for_query:
            service_for_query = services_all[0]

        availability = await db_service.get_availability(
            business_id=business_id,
            service_id=service_for_query["id"],
            date=pending_data["date"],
            preferred_time=None,
        )
        slots = availability.get("available_slots", [])
        dr = pending_data.get("time_daypart_range")
        if isinstance(dr, dict) and dr.get("start") and dr.get("end"):
            slots = filter_slots_by_hhmm_range(slots, dr["start"], dr["end"])

        date_show = format_date_human_es(str(pending_data["date"]))

        if not slots:
            from datetime import date as _date_type
            try:
                next_from = _date_type.fromisoformat(str(pending_data["date"])) + timedelta(days=1)
            except Exception:
                next_from = None
            next_days = (
                await db_service.get_next_available_days(
                    business_id=business_id,
                    service_id=service_for_query["id"],
                    from_date=next_from,
                    limit=3,
                    max_days=14,
                )
                if next_from
                else []
            )
            pending_data.pop("date", None)
            if next_days:
                pending_data["suggested_days"] = next_days
                await conversation_manager.update_context(
                    business_id,
                    phone_number,
                    {
                        "current_intent": "book_appointment",
                        "state": "awaiting_date",
                        "pending_data": pending_data,
                    },
                )
                return BotReply(
                    f"El <b>{date_show}</b> no tenemos horarios disponibles. "
                    "Los próximos días con disponibilidad son:\n\n¿Cuál preferís?",
                    keyboard=telegram_ui.with_footer(telegram_ui.day_buttons(next_days)),
                )
            await conversation_manager.update_context(
                business_id,
                phone_number,
                {
                    "current_intent": "book_appointment",
                    "state": "awaiting_date",
                    "pending_data": pending_data,
                },
            )
            return BotReply(
                f"Lo siento, el <b>{date_show}</b> no tenemos horarios disponibles. "
                "¿Querés probar otro día?",
                keyboard=telegram_ui.with_footer([]),
            )

        page_info = _paginate_slots(slots, page=0)
        pending_slots = {
            **pending_data,
            "available_slots": slots,
            "slot_page": 0,
            "service_id": service_for_query["id"],
        }
        await conversation_manager.update_context(
            business_id,
            phone_number,
            {
                "current_intent": "book_appointment",
                "state": "awaiting_slot_selection",
                "pending_data": pending_slots,
            },
        )
        return render_slots_reply(pending_slots, page=0)

    # 5. Servicio: si no está, intentar resolver del mensaje actual o preguntar
    if not pending_data.get("service"):
        services_all = await db_service.get_business_services(business_id)
        selected_name = _resolve_service_choice(
            services_all,
            raw_user_text,
            str(entities.get("service") or ""),
        )
        if selected_name:
            pending_data["service"] = selected_name
        else:
            slot = pending_data.get("selected_slot") or {}
            slot_time = slot.get("start_time", "")
            date_show = format_date_human_es(str(pending_data["date"]))
            time_part = f" a las <b>{slot_time}</b>" if slot_time else ""
            await conversation_manager.update_context(
                business_id,
                phone_number,
                {
                    "current_intent": "book_appointment",
                    "state": "awaiting_service",
                    "pending_data": pending_data,
                },
            )
            return BotReply(
                f"Perfecto. Para el <b>{date_show}</b>{time_part}, ¿qué servicio necesitás?",
                keyboard=telegram_ui.with_footer(telegram_ui.service_buttons(services_all)),
            )

    # 6. Tenemos toda la información necesaria; resolver service_id
    service_name = pending_data.get("service")
    date_str = pending_data.get("date")
    time_str = pending_data.get("time")

    # Si el slot ya fue elegido (flujo fecha→slot→servicio), ir directo a confirmación
    if pending_data.get("selected_slot"):
        selected_slot = pending_data["selected_slot"]
        services = await db_service.get_business_services(business_id)
        service = next(
            (s for s in services if s["name"].lower() in service_name.lower()), None
        )
        if not service:
            await conversation_manager.clear_pending_data(business_id, phone_number)
            return f"No encontré el servicio '{service_name}'. ¿Podrías elegir de la lista?"
        await conversation_manager.update_context(
            business_id,
            phone_number,
            {
                "current_intent": "book_appointment",
                "state": "awaiting_booking_confirmation",
                "pending_data": {**pending_data, "service_id": service["id"]},
            },
        )
        return _build_confirmation_text(
            context.get("customer_name", "Cliente"),
            service["name"],
            date_str,
            selected_slot,
        )

    # Resolver service_id desde el nombre
    services = await db_service.get_business_services(business_id)
    service = next(
        (s for s in services if s["name"].lower() in service_name.lower()), None
    )

    if not service:
        # Servicio no encontrado
        await conversation_manager.clear_pending_data(business_id, phone_number)
        return f"No encontré el servicio '{service_name}'. ¿Podrías elegir de la lista?"

    service_id = service["id"]

    # 5. Consultar disponibilidad
    try:
        availability = await db_service.get_availability(
            business_id=business_id,
            service_id=service_id,
            date=date_str,
            preferred_time=time_str if time_str else None,
        )

        slots = availability.get("available_slots", [])
        dr = pending_data.get("time_daypart_range")
        if isinstance(dr, dict) and dr.get("start") and dr.get("end"):
            slots = filter_slots_by_hhmm_range(slots, dr["start"], dr["end"])

        if not slots:
            date_show = format_date_human_es(date_str or "")
            try:
                next_from = date_type.fromisoformat(str(date_str)) + timedelta(days=1)
            except Exception:
                next_from = None
            next_days = (
                await db_service.get_next_available_days(
                    business_id=business_id,
                    service_id=service_id,
                    from_date=next_from,
                    limit=3,
                    max_days=14,
                )
                if next_from
                else []
            )
            fresh_pending = dict(pending_data)
            fresh_pending.pop("date", None)
            fresh_pending.pop("time", None)
            fresh_pending.pop("time_daypart_range", None)
            if next_days:
                fresh_pending["suggested_days"] = next_days
                await conversation_manager.update_context(
                    business_id,
                    phone_number,
                    {
                        "current_intent": "book_appointment",
                        "state": "awaiting_date",
                        "pending_data": fresh_pending,
                    },
                )
                return BotReply(
                    f"No tengo disponibilidad para {service['name']} el {date_show}. "
                    "Los próximos días disponibles son:\n\n¿Cuál preferís?",
                    keyboard=telegram_ui.with_footer(telegram_ui.day_buttons(next_days)),
                )
            await conversation_manager.clear_pending_data(business_id, phone_number)
            return BotReply(
                f"Lo siento, no tengo disponibilidad para {service['name']} el {date_show}. "
                "¿Te gustaría otra fecha?",
                keyboard=telegram_ui.with_footer([]),
            )

        exact_slot = pick_exact_slot(slots, time_str or "", allow_bare_hour=True)
        if exact_slot:
            await conversation_manager.update_context(
                business_id,
                phone_number,
                {
                    "current_intent": "book_appointment",
                    "state": "awaiting_booking_confirmation",
                    "pending_data": {
                        **pending_data,
                        "service_id": service_id,
                        "selected_slot": exact_slot,
                    },
                },
            )
            return _build_confirmation_text(
                context.get("customer_name", "Cliente"),
                service["name"],
                date_str,
                exact_slot,
            )

        # 6. Guardar slots y ofrecer alternativas cuando la hora exacta no existe
        preferred_hhmm = None
        if customer_id:
            preferred_hhmm = await db_service.get_customer_preferred_time_hhmm(customer_id)
        ranked_slots = sort_slots_by_requested_time(
            slots, time_str or "", preferred_hhmm=preferred_hhmm, allow_bare_hour=True
        )
        suggestions = ranked_slots[:8]

        page_info2 = _paginate_slots(suggestions, page=0)
        await conversation_manager.update_context(
            business_id,
            phone_number,
            {
                "current_intent": "book_appointment",
                "state": "awaiting_slot_selection",
                "pending_data": {
                    **pending_data,
                    "service_id": service_id,
                    "available_slots": suggestions,
                    "slot_page": 0,
                },
            },
        )

        req_txt = str(time_str or "").strip()
        if not req_txt and isinstance(dr, dict):
            req_txt = "en esa franja"
        date_show = format_date_human_es(date_str or "")
        pending_alt = {
            **pending_data,
            "available_slots": suggestions,
            "slot_page": 0,
            "service_id": service_id,
        }
        await conversation_manager.update_context(
            business_id,
            phone_number,
            {
                "current_intent": "book_appointment",
                "state": "awaiting_slot_selection",
                "pending_data": pending_alt,
            },
        )
        header = (
            f"No tengo disponibilidad exacta a las <b>{req_txt}</b> para {service['name']} el {date_show}. "
            "Sí tengo estas opciones:"
        )
        return render_slots_reply(pending_alt, page=0, header=header)

    except Exception:
        logger.exception("booking_availability_failed business=%s user=%s", business_id, phone_number)
        await conversation_manager.clear_pending_data(business_id, phone_number)
        return f"Hubo un problema consultando la disponibilidad. ¿Podrías intentar de nuevo?"


async def handle_slot_selection(nlu_result: Dict, context: Dict) -> str:
    """
    Maneja la selección de un slot disponible

    El cliente responde "1", "el primero", "3:00 PM", o en lenguaje natural ("las dos de la tarde").
    """
    business_id = context["business_id"]
    phone_number = context["phone_number"]
    customer_id = context["customer_id"]
    pending_data = context.get("pending_data", {})
    available_slots = pending_data.get("available_slots", [])

    if not available_slots:
        return "Parece que perdí los horarios disponibles. ¿Podrías decirme de nuevo para cuándo quieres la cita?"

    current_page = int(pending_data.get("slot_page") or 0)
    page_info = _paginate_slots(available_slots, page=current_page)

    page_slots = page_info["slots"]
    time_entity = nlu_result.get("entities", {}).get("time")
    fallback_message_lower = str(
        nlu_result.get("_raw_user_text")
        or nlu_result.get("raw_understanding", "")
        or ""
    ).lower()
    selected_slot = _resolve_slot_selection(
        page_slots,
        fallback_message_lower,
        str(time_entity or ""),
    )

    if not selected_slot:
        return render_slots_reply(
            pending_data,
            page=current_page,
            header="No entendí cuál horario elegiste. Estas siguen siendo las opciones:",
        )

    updated_pending = {**pending_data, "selected_slot": selected_slot}

    # Si no hay servicio aún, preguntarlo antes de confirmar
    if not pending_data.get("service"):
        services_all = await db_service.get_business_services(business_id)
        # Intentar resolver del texto actual
        selected_name = _resolve_service_choice(services_all, fallback_message_lower, "")
        if selected_name:
            updated_pending["service"] = selected_name
        else:
            slot_time = selected_slot.get("start_time", "")
            date_show = format_date_human_es(str(pending_data.get("date", "")))
            await conversation_manager.update_context(
                business_id,
                phone_number,
                {
                    "current_intent": "book_appointment",
                    "state": "awaiting_service",
                    "pending_data": updated_pending,
                },
            )
            return BotReply(
                f"Guardé tu horario: <b>{slot_time}</b> del <b>{date_show}</b>.\n\n"
                "¿Qué servicio necesitás?",
                keyboard=telegram_ui.with_footer(telegram_ui.service_buttons(services_all)),
            )

    await conversation_manager.update_context(
        business_id,
        phone_number,
        {
            "current_intent": "book_appointment",
            "state": "awaiting_booking_confirmation",
            "pending_data": updated_pending,
        },
    )
    return _build_confirmation_text(
        context.get("customer_name", "Cliente"),
        updated_pending.get("service", "servicio"),
        pending_data.get("date", ""),
        selected_slot,
    )


async def handle_booking_confirmation(nlu_result: Dict, context: Dict) -> str:
    business_id = context["business_id"]
    phone_number = context["phone_number"]
    customer_id = context.get("customer_id")
    pending_data = context.get("pending_data", {})
    selected_slot = pending_data.get("selected_slot")
    available_slots = pending_data.get("available_slots", [])
    user_text = str(
        nlu_result.get("_raw_user_text")
        or nlu_result.get("raw_understanding", "")
        or ""
    ).strip().lower()

    yes_words = ("si", "sí", "confirmo", "confirmar", "ok", "dale", "de acuerdo")
    no_words = ("no", "cambiar", "otro", "otra", "cancelar")

    if any(w in user_text for w in no_words):
        if available_slots:
            await conversation_manager.update_context(
                business_id,
                phone_number,
                {
                    "current_intent": "book_appointment",
                    "state": "awaiting_slot_selection",
                    "pending_data": pending_data,
                },
            )
            return render_slots_reply(
                pending_data,
                page=0,
                header="Perfecto, cambiamos el horario. Estas son las opciones disponibles:",
            )
        await conversation_manager.update_context(
            business_id,
            phone_number,
            {
                "current_intent": "book_appointment",
                "state": "awaiting_time",
                "pending_data": pending_data,
            },
        )
        return BotReply(
            "Listo, no la confirmé. ¿Qué hora te conviene?",
            keyboard=telegram_ui.with_footer([]),
        )

    if not any(w in user_text for w in yes_words):
        return BotReply(
            "Para confirmar tocá <b>✅ Confirmar</b> o <b>🔁 Ver otro horario</b>.",
            keyboard=telegram_ui.with_footer(telegram_ui.confirm_booking_buttons()),
        )

    if not selected_slot or not customer_id:
        await conversation_manager.clear_pending_data(business_id, phone_number)
        return "Perdí el contexto de la reserva. ¿Me decís de nuevo qué servicio y horario querés?"

    service_id = pending_data.get("service_id")
    if not service_id:
        await conversation_manager.clear_pending_data(business_id, phone_number)
        return "No pude validar el servicio. Intentemos de nuevo desde el inicio."

    try:
        # Revalidar disponibilidad inmediata para evitar confirmar un horario tomado en paralelo.
        requested_hhmm = slot_hhmm(selected_slot)
        fresh = await db_service.get_availability(
            business_id=business_id,
            service_id=service_id,
            date=str(pending_data.get("date") or ""),
            preferred_time=requested_hhmm,
        )
        still_free = pick_exact_slot(fresh.get("available_slots", []), requested_hhmm)
        if not still_free:
            logger.info(
                "booking_confirmation_slot_unavailable business=%s user=%s customer=%s service=%s date=%s slot=%s",
                business_id,
                phone_number,
                customer_id,
                service_id,
                pending_data.get("date"),
                requested_hhmm,
            )
            fresh_pending = {
                **pending_data,
                "available_slots": fresh.get("available_slots", [])[:8],
                "slot_page": 0,
            }
            await conversation_manager.update_context(
                business_id,
                phone_number,
                {
                    "current_intent": "book_appointment",
                    "state": "awaiting_slot_selection",
                    "pending_data": fresh_pending,
                },
            )
            return render_slots_reply(
                fresh_pending,
                page=0,
                header="Ese horario ya no está disponible. Te comparto opciones actualizadas:",
            )

        appointment_data = {
            "business": business_id,
            "customer": customer_id,
            "service": service_id,
            "start_at": selected_slot["start_datetime"],
            "end_at": selected_slot["end_datetime"],
            "created_via": "telegram",
        }
        appointment = await db_service.create_appointment(appointment_data)
        if isinstance(appointment, dict) and appointment.get("error") == "slot_conflict":
            fresh2 = await db_service.get_availability(
                business_id=business_id,
                service_id=service_id,
                date=str(pending_data.get("date") or ""),
            )
            fresh_slots = fresh2.get("available_slots", [])[:8]
            conflict_pending = {**pending_data, "available_slots": fresh_slots, "slot_page": 0}
            await conversation_manager.update_context(
                business_id,
                phone_number,
                {
                    "current_intent": "book_appointment",
                    "state": "awaiting_slot_selection",
                    "pending_data": conflict_pending,
                },
            )
            return render_slots_reply(
                conflict_pending,
                page=0,
                header="Ese horario acaba de ser reservado por otra persona. "
                "Te muestro las opciones actualizadas:",
            )
        logger.info(
            "booking_confirmed business=%s user=%s customer=%s service=%s appointment=%s slot=%s",
            business_id,
            phone_number,
            customer_id,
            service_id,
            appointment.get("id") if isinstance(appointment, dict) else None,
            requested_hhmm,
        )
        await conversation_manager.clear_pending_data(business_id, phone_number)

        business = await db_service.get_business(business_id)
        customer_name = context.get("customer_name") or ""
        await conversation_manager.mark_main_menu(business_id, phone_number)
        return telegram_ui.main_menu_reply(
            "✅ ¡Tu cita está confirmada!\n\n"
            f"👤 {customer_name or 'Cliente'}\n"
            f"📅 {format_date_human_es(pending_data.get('date') or '')}\n"
            f"⏰ {selected_slot.get('start_time')}\n"
            f"✂️ {pending_data.get('service', 'servicio')}\n"
            f"📍 {business.get('name', '')}\n"
            f"    {business.get('address', '')}",
            customer_name,
        )
    except Exception:
        logger.exception("booking_create_failed business=%s user=%s customer=%s", business_id, phone_number, customer_id)
        await conversation_manager.clear_pending_data(business_id, phone_number)
        return "Hubo un problema creando la cita. Por favor intentá de nuevo."

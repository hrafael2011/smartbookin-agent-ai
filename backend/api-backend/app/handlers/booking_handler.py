"""
Handler para el intent book_appointment
"""
import logging
import re
from typing import Dict, List
from app.services import db_service
from app.services.conversation_manager import conversation_manager
from app.utils.date_parse import format_date_human_es
from app.utils.time_parser import (
    filter_slots_by_hhmm_range,
    parse_time_candidates,
    pick_exact_slot,
    slot_hhmm,
    sort_slots_by_requested_time,
)

logger = logging.getLogger(__name__)


def _slots_short_list(slots: List[Dict], limit: int = 3) -> str:
    lines = []
    for i, slot in enumerate(slots[:limit], 1):
        lines.append(f"  {i}. {slot.get('start_time')}")
    return "\n".join(lines)


def _service_menu_text(services: List[Dict]) -> str:
    lines = []
    for i, s in enumerate(services, 1):
        lines.append(f"  {i}. {s['name']} (${s['price']}, {s['duration_minutes']} min)")
    return "\n".join(lines)


def _resolve_service_choice(services: List[Dict], raw_text: str, entity_service: str = "") -> str:
    txt = str(raw_text or "").strip().lower()
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
) -> str:
    who = customer_name or "cliente"
    hour = slot.get("start_time", "")
    date_show = format_date_human_es(date_str) if date_str else ""
    return (
        f"Perfecto, <b>{who}</b>. La hora <b>{hour}</b> está disponible.\n\n"
        "Resumen de la cita:\n"
        f"✂️ Servicio: {service_name}\n"
        f"📅 Fecha: {date_show}\n"
        f"⏰ Hora: {hour}\n"
        "\n"
        "¿Confirmo esta cita?\n"
        "Respondé <b>sí</b> para agendar o <b>no</b> para ver otros horarios."
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
            return NO_SERVICES_GENERIC

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
            pending_data.pop("date", None)
            await conversation_manager.update_context(
                business_id,
                phone_number,
                {
                    "current_intent": "book_appointment",
                    "state": "awaiting_date",
                    "pending_data": pending_data,
                },
            )
            return (
                f"Lo siento, el <b>{date_show}</b> no tenemos horarios disponibles. "
                "¿Querés probar otro día?"
            )

        await conversation_manager.update_context(
            business_id,
            phone_number,
            {
                "current_intent": "book_appointment",
                "state": "awaiting_slot_selection",
                "pending_data": {**pending_data, "available_slots": slots[:8]},
            },
        )
        return (
            f"Para el <b>{date_show}</b> tenemos estos horarios:\n\n"
            f"{_slots_short_list(slots, limit=8)}\n\n"
            "¿Cuál preferís? Respondé con el número o la hora exacta."
        )

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
            services_text = _service_menu_text(services_all)
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
            return (
                f"Perfecto. Para el <b>{date_show}</b>{time_part}, ¿qué servicio necesitás?\n\n"
                f"{services_text}\n\n"
                "Escribí el nombre o el número."
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
            # No hay disponibilidad
            await conversation_manager.clear_pending_data(business_id, phone_number)
            date_show = format_date_human_es(date_str or "")
            return f"Lo siento, no tengo disponibilidad para {service['name']} el {date_show}. ¿Te gustaría otra fecha?"

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
                },
            },
        )

        req_txt = str(time_str or "").strip()
        if not req_txt and isinstance(dr, dict):
            req_txt = "en esa franja"
        date_show = format_date_human_es(date_str or "")
        return (
            f"No tengo disponibilidad exacta a las <b>{req_txt}</b> para {service['name']} el {date_show}.\n\n"
            f"Sí tengo estas opciones:\n{_slots_short_list(suggestions, limit=8)}\n\n"
            "Decime cuál preferís (número u hora exacta)."
        )

    except Exception as e:
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

    time_entity = nlu_result.get("entities", {}).get("time")
    fallback_message_lower = str(
        nlu_result.get("_raw_user_text")
        or nlu_result.get("raw_understanding", "")
        or ""
    ).lower()
    selected_slot = _resolve_slot_selection(
        available_slots,
        fallback_message_lower,
        str(time_entity or ""),
    )

    if not selected_slot:
        return (
            "No entendí cuál horario elegiste.\n\n"
            f"Estas siguen siendo las opciones:\n{_slots_short_list(available_slots, limit=8)}\n\n"
            "Podés responder con el número, decir una hora exacta o indicarme otro día."
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
            services_text = _service_menu_text(services_all)
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
            return (
                f"Guardé tu horario: <b>{slot_time}</b> del <b>{date_show}</b>.\n\n"
                f"¿Qué servicio necesitás?\n\n{services_text}\n\n"
                "Escribí el nombre o el número."
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
            return (
                "Perfecto, cambiamos el horario. Estas son las opciones disponibles:\n\n"
                f"{_slots_short_list(available_slots, limit=8)}\n\n"
                "Decime el número u otra hora exacta."
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
        return "Listo, no la confirmé. ¿Qué hora te conviene?"

    if not any(w in user_text for w in yes_words):
        return "Para seguir, respondeme <b>sí</b> para confirmar o <b>no</b> para cambiar horario."

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
            await conversation_manager.update_context(
                business_id,
                phone_number,
                {
                    "current_intent": "book_appointment",
                    "state": "awaiting_slot_selection",
                    "pending_data": {
                        **pending_data,
                        "available_slots": fresh.get("available_slots", [])[:8],
                    },
                },
            )
            return (
                "Ese horario ya no está disponible. Te comparto opciones actualizadas:\n\n"
                f"{_slots_short_list(fresh.get('available_slots', []), limit=8)}\n\n"
                "Decime cuál preferís."
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
        return (
            "✅ ¡Tu cita está confirmada!\n\n"
            f"👤 {context.get('customer_name', 'Cliente')}\n"
            f"📅 {format_date_human_es(pending_data.get('date') or '')}\n"
            f"⏰ {selected_slot.get('start_time')}\n"
            f"✂️ {pending_data.get('service', 'servicio')}\n"
            f"📍 {business.get('name', '')}\n"
            f"    {business.get('address', '')}\n\n"
            "¿Necesitás algo más?"
        )
    except Exception:
        await conversation_manager.clear_pending_data(business_id, phone_number)
        return "Hubo un problema creando la cita. Por favor intentá de nuevo."

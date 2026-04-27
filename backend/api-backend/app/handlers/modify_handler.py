"""
Handler para el intent modify_appointment (reagendar)
"""
import re
from datetime import datetime
from typing import Dict, List, Optional

from app.services import db_service
from app.services.conversation_manager import conversation_manager
from app.utils.date_parse import format_date_human_es
from app.utils.time_parser import parse_time_candidates, pick_exact_slot, sort_slots_by_requested_time


def _slots_modify_list(slots: List[Dict], limit: int = 8) -> str:
    lines = []
    for i, slot in enumerate(slots[:limit], 1):
        lines.append(f"  {i}. {slot.get('start_time')}")
    return "\n".join(lines)


def _select_modify_slot(
    available_slots: List[Dict],
    raw_user: str,
    time_entity: str = "",
) -> Optional[Dict]:
    raw = (raw_user or "").strip()
    if not raw:
        return None
    t_low = raw.lower()
    time_like = bool(parse_time_candidates(raw, allow_bare_hour=False)) or ":" in raw

    cand_ent = str(time_entity or "").strip()
    if cand_ent:
        ex = pick_exact_slot(available_slots, cand_ent, allow_bare_hour=False)
        if ex:
            return ex

    for tc in parse_time_candidates(raw, allow_bare_hour=False):
        ex = pick_exact_slot(available_slots, tc, allow_bare_hour=False)
        if ex:
            return ex

    for slot in available_slots:
        st = str(slot.get("start_time") or "").lower()
        if st and st in t_low:
            return slot

    if not time_like and raw.isdigit():
        idx = int(raw) - 1
        if 0 <= idx < len(available_slots):
            return available_slots[idx]

    if not time_like:
        m = re.search(r"\b([1-9])\b", t_low)
        if m:
            idx = int(m.group(1)) - 1
            if 0 <= idx < len(available_slots):
                return available_slots[idx]

    ordinals = {
        "primero": 0,
        "primer": 0,
        "segundo": 1,
        "tercero": 2,
        "cuarto": 3,
        "quinto": 4,
        "último": -1,
        "ultimo": -1,
    }
    for word, index in ordinals.items():
        if word in t_low:
            if index == -1 and available_slots:
                return available_slots[-1]
            if 0 <= index < len(available_slots):
                return available_slots[index]
    return None


async def handle_modify_appointment(nlu_result: Dict, context: Dict) -> str:
    """
    Maneja la modificación/reagendamiento de citas

    Flow:
    1. Obtener citas futuras del cliente
    2. Si tiene múltiples, pedir que elija cuál
    3. Pedir nueva fecha/hora
    4. Consultar disponibilidad
    5. Ofrecer slots
    6. Actualizar appointment

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
    entities = nlu_result.get("entities", {})

    if not customer_id:
        return "No tienes citas registradas para modificar."

    try:
        # Obtener citas futuras
        appointments = await db_service.get_customer_appointments(
            customer_id=customer_id,
            upcoming=True
        )

        if not appointments:
            return "No tienes citas próximas para modificar."

        # === PASO 1: Seleccionar la cita a modificar ===
        if not pending_data.get("selected_appointment_id"):
            # Solo tiene 1 cita
            if len(appointments) == 1:
                appt = appointments[0]
                start_at = datetime.fromisoformat(appt['start_at'].replace('Z', '+00:00'))
                date_str = start_at.strftime("%A %d de %B")
                time_str = start_at.strftime("%I:%M %p")
                service_name = appt.get('service_name', 'Servicio')

                # Guardar cita seleccionada
                await conversation_manager.update_context(
                    business_id,
                    phone_number,
                    {
                        "current_intent": "modify_appointment",
                        "state": "awaiting_new_datetime",
                        "pending_data": {
                            "selected_appointment_id": appt['id'],
                            "service_id": appt['service'],
                            "service_name": service_name
                        }
                    }
                )

                return f"""Tu cita actual:
📅 {date_str}
⏰ {time_str}
✂️ {service_name}

¿Para cuándo quieres reagendarla? (Ej: mañana, viernes, el 10 de diciembre)"""

            # Tiene múltiples citas
            if current_state != "awaiting_appointment_selection_modify":
                lines = [f"Tienes {len(appointments)} citas próximas. ¿Cuál quieres reagendar?"]
                lines.append("")

                for i, appt in enumerate(appointments[:5], 1):
                    start_at = datetime.fromisoformat(appt['start_at'].replace('Z', '+00:00'))
                    date_str = start_at.strftime("%d %b")
                    time_str = start_at.strftime("%I:%M %p")
                    service_name = appt.get('service_name', 'Servicio')

                    lines.append(f"{i}. {date_str} {time_str} - {service_name}")

                lines.append("")
                lines.append("Responde con el número.")

                await conversation_manager.update_context(
                    business_id,
                    phone_number,
                    {
                        "current_intent": "modify_appointment",
                        "state": "awaiting_appointment_selection_modify",
                        "pending_data": {"appointments": appointments}
                    }
                )

                return "\n".join(lines)

            # Cliente seleccionó una cita
            selection = entities.get("appointment_number", "")
            raw_user = (nlu_result.get("_raw_user_text") or "").strip()
            try:
                index = None
                if isinstance(selection, str) and selection.isdigit():
                    index = int(selection) - 1
                elif isinstance(selection, int):
                    index = selection - 1
                elif raw_user.isdigit():
                    index = int(raw_user) - 1
                else:
                    m = re.search(r"\b([1-9])\b", raw_user)
                    if m:
                        index = int(m.group(1)) - 1
                    else:
                        return "No entendí. Por favor responde con el número (1, 2, 3...)"

                if index is not None and 0 <= index < len(appointments):
                    selected_appt = appointments[index]
                    service_name = selected_appt.get('service_name', 'Servicio')

                    await conversation_manager.update_context(
                        business_id,
                        phone_number,
                        {
                            "current_intent": "modify_appointment",
                            "state": "awaiting_new_datetime",
                            "pending_data": {
                                "selected_appointment_id": selected_appt['id'],
                                "service_id": selected_appt['service'],
                                "service_name": service_name
                            }
                        }
                    )

                    return f"Perfecto. ¿Para cuándo quieres reagendar tu {service_name}? (Ej: mañana, viernes, 10 de diciembre)"

                if index is not None:
                    return f"Por favor elegí un número entre 1 y {len(appointments)}."

            except Exception:
                return "No entendí cuál cita. Responde con el número."

        # === PASO 2: Cliente dio nueva fecha/hora ===
        selected_appointment_id = pending_data.get("selected_appointment_id")
        service_id = pending_data.get("service_id")
        service_name = pending_data.get("service_name", "servicio")

        # Verificar si tenemos fecha y hora
        new_date = pending_data.get("new_date") or entities.get("date")
        new_time = pending_data.get("new_time") or entities.get("time")

        if not new_date:
            # Pedir fecha
            await conversation_manager.update_context(
                business_id,
                phone_number,
                {
                    "state": "awaiting_new_date",
                    "pending_data": {**pending_data}
                }
            )
            return "¿Para qué día? (Ej: mañana, viernes, 10 de diciembre)"

        # Guardar fecha
        pending_data["new_date"] = new_date

        if not new_time:
            # Pedir hora
            await conversation_manager.update_context(
                business_id,
                phone_number,
                {
                    "state": "awaiting_new_time",
                    "pending_data": {**pending_data}
                }
            )
            return "¿A qué hora prefieres? (Ej: 3 PM, en la mañana, 15:00)"

        # Guardar hora
        pending_data["new_time"] = new_time

        # === PASO 3: Consultar disponibilidad ===
        if current_state != "awaiting_slot_selection_modify":
            try:
                availability = await db_service.get_availability(
                    business_id=business_id,
                    service_id=service_id,
                    date=new_date,
                    preferred_time=new_time if new_time else None
                )

                slots = availability.get("available_slots", [])

                if not slots:
                    await conversation_manager.clear_pending_data(business_id, phone_number)
                    return f"Lo siento, no hay disponibilidad para {service_name} el {new_date}. ¿Te gustaría otra fecha?"

                req_txt = str(new_time or "").strip()
                ranked = sort_slots_by_requested_time(
                    slots, req_txt, preferred_hhmm=None, allow_bare_hour=True
                )
                exact = pick_exact_slot(slots, req_txt, allow_bare_hour=True)

                date_show = (
                    format_date_human_es(str(new_date))
                    if isinstance(new_date, str) and len(str(new_date)) == 10
                    else str(new_date)
                )

                deduped: List[Dict] = []
                seen_dt = set()
                for s in ([exact] if exact else []) + ranked:
                    dt = s.get("start_datetime")
                    if dt and dt not in seen_dt:
                        seen_dt.add(dt)
                        deduped.append(s)
                offer = deduped[:8]

                if exact:
                    header = (
                        f"Para el <b>{date_show}</b> tenemos tu hora pedida "
                        f"(<b>{exact.get('start_time')}</b>) entre las opciones.\n\n"
                    )
                else:
                    header = (
                        f"No tengo disponibilidad exacta a las <b>{req_txt}</b> el <b>{date_show}</b>. "
                        f"Estos son horarios disponibles para <b>{service_name}</b>:\n\n"
                    )

                await conversation_manager.update_context(
                    business_id,
                    phone_number,
                    {
                        "current_intent": "modify_appointment",
                        "state": "awaiting_slot_selection_modify",
                        "pending_data": {
                            **pending_data,
                            "available_slots": offer,
                        },
                    },
                )

                return (
                    f"{header}{_slots_modify_list(offer, limit=8)}\n\n"
                    "¿Cuál preferís? Respondé con el número o la hora exacta."
                )

            except Exception as e:
                await conversation_manager.clear_pending_data(business_id, phone_number)
                return "Hubo un problema consultando disponibilidad. Por favor intenta de nuevo."

        # === PASO 4: Cliente seleccionó slot ===
        available_slots = pending_data.get("available_slots", [])

        if not available_slots:
            return "Parece que perdí los horarios. ¿Podrías decirme de nuevo para cuándo quieres la cita?"

        raw_user = (nlu_result.get("_raw_user_text") or "").strip()
        time_ent = str((entities or {}).get("time") or "")
        selected_slot = _select_modify_slot(available_slots, raw_user, time_ent)

        if not selected_slot:
            return (
                "No entendí cuál horario elegiste.\n\n"
                f"Estas siguen siendo las opciones:\n{_slots_modify_list(available_slots, limit=8)}\n\n"
                "Respondé con el número o la hora exacta."
            )

        # === PASO 5: Actualizar appointment ===
        try:
            update_data = {
                "start_at": selected_slot["start_datetime"],
                "end_at": selected_slot["end_datetime"]
            }

            updated_appt = await db_service.update_appointment(
                appointment_id=selected_appointment_id,
                update_data=update_data
            )

            # Limpiar contexto
            await conversation_manager.clear_pending_data(business_id, phone_number)

            date_out = (
                format_date_human_es(str(new_date))
                if isinstance(new_date, str) and len(str(new_date)) == 10
                else str(new_date)
            )
            return f"""✅ ¡Listo! Tu cita se reagendó exitosamente

📅 Nueva fecha: {date_out}
⏰ Nueva hora: {selected_slot['start_time']}
✂️ {service_name}

Te enviaré nuevos recordatorios 😊

¿Necesitas algo más?"""

        except Exception as e:
            await conversation_manager.clear_pending_data(business_id, phone_number)
            return "Hubo un problema reagendando tu cita. Por favor intenta de nuevo."

    except Exception as e:
        return "Hubo un problema procesando tu solicitud. Por favor intenta de nuevo."

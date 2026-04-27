"""
Handler para el intent check_appointment
"""
from datetime import datetime
from typing import Dict
from app.services import db_service
from app.services.conversation_manager import conversation_manager


async def handle_check_appointment(nlu_result: Dict, context: Dict) -> str:
    """
    Maneja la consulta de citas del cliente

    Args:
        nlu_result: Resultado del NLU Engine
        context: Contexto de conversación

    Returns:
        Mensaje con las citas del cliente
    """
    business_id = context["business_id"]
    phone_number = context["phone_number"]
    customer_id = context.get("customer_id")
    customer_name = context.get("customer_name", "Cliente")

    if not customer_id:
        return "Parece que aún no tienes citas registradas. ¿Te gustaría agendar una?"

    try:
        # Obtener citas futuras del cliente
        appointments = await db_service.get_customer_appointments(
            customer_id=customer_id,
            upcoming=True
        )

        if not appointments:
            return f"No tienes citas próximas programadas, {customer_name}. ¿Te gustaría agendar una? 😊"

        # Formatear respuesta
        lines = [f"Estas son tus citas próximas, {customer_name}:"]
        lines.append("")

        for i, appt in enumerate(appointments[:5], 1):  # Máximo 5 citas
            # Parsear datetime
            start_at = datetime.fromisoformat(appt['start_at'].replace('Z', '+00:00'))

            # Formatear fecha y hora
            date_str = start_at.strftime("%A %d de %B")  # "Viernes 05 de diciembre"
            time_str = start_at.strftime("%I:%M %p")  # "03:00 PM"

            service_name = appt.get('service_name', 'Servicio')
            business_name = appt.get('business_name', '')
            status = appt.get('status', 'scheduled')

            # Emoji según estado
            status_emoji = {
                'scheduled': '📅',
                'confirmed': '✅',
                'pending_confirmation': '⏰'
            }.get(status, '📅')

            lines.append(f"{status_emoji} **Cita {i}**")
            lines.append(f"   📅 {date_str}")
            lines.append(f"   ⏰ {time_str}")
            lines.append(f"   ✂️ {service_name}")
            lines.append(f"   📍 {business_name}")
            lines.append("")

        if len(appointments) > 5:
            lines.append(f"... y {len(appointments) - 5} citas más")
            lines.append("")

        lines.append("¿Quieres modificar o cancelar alguna? Solo dime cuál 😊")

        return "\n".join(lines)

    except Exception as e:
        return f"Hubo un problema consultando tus citas. Por favor intenta de nuevo en un momento."

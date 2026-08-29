"""Respuestas sobre el negocio solo con datos de base de datos (sin LLM)."""
from app.core.response_builder import BotReply
from app.services import db_service
from app.utils import telegram_ui


async def handle_business_info(business_id: int) -> BotReply:
    binfo = await db_service.get_business(business_id)
    sch = await db_service.get_business_schedule(business_id)
    weekday_names = [
        "Lunes",
        "Martes",
        "Miércoles",
        "Jueves",
        "Viernes",
        "Sábado",
        "Domingo",
    ]
    lines = [f"📍 {binfo.get('name', 'Negocio')}"]
    desc = (binfo.get("description") or "").strip()
    if desc:
        lines.append(desc)
    addr = (binfo.get("address") or "").strip()
    if addr:
        lines.append(f"Dirección: {addr}")
    lines.append("")
    lines.append("Horarios:")
    if not sch:
        lines.append("  • No hay horarios cargados todavía.")
    else:
        for r in sch:
            wd = weekday_names[r.get("weekday", 0)]
            lines.append(f"  • {wd}: {r.get('start_time')} - {r.get('end_time')}")
    return BotReply("\n".join(lines), keyboard=telegram_ui.with_footer([]))


async def handle_business_services(business_id: int) -> BotReply:
    services = await db_service.get_business_services(business_id)
    business = await db_service.get_business(business_id)
    bname = business.get("name", "el negocio")

    if not services:
        return BotReply(
            f"Por ahora <b>{bname}</b> no tiene servicios cargados en el sistema.\n\n"
            "Puedo ayudarte con horarios, ubicación o con otras consultas del negocio.",
            keyboard=telegram_ui.with_footer([]),
        )

    lines = [f"Estos son los servicios de <b>{bname}</b>:", ""]
    for s in services:
        lines.append(f"  • {s['name']} — ${s['price']}, {s['duration_minutes']} min")
    return BotReply(
        "\n".join(lines),
        keyboard=telegram_ui.with_footer(telegram_ui.service_buttons(services)),
    )

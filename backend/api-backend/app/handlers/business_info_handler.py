"""Respuestas sobre el negocio solo con datos de base de datos (sin LLM)."""
from app.services import db_service


async def handle_business_info(business_id: int) -> str:
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
    return "\n".join(lines)


async def handle_business_services(business_id: int) -> str:
    services = await db_service.get_business_services(business_id)
    business = await db_service.get_business(business_id)
    bname = business.get("name", "el negocio")

    if not services:
        return (
            f"Por ahora <b>{bname}</b> no tiene servicios cargados en el sistema.\n\n"
            "Puedo ayudarte con horarios, ubicación o con otras consultas del negocio."
        )

    lines = [f"Estos son los servicios de <b>{bname}</b>:", ""]
    for i, service in enumerate(services, 1):
        lines.append(
            f"  {i}. {service['name']} (${service['price']}, {service['duration_minutes']} min)"
        )
    lines.append("")
    lines.append("Si querés, decime cuál te interesa y te ayudo a agendar.")
    return "\n".join(lines)

"""
whatsapp_renderer: BotReply (teclado Telegram) → payload interactivo de WhatsApp.
Reglas: 0 opciones → texto; ≤3 → botones; 4..10 → lista (con navegación si cabe);
>10 → primeras 7 + fila de paginación; títulos recortados; HTML → *bold*.
"""
from datetime import datetime

from app.core.response_builder import BotReply
from app.services.whatsapp_renderer import render_bot_reply
from app.utils.telegram_ui import (
    confirm_booking_buttons,
    day_buttons,
    main_menu_reply,
    service_buttons,
    time_grid_buttons,
    with_footer,
)


def _slots(hours):
    return [
        {
            "start_time": f"{h}:00 AM" if h < 12 else (f"{h-12}:00 PM" if h > 12 else "12:00 PM"),
            "start_datetime": f"2026-08-30T{h:02d}:00:00",
        }
        for h in hours
    ]


def test_no_keyboard_renders_text():
    render = render_bot_reply(BotReply("Listo"))

    assert render.kind == "text"
    assert render.text == "Listo"
    assert render.buttons == []
    assert render.sections == []


def test_empty_own_options_renders_text():
    # with_footer([]) = solo botones nav → no son opciones de decisión → texto puro
    reply = BotReply("Sin opciones", keyboard=with_footer([]))

    render = render_bot_reply(reply)

    assert render.kind == "text"
    assert render.text == "Sin opciones"


def test_two_options_renders_reply_buttons():
    reply = BotReply("¿Confirmas?", keyboard=confirm_booking_buttons())

    render = render_bot_reply(reply)

    assert render.kind == "button"
    assert [b["id"] for b in render.buttons] == ["confirm_yes", "confirm_no"]
    assert all(len(b["title"]) <= 20 for b in render.buttons)
    assert render.sections == []


def test_main_menu_renders_list_without_numbering():
    reply = main_menu_reply(customer_name="Ana")

    render = render_bot_reply(reply)

    assert render.kind == "list"
    assert "Elegí una opción" in render.text
    assert "1)" not in render.text  # usa el texto sin numeración, no text_plain
    assert len(render.sections) == 1
    assert render.sections[0]["title"] == "Opciones"
    assert [r["id"] for r in render.sections[0]["rows"]] == [
        "menu_agendar",
        "menu_ver_citas",
        "menu_cambiar",
        "menu_cancelar",
        "menu_horarios",
    ]


def test_services_with_footer_renders_list_with_nav_section():
    services = [
        {"id": i, "name": f"Servicio {i}"}
        for i in range(1, 6)
    ]
    reply = BotReply("Elegí un servicio", keyboard=with_footer(service_buttons(services)))

    render = render_bot_reply(reply)

    assert render.kind == "list"
    titles = [s["title"] for s in render.sections]
    assert "Servicios" in titles
    assert "Navegación" in titles
    servicios = next(s for s in render.sections if s["title"] == "Servicios")
    assert len(servicios["rows"]) == 5
    nav = next(s for s in render.sections if s["title"] == "Navegación")
    assert [r["id"] for r in nav["rows"]] == ["nav_back", "nav_menu", "nav_exit"]


def test_slots_over_ten_truncated_with_pagination():
    slots = _slots(list(range(9, 23)))  # 14 slots → página 0 con "Después ▶"
    reply = BotReply(
        "Horarios disponibles",
        keyboard=with_footer(time_grid_buttons(slots, "2026-08-30", page=0)),
    )

    render = render_bot_reply(reply)

    assert render.kind == "list"
    horarios = next(s for s in render.sections if s["title"].startswith("Horarios"))
    assert len(horarios["rows"]) == 7
    otros = next(s for s in render.sections if s["title"] == "Opciones")
    assert otros["rows"][0]["id"] == "slots_page_1"
    assert otros["rows"][0]["title"] == "Después ▶"
    assert render.dropped >= 5  # 14 - 7 + nav descartado


def test_day_rows_grouped_by_week_sections():
    days = [
        {"date": "2026-08-24", "label": "lun 24"},
        {"date": "2026-08-25", "label": "mar 25"},
        {"date": "2026-08-26", "label": "mié 26"},
        {"date": "2026-08-31", "label": "lun 31"},
    ]
    now = datetime(2026, 8, 30, 12, 0)
    reply = BotReply("Elegí un día", keyboard=day_buttons(days))

    render = render_bot_reply(reply, now=now)

    titles = {s["title"] for s in render.sections}
    assert titles == {"Esta semana", "Próxima semana"}
    esta = next(s for s in render.sections if s["title"] == "Esta semana")
    proxima = next(s for s in render.sections if s["title"] == "Próxima semana")
    assert [r["id"] for r in esta["rows"]] == [
        "day_2026-08-24",
        "day_2026-08-25",
        "day_2026-08-26",
    ]
    assert [r["id"] for r in proxima["rows"]] == ["day_2026-08-31"]


def test_service_titles_clipped_to_24_chars():
    services = [{"id": 1, "name": "Corte de cabello con barba y arreglo facial completo"}]
    reply = BotReply("Elegí un servicio", keyboard=service_buttons(services))

    render = render_bot_reply(reply)

    assert render.kind == "button"
    assert len(render.buttons[0]["title"]) <= 24
    assert render.buttons[0]["title"].endswith("…")
    assert render.buttons[0]["id"] == "service_1"


def test_text_strips_html_and_converts_bold():
    reply = BotReply("Corte <b>Premium</b> con <i>detalles</i>")

    render = render_bot_reply(reply)

    assert render.kind == "text"
    assert render.text == "Corte *Premium* con _detalles_"


def test_callback_token_is_stripped_from_ids():
    reply = BotReply(
        "Opciones",
        keyboard=[
            [{"text": "✅ Confirmar", "callback_data": "confirm_yes|abc123"}],
        ],
    )

    render = render_bot_reply(reply)

    assert render.kind == "button"
    assert render.buttons[0]["id"] == "confirm_yes"

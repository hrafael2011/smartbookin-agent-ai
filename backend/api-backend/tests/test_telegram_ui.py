"""
Builders de teclados inline y convención de callback_data (app/utils/telegram_ui.py).
"""
from datetime import date as date_type

from app.core.response_builder import BotReply
from app.utils import telegram_ui


# ── Footer centralizado ───────────────────────────────────────────────────────

def test_build_nav_footer_is_single_row_with_three_actions():
    footer = telegram_ui.build_nav_footer()

    assert len(footer) == 3
    assert [b["callback_data"] for b in footer] == ["nav_back", "nav_menu", "nav_exit"]


def test_with_footer_appends_footer_row_to_own_rows():
    rows = [[{"text": "A", "callback_data": "service_1"}]]

    full = telegram_ui.with_footer(rows)

    assert len(full) == 2
    assert [b["callback_data"] for b in full[-1]] == ["nav_back", "nav_menu", "nav_exit"]


# ── Menú principal ────────────────────────────────────────────────────────────

def test_main_menu_keyboard_has_five_menu_actions():
    kb = telegram_ui.main_menu_keyboard()

    callbacks = [btn["callback_data"] for row in kb for btn in row]
    assert callbacks == [
        "menu_agendar",
        "menu_ver_citas",
        "menu_cambiar",
        "menu_cancelar",
        "menu_horarios",
    ]


def test_guided_menu_reply_is_bot_reply_with_main_menu_keyboard():
    reply = telegram_ui.guided_menu_reply("Ana")

    assert isinstance(reply, BotReply)
    assert "Ana" in reply
    assert "Elegí una opción" in reply
    assert reply.keyboard == telegram_ui.main_menu_keyboard()


def test_guided_menu_reply_has_no_numbered_options():
    reply = telegram_ui.guided_menu_reply("Ana")

    assert "1) Agendar cita" not in reply
    assert "Elegí una opción" in reply
    assert reply.keyboard == telegram_ui.main_menu_keyboard()


def test_main_menu_reply_with_prefix():
    reply = telegram_ui.main_menu_reply("Listo.", "Ana")

    assert reply.startswith("Listo.")
    assert "Elegí una opción" in reply
    assert reply.keyboard == telegram_ui.main_menu_keyboard()


def test_main_menu_reply_has_numbered_text_plain():
    reply = telegram_ui.main_menu_reply("Listo.", "Ana")

    assert "1) Agendar cita" in reply.text_plain
    assert "Elegí una opción" in reply
    assert reply.text_plain.startswith("Listo.")


# ── Servicios ─────────────────────────────────────────────────────────────────

def test_service_buttons_use_ids_two_per_row():
    services = [
        {"id": 1, "name": "Corte"},
        {"id": 2, "name": "Cerquillos"},
        {"id": 3, "name": "Barba"},
    ]

    rows = telegram_ui.service_buttons(services)

    assert rows[0] == [
        {"text": "Corte", "callback_data": "service_1"},
        {"text": "Cerquillos", "callback_data": "service_2"},
    ]
    assert rows[1] == [{"text": "Barba", "callback_data": "service_3"}]


# ── Días ──────────────────────────────────────────────────────────────────────

def test_day_buttons_use_iso_date_in_callback():
    days = [
        {"date": "2026-08-29", "label": "Vie 29"},
        {"date": "2026-08-30", "label": "Sáb 30"},
    ]

    rows = telegram_ui.day_buttons(days)

    assert rows[0][0] == {"text": "Vie 29", "callback_data": "day_2026-08-29"}
    assert rows[1][0] == {"text": "Sáb 30", "callback_data": "day_2026-08-30"}


# ── Grilla de horarios ────────────────────────────────────────────────────────

def _slot(start_datetime: str, start_time: str = "9:00 AM") -> dict:
    return {"start_time": start_time, "start_datetime": start_datetime}


def test_time_grid_three_columns_with_hhmm_callbacks():
    slots = [_slot(f"2026-08-28T{h:02d}:00:00+00:00") for h in range(9, 12)]

    rows = telegram_ui.time_grid_buttons(slots, "2026-08-28", page=0)

    assert len(rows[0]) == 3
    assert rows[0][0]["callback_data"] == "time_2026-08-28_09:00"
    assert rows[0][1]["callback_data"] == "time_2026-08-28_10:00"
    assert rows[0][2]["callback_data"] == "time_2026-08-28_11:00"


def test_time_grid_paginates_after_12_slots():
    slots = [_slot(f"2026-08-28T{9 + i // 2:02d}:{30 * (i % 2):02d}:00+00:00", "10:00 AM") for i in range(13)]

    page0 = telegram_ui.time_grid_buttons(slots, "2026-08-28", page=0)
    page1 = telegram_ui.time_grid_buttons(slots, "2026-08-28", page=1)

    # Página 0: 4 filas de 3 + fila de paginación con "Después ▶"
    assert len(page0) == 5
    assert page0[-1] == [{"text": "Después ▶", "callback_data": "slots_page_1"}]
    # Página 1: 1 fila (1 slot) + fila de paginación con "◀ Antes"
    assert len(page1) == 2
    assert page1[-1] == [{"text": "◀ Antes", "callback_data": "slots_page_0"}]


def test_time_grid_no_pagination_row_when_fits():
    slots = [_slot(f"2026-08-28T{9 + i:02d}:00:00+00:00", "10:00 AM") for i in range(12)]

    rows = telegram_ui.time_grid_buttons(slots, "2026-08-28", page=0)

    assert len(rows) == 4
    assert all(b["callback_data"].startswith("time_") for row in rows for b in row)


# ── Citas (cancelar / modificar) ──────────────────────────────────────────────

def test_appointment_buttons_short_label_and_ids():
    appointments = [
        {
            "id": 11,
            "service_name": "Corte",
            "start_at": "2026-08-28T09:00:00+00:00",  # convenio: hora local estampada como UTC
        },
    ]

    rows = telegram_ui.appointment_buttons(appointments, prefix="cancel_appt")

    assert rows[0][0]["text"] == "Corte · vie 28, 9:00 AM"
    assert rows[0][0]["callback_data"] == "cancel_appt_11"


def test_appointment_buttons_modify_prefix():
    appointments = [
        {
            "id": 12,
            "service_name": "Barba",
            "start_at": "2026-08-29T11:00:00+00:00",  # convenio: hora local estampada como UTC
        },
    ]

    rows = telegram_ui.appointment_buttons(appointments, prefix="modify_appt")

    assert rows[0][0]["text"] == "Barba · sáb 29, 11:00 AM"
    assert rows[0][0]["callback_data"] == "modify_appt_12"


# ── Confirmaciones ────────────────────────────────────────────────────────────

def test_confirm_booking_buttons():
    rows = telegram_ui.confirm_booking_buttons()

    assert [b["callback_data"] for b in rows[0]] == ["confirm_yes", "confirm_no"]


def test_cancel_confirm_buttons():
    rows = telegram_ui.cancel_confirm_buttons()

    assert [b["callback_data"] for b in rows[0]] == ["cancel_confirm_yes", "cancel_confirm_no"]


def test_resume_buttons():
    rows = telegram_ui.resume_buttons()

    assert [b["callback_data"] for b in rows[0]] == ["resume_yes", "resume_no"]


# ── Meses / semanas (calendario) ──────────────────────────────────────────────

def test_month_and_week_buttons():
    months = [{"index": 1, "label": "Septiembre 2026"}]
    weeks = [{"index": 2, "label": "Semana del 1 al 7", "day_count": 3}]

    assert telegram_ui.month_buttons(months)[0][0]["callback_data"] == "month_1"
    assert telegram_ui.week_buttons(weeks)[0][0]["callback_data"] == "week_2"


# ── Parser de callback_data ───────────────────────────────────────────────────

def test_parse_inline_callback_namespaces():
    assert telegram_ui.parse_inline_callback("service_3") == {"ns": "service", "value": "3"}
    assert telegram_ui.parse_inline_callback("day_2026-08-29") == {"ns": "day", "value": "2026-08-29"}
    assert telegram_ui.parse_inline_callback("time_2026-08-29_09:00") == {
        "ns": "time",
        "value": ("2026-08-29", "09:00"),
    }
    assert telegram_ui.parse_inline_callback("slots_page_2") == {"ns": "slots_page", "value": "2"}
    assert telegram_ui.parse_inline_callback("menu_agendar") == {"ns": "menu", "value": "agendar"}
    assert telegram_ui.parse_inline_callback("nav_back") == {"ns": "nav", "value": "back"}
    assert telegram_ui.parse_inline_callback("confirm_yes") == {"ns": "confirm", "value": "yes"}
    assert telegram_ui.parse_inline_callback("cancel_appt_11") == {"ns": "cancel_appt", "value": "11"}
    assert telegram_ui.parse_inline_callback("cancel_confirm_no") == {
        "ns": "cancel_confirm",
        "value": "no",
    }
    assert telegram_ui.parse_inline_callback("modify_appt_12") == {"ns": "modify_appt", "value": "12"}
    assert telegram_ui.parse_inline_callback("month_1") == {"ns": "month", "value": "1"}
    assert telegram_ui.parse_inline_callback("week_2") == {"ns": "week", "value": "2"}
    assert telegram_ui.parse_inline_callback("resume_yes") == {"ns": "resume", "value": "yes"}


def test_slot_by_hhmm_finds_exact_slot():
    slots = [
        {"start_time": "9:00 AM", "start_datetime": "2026-08-28T09:00:00+00:00"},
        {"start_time": "9:15 AM", "start_datetime": "2026-08-28T09:15:00+00:00"},
    ]

    assert telegram_ui.slot_by_hhmm(slots, "09:15") == slots[1]
    assert telegram_ui.slot_by_hhmm(slots, "10:00") is None


def test_parse_inline_callback_rejects_unknown_or_plain_text():
    assert telegram_ui.parse_inline_callback("hola") is None
    assert telegram_ui.parse_inline_callback("5") is None
    assert telegram_ui.parse_inline_callback("nav_") is None
    assert telegram_ui.parse_inline_callback("day_2026-13-45") is None
    assert telegram_ui.parse_inline_callback("time_2026-08-29_9am") is None
    assert telegram_ui.parse_inline_callback("time_2026-08-29_99:99") is None

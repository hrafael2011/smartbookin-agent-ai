"""render_slots_reply: grilla de horarios paginada con footer (booking_handler)."""
from app.core.response_builder import BotReply
from app.handlers.booking_handler import render_slots_reply


def _pending(slots):
    return {"date": "2026-08-28", "available_slots": slots}


def _slots(count):
    return [
        {"start_time": "10:00 AM", "start_datetime": f"2026-08-28T{10 + i:02d}:00:00+00:00"}
        for i in range(count)
    ]


def test_render_slots_reply_is_bot_reply_with_grid_and_footer():
    reply = render_slots_reply(_pending(_slots(3)))

    assert isinstance(reply, BotReply)
    assert "viernes 28 de agosto" in reply
    callbacks = [b["callback_data"] for row in reply.keyboard for b in row]
    assert callbacks[0] == "time_2026-08-28_10:00"
    # Última fila: footer centralizado
    assert [b["callback_data"] for b in reply.keyboard[-1]] == ["nav_back", "nav_menu", "nav_exit"]


def test_render_slots_reply_page_one_has_prev_pagination():
    reply = render_slots_reply(_pending(_slots(13)), page=1)

    page_row = reply.keyboard[-2]
    assert [b["callback_data"] for b in page_row] == ["slots_page_0"]
    assert reply.keyboard[-1][0]["callback_data"] == "nav_back"


def test_render_slots_reply_preserves_footer_below_pagination():
    reply = render_slots_reply(_pending(_slots(13)), page=0)

    assert [b["callback_data"] for b in reply.keyboard[-1]] == ["nav_back", "nav_menu", "nav_exit"]
    assert reply.keyboard[-2] == [{"text": "Después ▶", "callback_data": "slots_page_1"}]

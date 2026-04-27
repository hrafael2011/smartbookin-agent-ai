import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List
import sys
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.database import AsyncSessionLocal
from app.models import Business
from app.services.telegram_inbound import process_telegram_update
from app.services.telegram_client import telegram_client
from app.services.nlu_engine import nlu_engine
from app.services.telegram_link_service import clear_user_binding, tg_chat_key
from app.services.conversation_manager import conversation_manager


def _tomorrow() -> str:
    return (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")


async def _pick_business() -> Dict[str, Any]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Business).where(Business.is_active == True).order_by(Business.id).limit(1)
        )
        b = result.scalars().first()
        if not b:
            raise RuntimeError("No se encontró negocio para pruebas.")
        return {"id": b.id, "name": b.name, "token": b.telegram_invite_token}


def _make_payload(chat_id: str, text: str) -> Dict[str, Any]:
    return {
        "message": {
            "message_id": 1,
            "date": int(datetime.utcnow().timestamp()),
            "chat": {"id": int(chat_id)},
            "text": text,
        }
    }


async def _fake_nlu_process(message: str, context: Dict, business_id: str, customer_context: str = "") -> Dict:
    t = (message or "").strip().lower()
    entities: Dict[str, Any] = {}
    intent = "general_question"
    confidence = 0.91

    if any(k in t for k in ["cita", "agendar", "turno", "reservar", "horario", "disponible"]):
        intent = "book_appointment"
    if "cancel" in t:
        intent = "cancel_appointment"
    if "cambiar" in t or "modificar" in t:
        intent = "modify_appointment"
    if "mis citas" in t or "ver citas" in t:
        intent = "check_appointment"

    if "corte" in t:
        entities["service"] = "Corte"
        intent = "book_appointment"
    if "cerquillo" in t:
        entities["service"] = "Cerquillos"
        intent = "book_appointment"
    if "mañana" in t:
        entities["date"] = _tomorrow()
        intent = "book_appointment"
    if "10" in t:
        entities["time"] = "10:00"
        intent = "book_appointment"
    elif "11" in t:
        entities["time"] = "11:00"
        intent = "book_appointment"
    elif "9" in t:
        entities["time"] = "09:00"
        intent = "book_appointment"

    return {
        "intent": intent,
        "confidence": confidence,
        "entities": entities,
        "missing": [],
        "response_text": "OK",
        "raw_understanding": message,
    }


async def run() -> None:
    biz = await _pick_business()
    chat_id = "991234001"
    user_key = tg_chat_key(chat_id)

    await clear_user_binding(chat_id)
    await conversation_manager.delete_all_contexts_for_phone_number(user_key)

    sent: List[Dict[str, str]] = []
    old_send = telegram_client.send_text_message
    old_nlu = nlu_engine.process

    async def _capture_send(chat_id: str, message: str):
        sent.append({"chat_id": chat_id, "message": message})
        return {"ok": True}

    nlu_engine.process = _fake_nlu_process  # type: ignore
    telegram_client.send_text_message = _capture_send  # type: ignore

    scenarios = [
        ("start_link", [f"/start {biz['token']}"]),
        ("first_name", ["Carlos"]),
        ("yes_after_prompt", ["sí"]),
        ("menu_service_by_number", ["1", "1", "mañana", "10:00 am", "sí"]),
        ("menu_service_by_text", ["1", "corte", "mañana", "11:00", "sí"]),
        ("availability_question", ["quiero saber horarios disponibles mañana para corte"]),
        ("time_not_available_flow", ["quiero cita de corte mañana a las 23:00"]),
    ]

    for name, messages in scenarios:
        print(f"\n===== SCENARIO: {name} =====")
        for m in messages:
            before = len(sent)
            await process_telegram_update(_make_payload(chat_id, m))
            new_msgs = sent[before:]
            print(f"USER: {m}")
            if not new_msgs:
                print("BOT: <sin respuesta>")
            for out in new_msgs:
                txt = out["message"].replace("\n", " | ")
                print(f"BOT: {txt}")

    # restore
    telegram_client.send_text_message = old_send  # type: ignore
    nlu_engine.process = old_nlu  # type: ignore


if __name__ == "__main__":
    asyncio.run(run())

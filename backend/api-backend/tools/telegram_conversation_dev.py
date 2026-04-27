#!/usr/bin/env python3
"""
Pruebas reproducibles del bot Telegram sin depender del chat en el teléfono.

 Modo in-process (recomendado): ejecuta process_telegram_update, intercepta sendMessage
  e imprime USER:/BOT: en consola. Requiere DATABASE_URL (misma DB que el api-backend).

  Modo http: envía JSON al webhook (servidor en marcha). El bot responde por Telegram real salvo que hayas mockeado el cliente en otro entorno.

Uso típico (desde api-backend/, con venv activado):

  python3 tools/telegram_conversation_dev.py in-process \\
    --chat-id 991234777 \\
    --invite-token TU_TOKEN_DEL_PANEL \\
    --reset \\
    --messages "/start TU_TOKEN_DEL_PANEL" "Ana" "1" "quiero turno mañana"

  python3 tools/telegram_conversation_dev.py http \\
    --base-url http://localhost:8000 \\
    --chat-id 991234777 \\
    --messages "hola"
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _payload(chat_id: str, text: str) -> Dict[str, Any]:
    ts = int(datetime.now(timezone.utc).timestamp())
    return {
        "update_id": ts,
        "message": {
            "message_id": ts % 1_000_000_000,
            "date": ts,
            "chat": {"id": int(chat_id), "type": "private"},
            "from": {"id": int(chat_id), "is_bot": False, "first_name": "Dev"},
            "text": text,
        },
    }


async def _run_http(base_url: str, chat_id: str, messages: List[str]) -> None:
    import httpx

    url = base_url.rstrip("/") + "/webhooks/telegram"
    async with httpx.AsyncClient(timeout=120.0) as client:
        for text in messages:
            body = _payload(chat_id, text)
            print(f"\n>>> POST {url}\nUSER: {text!r}")
            r = await client.post(url, json=body)
            print(f"HTTP {r.status_code}: {r.text[:500]}")


async def _run_in_process(
    chat_id: str,
    messages: List[str],
    *,
    reset: bool,
    capture_nlu: bool,
) -> None:
    from app.services.telegram_inbound import process_telegram_update
    from app.services.telegram_client import telegram_client
    from app.services.nlu_engine import nlu_engine
    from app.services.telegram_link_service import clear_user_binding, tg_chat_key
    from app.services.conversation_manager import conversation_manager

    user_key = tg_chat_key(chat_id)
    if reset:
        await clear_user_binding(chat_id)
        await conversation_manager.delete_all_contexts_for_phone_number(user_key)

    sent: List[str] = []
    old_send = telegram_client.send_text_message
    old_nlu = nlu_engine.process

    async def _capture_send(chat_id: str, message: str) -> Dict[str, Any]:
        sent.append(message)
        print(f"BOT: {message.replace(chr(10), ' | ')}")
        return {"ok": True}

    async def _nlu_with_log(msg: str, ctx: Dict, business_id, customer_context: str = ""):
        out = await old_nlu(msg, ctx, business_id, customer_context=customer_context)
        if capture_nlu:
            print(f"    [NLU] intent={out.get('intent')} conf={out.get('confidence')} entities={out.get('entities')}")
        return out

    telegram_client.send_text_message = _capture_send  # type: ignore
    if capture_nlu:
        nlu_engine.process = _nlu_with_log  # type: ignore

    try:
        for text in messages:
            sent.clear()
            print(f"\nUSER: {text!r}")
            await process_telegram_update(_payload(chat_id, text))
            if not sent:
                print("BOT: <sin sendMessage — revisá logs o flujo temprano (/start, vínculo)>")
    finally:
        telegram_client.send_text_message = old_send  # type: ignore
        nlu_engine.process = old_nlu  # type: ignore


def _parse_messages(args: argparse.Namespace) -> List[str]:
    if args.file:
        path = Path(args.file)
        lines = path.read_text(encoding="utf-8").splitlines()
        return [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]
    if args.messages:
        return list(args.messages)
    print("Leyendo mensajes desde stdin (una línea por mensaje, EOF con Ctrl+D):", file=sys.stderr)
    return [ln.strip() for ln in sys.stdin if ln.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulación de conversación Telegram (dev)")
    sub = parser.add_subparsers(dest="mode", required=True)

    p_http = sub.add_parser("http", help="POST al webhook HTTP (servidor corriendo)")
    p_http.add_argument("--base-url", default="http://localhost:8000", help="Origen del api-backend")
    p_http.add_argument("--chat-id", required=True, help="chat.id entero como string")
    p_http.add_argument("--messages", nargs="*", help="Mensajes en orden")
    p_http.add_argument("--file", "-f", help="Archivo con un mensaje por línea (# comentario)")

    p_in = sub.add_parser("in-process", help="Misma lógica que producción, respuestas en consola")
    p_in.add_argument("--chat-id", default="991234777", help="ID de chat fijo para pruebas")
    p_in.add_argument("--messages", nargs="*", help="Mensajes en orden")
    p_in.add_argument("--file", "-f", help="Archivo con un mensaje por línea")
    p_in.add_argument("--reset", action="store_true", help="Limpia binding y contexto para este chat")
    p_in.add_argument("--log-nlu", action="store_true", help="Imprime intent/entities tras cada NLU")

    args = parser.parse_args()
    messages = _parse_messages(args)
    if not messages:
        print("No hay mensajes.", file=sys.stderr)
        sys.exit(2)

    if args.mode == "http":
        asyncio.run(_run_http(args.base_url, args.chat_id, messages))
    else:
        asyncio.run(
            _run_in_process(
                args.chat_id,
                messages,
                reset=args.reset,
                capture_nlu=args.log_nlu,
            )
        )


if __name__ == "__main__":
    main()

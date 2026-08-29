"""
Cliente para Telegram Bot API
"""
import logging
from typing import Dict, Optional, List

import httpx

from app.config import config

logger = logging.getLogger(__name__)


class TelegramClient:
    """Cliente para enviar mensajes por Telegram Bot API"""

    def __init__(self):
        self.api_url = config.TELEGRAM_API_BASE_URL
        self.timeout = 30

    async def send_text_message(
        self,
        chat_id: str,
        message: str,
        reply_markup: Optional[Dict] = None,
    ) -> Dict:
        """
        Envía un mensaje de texto (con reply_markup opcional, ej. inline_keyboard).
        """
        if not config.TELEGRAM_BOT_TOKEN:
            logger.error("TELEGRAM_BOT_TOKEN no está definido; no se puede enviar mensajes al chat.")
            raise RuntimeError("TELEGRAM_BOT_TOKEN missing")

        url = f"{self.api_url}/sendMessage"

        data: Dict = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
        }
        if reply_markup:
            data["reply_markup"] = reply_markup

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=data)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                body = (e.response.text or "")[:500]
                logger.error(
                    "Telegram sendMessage falló (%s): %s",
                    e.response.status_code,
                    body,
                )
                raise
            return response.json()

    async def send_inline_keyboard(
        self,
        chat_id: str,
        body_text: str,
        rows: List[List[Dict[str, str]]],
    ) -> Dict:
        """
        Envía un mensaje con Inline Keyboard.

        ``rows`` es una lista de filas; cada fila una lista de botones
        ``{"text": "...", "callback_data": "..."}`` (ver app/utils/telegram_ui.py).
        """
        return await self.send_text_message(
            chat_id=chat_id,
            message=body_text,
            reply_markup={"inline_keyboard": rows},
        )

    def extract_message_from_webhook(self, payload: Dict) -> Optional[Dict]:
        """
        Extrae información del mensaje desde el webhook de Telegram
        
        Payload examples:
        - Regular message: {"message": {"chat": {"id": 123}, "text": "Hi"}}
        - Callback query: {"callback_query": {"message": {"chat": {"id": 123}}, "data": "confirm_yes"}}
        """
        try:
            msg_obj = None
            if "message" in payload:
                msg_obj = payload["message"]
            elif "edited_message" in payload:
                msg_obj = payload["edited_message"]

            if msg_obj is not None:
                message = msg_obj
                chat_id = str(message.get("chat", {}).get("id"))

                return {
                    "message_id": str(message.get("message_id")),
                    "from": chat_id,
                    "timestamp": str(message.get("date")),
                    "type": "text",
                    "text": message.get("text", ""),
                }

            if "callback_query" in payload:
                callback = payload["callback_query"]
                message = callback.get("message") or {}
                chat_id = str(message.get("chat", {}).get("id"))
                if not message or not chat_id or chat_id == "None":
                    logger.warning(
                        "telegram callback_query sin message/chat; ignorado (data=%s)",
                        (callback.get("data") or "")[:50],
                    )
                    return None
                return {
                    "message_id": str(callback.get("id")),  # único por toque (dedupe)
                    "from": chat_id,
                    "timestamp": str(message.get("date")),
                    "type": "interactive",
                    "button_payload": callback.get("data"),
                    "text": callback.get("data"),
                }

            return None

        except (KeyError, IndexError, TypeError) as e:
            print(f"Error parsing Telegram webhook payload: {e}")
            return None


# Singleton instance
telegram_client = TelegramClient()

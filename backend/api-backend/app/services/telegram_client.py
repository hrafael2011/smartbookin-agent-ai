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

    async def send_text_message(self, chat_id: str, message: str) -> Dict:
        """
        Envía un mensaje de texto
        """
        if not config.TELEGRAM_BOT_TOKEN:
            logger.error("TELEGRAM_BOT_TOKEN no está definido; no se puede enviar mensajes al chat.")
            raise RuntimeError("TELEGRAM_BOT_TOKEN missing")

        url = f"{self.api_url}/sendMessage"

        data = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
        }

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

    async def send_interactive_buttons(
        self,
        chat_id: str,
        body_text: str,
        buttons: List[Dict[str, str]],
    ) -> Dict:
        """
        Envía un mensaje con botones interactivos (Inline Keyboard)
        
        Buttons format: [{"id": "btn_1", "title": "Sí, confirmo"}, ...]
        """
        url = f"{self.api_url}/sendMessage"

        # Construir Inline Keyboard
        inline_keyboard = []
        for btn in buttons:
            inline_keyboard.append([{
                "text": btn.get("title", "Opción"),
                "callback_data": btn.get("id", "btn")
            }])

        data = {
            "chat_id": chat_id,
            "text": body_text,
            "reply_markup": {
                "inline_keyboard": inline_keyboard
            },
            "parse_mode": "HTML"
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=data)
            response.raise_for_status()
            return response.json()

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
                message = callback.get("message", {})
                chat_id = str(message.get("chat", {}).get("id"))
                
                return {
                    "message_id": str(message.get("message_id")),
                    "from": chat_id,
                    "timestamp": str(message.get("date")),
                    "type": "interactive",
                    "button_payload": callback.get("data"),
                    "text": callback.get("data"), # Usamos el data como texto para el NLU si es necesario
                }
                
            return None

        except (KeyError, IndexError, TypeError) as e:
            print(f"Error parsing Telegram webhook payload: {e}")
            return None


# Singleton instance
telegram_client = TelegramClient()

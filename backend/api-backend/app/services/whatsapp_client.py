"""
Cliente para Meta WhatsApp Business API
"""
import httpx
import hmac
import hashlib
from typing import Dict, Optional, List
from app.config import config


class WhatsAppClient:
    """Cliente para enviar mensajes por WhatsApp Business API"""

    def __init__(self):
        self.api_url = config.META_API_BASE_URL
        self.token = config.META_WABA_TOKEN
        self.app_secret = config.META_APP_SECRET
        self.timeout = 30

    def validate_signature(self, payload: bytes, signature: str) -> bool:
        """
        Valida la firma HMAC SHA256 de Meta

        Args:
            payload: Body del request (bytes)
            signature: Header X-Hub-Signature-256

        Returns:
            True si la firma es válida
        """
        if not signature or not self.app_secret:
            return False

        expected = hmac.new(
            self.app_secret.encode(), payload, hashlib.sha256
        ).hexdigest()

        expected_signature = f"sha256={expected}"

        return hmac.compare_digest(expected_signature, signature)

    async def send_text_message(
        self, to: str, message: str, phone_number_id: Optional[str] = None
    ) -> Dict:
        """
        Envía un mensaje de texto

        Args:
            to: Número de teléfono del destinatario (con código de país)
            message: Texto del mensaje
            phone_number_id: ID del número de WhatsApp Business (opcional)

        Returns:
            Response de Meta API
        """
        # En producción, phone_number_id vendría de la configuración del negocio
        if not phone_number_id:
            phone_number_id = config.META_PHONE_NUMBER_ID

        url = f"{self.api_url}/{phone_number_id}/messages"

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        data = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": False, "body": message},
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=data, headers=headers)
            response.raise_for_status()
            return response.json()

    async def send_interactive_buttons(
        self,
        to: str,
        body_text: str,
        buttons: List[Dict[str, str]],
        phone_number_id: Optional[str] = None,
    ) -> Dict:
        """
        Envía un mensaje con botones interactivos

        Args:
            to: Número de teléfono del destinatario
            body_text: Texto del mensaje
            buttons: Lista de botones [{"id": "btn_1", "title": "Sí, confirmo"}, ...]
                     Máximo 3 botones, máximo 20 caracteres por título

        Returns:
            Response de Meta API

        Ejemplo:
            await client.send_interactive_buttons(
                to="+18095551234",
                body_text="¿Confirmas tu asistencia?",
                buttons=[
                    {"id": "confirm_yes", "title": "✅ Sí, confirmo"},
                    {"id": "confirm_no", "title": "❌ No puedo ir"},
                    {"id": "reschedule", "title": "🔄 Reagendar"}
                ]
            )
        """
        if not phone_number_id:
            phone_number_id = config.META_PHONE_NUMBER_ID

        url = f"{self.api_url}/{phone_number_id}/messages"

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        # Construir botones
        button_list = []
        for i, btn in enumerate(buttons[:3]):  # Máximo 3 botones
            button_list.append({
                "type": "reply",
                "reply": {
                    "id": btn.get("id", f"btn_{i}"),
                    "title": btn.get("title", "Opción")[:20]  # Máximo 20 chars
                }
            })

        data = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body_text},
                "action": {"buttons": button_list}
            }
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=data, headers=headers)
            response.raise_for_status()
            return response.json()

    async def mark_as_read(
        self, message_id: str, phone_number_id: Optional[str] = None
    ) -> Dict:
        """
        Marca un mensaje como leído

        Args:
            message_id: ID del mensaje a marcar como leído
            phone_number_id: ID del número de WhatsApp Business

        Returns:
            Response de Meta API
        """
        if not phone_number_id:
            phone_number_id = config.META_PHONE_NUMBER_ID

        url = f"{self.api_url}/{phone_number_id}/messages"

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        data = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=data, headers=headers)
            response.raise_for_status()
            return response.json()

    def extract_message_from_webhook(self, payload: Dict) -> Optional[Dict]:
        """
        Extrae información del mensaje desde el webhook de Meta

        Args:
            payload: JSON del webhook

        Returns:
            {
                "message_id": "wamid.xxx",
                "from": "+18095551234",
                "timestamp": "1234567890",
                "type": "text",
                "text": "Hola, necesito una cita",
                "business_phone_number_id": "123456789",
                "button_payload": "confirm_yes"  # Si es respuesta de botón
            }
            o None si no es un mensaje válido
        """
        try:
            entry = payload.get("entry", [{}])[0]
            changes = entry.get("changes", [{}])[0]
            value = changes.get("value", {})

            # Obtener el mensaje
            messages = value.get("messages", [])
            if not messages:
                return None

            message = messages[0]

            # Información básica
            result = {
                "message_id": message.get("id"),
                "from": message.get("from"),
                "timestamp": message.get("timestamp"),
                "type": message.get("type"),
                "business_phone_number_id": value.get("metadata", {}).get(
                    "phone_number_id"
                ),
            }

            # Extraer texto según el tipo
            msg_type = message.get("type")

            if msg_type == "text":
                result["text"] = message.get("text", {}).get("body", "")

            elif msg_type == "interactive":
                # Respuesta de botón
                interactive = message.get("interactive", {})
                button_reply = interactive.get("button_reply", {})
                result["button_payload"] = button_reply.get("id")
                result["text"] = button_reply.get("title", "")

            elif msg_type == "button":
                # Botón rápido (quick reply)
                result["button_payload"] = message.get("button", {}).get("payload")
                result["text"] = message.get("button", {}).get("text", "")

            else:
                # Otros tipos no soportados aún
                return None

            return result

        except (KeyError, IndexError, TypeError) as e:
            print(f"Error parsing webhook payload: {e}")
            return None


# Singleton instance
whatsapp_client = WhatsAppClient()

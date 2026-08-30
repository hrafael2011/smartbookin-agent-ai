"""
Cliente para Meta WhatsApp Business API
"""
import httpx
import hmac
import hashlib
from typing import Dict, Optional, List
from app.config import config


class WhatsAppAPIError(Exception):
    """Error de la Graph API de Meta (código + mensaje estructurado).

    Códigos relevantes para recordatorios:
        131026 plantilla no aprobada · 131047 fuera de ventana de 24h ·
        131056 rate limit · 133010 número no registrado en WhatsApp.
    """

    def __init__(self, code: int, message: str):
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message


class WhatsAppClient:
    """Cliente para enviar mensajes por WhatsApp Business API"""

    def __init__(self):
        self.api_url = config.META_API_BASE_URL
        self.token = config.META_WABA_TOKEN
        self.app_secret = config.META_APP_SECRET
        self.timeout = 30

    def _resolve_phone_number_id(self, phone_number_id: Optional[str]) -> str:
        """Resuelve el phone_number_id del tenant para un envío.

        Multi-tenant: el caller DEBE pasar el id del negocio. Sin él, se cae al
        config global solo si está seteado con un valor real (dev/test); con el
        placeholder o vacío → ValueError (enviar por el número de otro tenant
        sería peor que fallar el envío).
        """
        pid = phone_number_id or config.META_PHONE_NUMBER_ID
        if not pid or pid == "YOUR_PHONE_NUMBER_ID":
            raise ValueError("phone_number_id requerido para envío multi-tenant")
        return pid

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
        phone_number_id = self._resolve_phone_number_id(phone_number_id)

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
        phone_number_id = self._resolve_phone_number_id(phone_number_id)

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

    @staticmethod
    def _clip(text: str, limit: int) -> str:
        """Trunca a `limit` code points, dejando el último para «…»."""
        if len(text) <= limit:
            return text
        return text[: limit - 1] + "…"

    async def send_list_message(
        self,
        to: str,
        body_text: str,
        sections: List[Dict],
        button_label: str = "Ver opciones",
        header_text: Optional[str] = None,
        phone_number_id: Optional[str] = None,
    ) -> Dict:
        """
        Envía un List Message (interactive.type=list) con secciones y filas.

        Límites de Meta: ≤10 filas totales (sumando secciones), 1..10 secciones,
        título de fila y de sección ≤24 chars, botón ≤20 chars, header ≤60,
        body ≤1024. Los títulos largos se truncan con «…»; ids >256 → error.
        """
        if not sections or len(sections) > 10:
            raise ValueError("sections debe tener entre 1 y 10 secciones")
        total_rows = sum(len(sec.get("rows", [])) for sec in sections)
        if total_rows > 10:
            raise ValueError("máximo 10 filas en total entre todas las secciones")
        for sec in sections:
            rows = sec.get("rows", [])
            if not rows or len(rows) > 10:
                raise ValueError("cada sección debe tener entre 1 y 10 filas")
            for row in rows:
                if len(row.get("id", "")) > 256:
                    raise ValueError("el id de una fila excede 256 caracteres")

        phone_number_id = self._resolve_phone_number_id(phone_number_id)

        url = f"{self.api_url}/{phone_number_id}/messages"

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        interactive: Dict = {
            "type": "list",
            "body": {"text": self._clip(body_text, 1024)},
            "action": {
                "button": self._clip(button_label, 20),
                "sections": [
                    {
                        "title": self._clip(sec.get("title", "Opciones"), 24),
                        "rows": [
                            self._list_row(row)
                            for row in sec["rows"]
                        ],
                    }
                    for sec in sections
                ],
            },
        }
        if header_text:
            interactive["header"] = {"type": "text", "text": self._clip(header_text, 60)}

        data = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": interactive,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=data, headers=headers)
            response.raise_for_status()
            return response.json()

    @staticmethod
    def _list_row(row: Dict) -> Dict:
        """Fila de lista: id intacto, título recortado a 24, descripción a 72."""
        result: Dict = {
            "id": row["id"],
            "title": WhatsAppClient._clip(row.get("title", ""), 24),
        }
        if row.get("description"):
            result["description"] = row["description"][:72]
        return result

    async def send_template_message(
        self,
        to: str,
        template_name: str,
        language_code: str,
        body_parameters: List[str],
        button_payloads: Optional[Dict[int, str]] = None,
        phone_number_id: Optional[str] = None,
    ) -> Dict:
        """
        Envía una plantilla aprobada por Meta (type=template).

        Args:
            to: Número del destinatario (E.164).
            template_name: Nombre de la plantilla aprobada (ej. appointment_reminder).
            language_code: Código de idioma de la plantilla (ej. "es").
            body_parameters: Valores de los placeholders {{1}}, {{2}}, … del cuerpo.
            button_payloads: {índice_botón: payload} para botones quick_reply de la
                plantilla (el payload del botón se rellena dinámicamente, ej. cita id).
            phone_number_id: ID del número del negocio (multi-tenant).

        Raises:
            WhatsAppAPIError: con el código de error de Meta (131026, 131047, …).
        """
        phone_number_id = self._resolve_phone_number_id(phone_number_id)

        url = f"{self.api_url}/{phone_number_id}/messages"

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        components: List[Dict] = [
            {
                "type": "body",
                "parameters": [
                    {"type": "text", "text": p} for p in body_parameters
                ],
            }
        ]
        if button_payloads:
            for index, payload in sorted(button_payloads.items()):
                components.append(
                    {
                        "type": "button",
                        "sub_type": "quick_reply",
                        "index": str(index),
                        "parameters": [{"type": "payload", "payload": payload}],
                    }
                )

        data = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
                "components": components,
            },
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=data, headers=headers)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                try:
                    err = response.json().get("error", {})
                    code = int(err.get("code", 0))
                    message = err.get("message", str(e))
                except (ValueError, TypeError):
                    code, message = 0, str(e)
                raise WhatsAppAPIError(code=code, message=message) from e
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
        phone_number_id = self._resolve_phone_number_id(phone_number_id)

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
                "button_payload": "confirm_yes",  # Si es respuesta de botón
                "list_payload": "slot_2026-08-30_09:00"  # Si es respuesta de lista
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
                # Sin mensajes: puede ser un status update (sent/delivered/read/failed).
                statuses = value.get("statuses", [])
                if statuses:
                    status = statuses[0]
                    return {
                        "type": "status_update",
                        "status": status.get("status"),
                        "message_id": status.get("id"),
                        "recipient_id": status.get("recipient_id"),
                        "errors": status.get("errors"),
                        "business_phone_number_id": value.get("metadata", {}).get(
                            "phone_number_id"
                        ),
                    }
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
                # Respuesta de botón (button_reply) o de lista (list_reply)
                interactive = message.get("interactive", {})
                button_reply = interactive.get("button_reply", {})
                list_reply = interactive.get("list_reply", {})
                result["button_payload"] = button_reply.get("id")
                result["list_payload"] = list_reply.get("id")
                result["text"] = list_reply.get("title", "") or button_reply.get("title", "")

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

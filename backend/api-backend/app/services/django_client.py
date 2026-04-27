"""
Cliente HTTP para comunicarse con Django API
"""
import httpx
from typing import Dict, List, Optional
from app.config import config


class DjangoAPIClient:
    """Cliente para consumir la API REST de Django"""

    def __init__(self):
        self.base_url = config.DJANGO_API_BASE_URL
        self.timeout = config.DJANGO_API_TIMEOUT

    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """
        Realiza una petición HTTP al backend Django

        Args:
            method: GET, POST, PATCH, DELETE
            endpoint: Endpoint relativo (ej: /api/v1/customers)
            **kwargs: Parámetros adicionales (json, params, etc.)

        Returns:
            Response JSON
        """
        url = f"{self.base_url}{endpoint}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()

    # ========== CUSTOMERS ==========

    async def find_or_create_customer(
        self, business_id: str, phone: str, name: Optional[str] = None
    ) -> Dict:
        """
        Busca o crea un cliente

        Args:
            business_id: UUID del negocio
            phone: Teléfono del cliente
            name: Nombre del cliente (requerido si no existe)

        Returns:
            {
                "customer": {...},
                "created": true/false
            }
        """
        return await self._request(
            "POST",
            "/api/v1/customers/find_or_create",
            json={"business_id": business_id, "phone": phone, "name": name},
        )

    async def get_customer(self, customer_id: str) -> Dict:
        """Obtiene información de un cliente"""
        return await self._request("GET", f"/api/v1/customers/{customer_id}")

    async def get_customer_by_phone(self, business_id: str, phone: str) -> Optional[Dict]:
        """Busca un cliente por teléfono"""
        response = await self._request(
            "GET", "/api/v1/customers", params={"business_id": business_id, "phone": phone}
        )
        results = response.get("results", []) if isinstance(response, dict) else response
        return results[0] if results else None

    # ========== BUSINESSES ==========

    async def get_business(self, business_id: str) -> Dict:
        """Obtiene información de un negocio con servicios y horarios"""
        return await self._request("GET", f"/api/v1/businesses/{business_id}")

    async def get_business_services(self, business_id: str) -> List[Dict]:
        """Obtiene servicios activos de un negocio"""
        return await self._request("GET", f"/api/v1/businesses/{business_id}/services")

    async def get_business_schedule(self, business_id: str) -> List[Dict]:
        """Obtiene horarios de un negocio"""
        return await self._request("GET", f"/api/v1/businesses/{business_id}/schedule")

    async def get_businesses_by_owner(self, owner_id: str) -> List[Dict]:
        """Obtiene todos los negocios de un dueño (para multi-negocio)"""
        return await self._request("GET", f"/api/v1/owners/{owner_id}/businesses")

    # ========== APPOINTMENTS ==========

    async def get_availability(
        self, business_id: str, service_id: str, date: str, preferred_time: Optional[str] = None
    ) -> Dict:
        """
        Consulta disponibilidad de slots

        Args:
            business_id: UUID del negocio
            service_id: UUID del servicio
            date: Fecha en formato YYYY-MM-DD
            preferred_time: Hora preferida en formato HH:MM (opcional)

        Returns:
            {
                "date": "2025-12-05",
                "available_slots": [
                    {
                        "start_time": "09:00",
                        "end_time": "09:30",
                        "start_datetime": "2025-12-05T09:00:00-04:00",
                        "end_datetime": "2025-12-05T09:30:00-04:00",
                        "is_preferred": false
                    },
                    ...
                ]
            }
        """
        params = {
            "business_id": business_id,
            "service_id": service_id,
            "date": date,
        }
        if preferred_time:
            params["preferred_time"] = preferred_time

        return await self._request("GET", "/api/v1/appointments/availability", params=params)

    async def create_appointment(self, appointment_data: Dict) -> Dict:
        """
        Crea una cita

        Args:
            appointment_data: {
                "business": "uuid",
                "customer": "uuid",
                "service": "uuid",
                "start_at": "2025-12-05T09:00:00-04:00",
                "end_at": "2025-12-05T09:30:00-04:00",
                "created_via": "whatsapp",
                "notes": "..."
            }

        Returns:
            Appointment creado
        """
        return await self._request("POST", "/api/v1/appointments", json=appointment_data)

    async def get_customer_appointments(
        self, customer_id: str, upcoming: bool = True
    ) -> List[Dict]:
        """Obtiene citas de un cliente"""
        params = {"customer_id": customer_id}
        if upcoming:
            params["upcoming"] = "true"

        response = await self._request("GET", "/api/v1/appointments", params=params)
        return response.get("results", []) if isinstance(response, dict) else response

    async def cancel_appointment(self, appointment_id: str, notes: Optional[str] = None) -> Dict:
        """Cancela una cita"""
        data = {}
        if notes:
            data["notes"] = notes

        return await self._request("POST", f"/api/v1/appointments/{appointment_id}/cancel", json=data)

    async def update_appointment(self, appointment_id: str, update_data: Dict) -> Dict:
        """
        Actualiza una cita (reagendar)

        Args:
            appointment_id: UUID de la cita
            update_data: {
                "start_at": "2025-12-06T10:00:00-04:00",
                "end_at": "2025-12-06T10:30:00-04:00"
            }

        Returns:
            Appointment actualizado
        """
        return await self._request("PATCH", f"/api/v1/appointments/{appointment_id}", json=update_data)

    async def confirm_appointment(self, appointment_id: str) -> Dict:
        """Confirma una cita (usado en recordatorios)"""
        return await self._request("POST", f"/api/v1/appointments/{appointment_id}/confirm")


    # ========== CONVERSATION STATE ==========

    async def get_conversation_state(self, business_id: str, phone_number: str) -> Optional[Dict]:
        """Obtiene el estado de la conversación desde Postgres (vía Django)"""
        try:
            return await self._request("GET", f"/api/v1/conversation-states/{phone_number}/", params={"business_id": business_id})
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def save_conversation_state(self, business_id: str, phone_number: str, context_data: Dict) -> Dict:
        """Guarda o actualiza el estado de la conversación"""
        data = {
            "phone_number": phone_number,
            "business": business_id,
            "context_data": context_data
        }
        try:
            return await self._request("PUT", f"/api/v1/conversation-states/{phone_number}/", json=data)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return await self._request("POST", "/api/v1/conversation-states/", json=data)
            raise

# Singleton instance
django_client = DjangoAPIClient()

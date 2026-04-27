"""
NLU Engine - Motor de procesamiento de lenguaje natural con GPT-4o-mini
"""
import json
from openai import AsyncOpenAI
from typing import Dict, List
from datetime import datetime, timedelta
from app.config import config
from app.services import db_service
from app.prompts.system_prompt import (
    get_classification_prompt,
    get_conversational_reply_prompt,
)
from app.utils.date_parse import resolve_date_from_spanish_text

# Solo estos intents usan segunda llamada LLM (redacción); el resto usa handlers o datos fijos.
CONVERSATIONAL_INTENTS = frozenset(
    {"greeting", "general_question", "clarification_needed"}
)


class NLUEngine:
    """Motor de NLU usando GPT-4o-mini"""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
        self.model = config.OPENAI_MODEL
        self.temperature = config.OPENAI_TEMPERATURE
        self.max_tokens = config.OPENAI_MAX_TOKENS
        self.timeout = config.OPENAI_TIMEOUT

    def _build_chat_messages(
        self, system_prompt: str, context: Dict, message: str
    ) -> List[Dict]:
        messages = [{"role": "system", "content": system_prompt}]
        recent_messages = context.get("recent_messages", [])[-5:]
        for msg in recent_messages:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": message})
        return messages

    async def _classify(
        self, message: str, context: Dict, business_id, customer_context: str
    ) -> Dict:
        business_info = await db_service.get_business(business_id)
        services = await db_service.get_business_services(business_id)
        schedule_rules = await db_service.get_business_schedule(business_id)
        schedule_text = self._format_schedule(schedule_rules)
        system_prompt = get_classification_prompt(
            business_name=business_info.get("name") or "Negocio",
            services=services,
            schedule_info=schedule_text,
            address=business_info.get("address", "") or "",
            description=business_info.get("description", "") or "",
            customer_info=customer_context,
            flow_intent=str(context.get("current_intent") or ""),
            flow_state=str(context.get("state") or ""),
        )
        messages = self._build_chat_messages(system_prompt, context, message)
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=self.temperature,
            max_tokens=min(512, self.max_tokens),
            timeout=self.timeout,
        )
        result = json.loads(response.choices[0].message.content)
        result.pop("response_text", None)
        result.setdefault("entities", {})
        result.setdefault("missing", [])
        result.setdefault("raw_understanding", "")
        result.setdefault("confidence", 0.0)
        result.setdefault("intent", "clarification_needed")
        return self._normalize_dates(result, user_message=message)

    async def _generate_conversational_reply(
        self,
        message: str,
        context: Dict,
        business_name: str,
        customer_context: str,
    ) -> str:
        system_prompt = get_conversational_reply_prompt(
            business_name=business_name,
            customer_info=customer_context,
        )
        messages = self._build_chat_messages(system_prompt, context, message)
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.45,
            max_tokens=min(450, self.max_tokens),
            timeout=self.timeout,
        )
        text = (response.choices[0].message.content or "").strip()
        return text

    async def process(
        self, message: str, context: Dict, business_id, customer_context: str = ""
    ) -> Dict:
        """
        Clasificación sin texto al usuario para intents de acción; segunda llamada solo
        para greeting / general_question / clarification_needed.
        """
        try:
            business_info = await db_service.get_business(business_id)
            bname = business_info.get("name") or "Negocio"
            services = await db_service.get_business_services(business_id)

            if not services:
                from app.services.no_services_nlu import nlu_result_without_openai

                result = nlu_result_without_openai(message)
                intent = result.get("intent") or "clarification_needed"
                result["intent"] = intent
                if intent in CONVERSATIONAL_INTENTS and not result.get("response_text"):
                    result["response_text"] = await self._generate_conversational_reply(
                        message, context, bname, customer_context
                    )
                elif not result.get("response_text"):
                    result["response_text"] = ""
                return result

            result = await self._classify(message, context, business_id, customer_context)
            intent = result.get("intent") or "clarification_needed"
            result["intent"] = intent

            if intent in CONVERSATIONAL_INTENTS and not result.get("response_text"):
                result["response_text"] = await self._generate_conversational_reply(
                    message, context, bname, customer_context
                )
            elif not result.get("response_text"):
                result["response_text"] = ""

            return result

        except Exception as e:
            print(f"Error en NLU Engine: {e}")
            return {
                "intent": "error",
                "confidence": 0.0,
                "entities": {},
                "missing": [],
                "response_text": "Disculpa, tuve un problema procesando tu mensaje. ¿Podrías repetirlo?",
                "raw_understanding": f"Error: {str(e)}",
            }

    def _format_schedule(self, schedule_rules: List[Dict]) -> str:
        """
        Formatea las reglas de horario en texto legible

        Args:
            schedule_rules: Lista de ScheduleRule

        Returns:
            Texto formateado con horarios
        """
        if not schedule_rules:
            return "No hay horarios configurados"

        weekday_names = {
            0: "Lunes",
            1: "Martes",
            2: "Miércoles",
            3: "Jueves",
            4: "Viernes",
            5: "Sábado",
            6: "Domingo",
        }

        lines = []
        for rule in schedule_rules:
            weekday = rule.get("weekday")
            start_time = rule.get("start_time")
            end_time = rule.get("end_time")

            day_name = weekday_names.get(weekday, f"Día {weekday}")
            lines.append(f"  {day_name}: {start_time} - {end_time}")

        return "\n".join(lines)

    def _normalize_dates(self, result: Dict, user_message: str = "") -> Dict:
        """
        Normaliza solo expresiones relativas en entities["date"] (mañana, lunes, etc.).
        Las fechas ISO y la autoridad final sobre YYYY-MM-DD las resuelve el orchestrator en Python.
        """
        entities = result.get("entities", {})
        date_str = entities.get("date", "")

        if not date_str:
            return result

        if len(date_str) == 10 and date_str[4] == "-" and date_str[7] == "-":
            return result

        # Normalizar fechas relativas
        today = datetime.now().date()

        date_mapping = {
            "hoy": today,
            "today": today,
            "mañana": today + timedelta(days=1),
            "tomorrow": today + timedelta(days=1),
            "pasado mañana": today + timedelta(days=2),
        }

        # Días de la semana
        weekday_mapping = {
            "lunes": 0,
            "martes": 1,
            "miércoles": 2,
            "miercoles": 2,
            "jueves": 3,
            "viernes": 4,
            "sábado": 5,
            "sabado": 5,
            "domingo": 6,
        }

        date_lower = date_str.lower()

        # Buscar en mapping directo
        if date_lower in date_mapping:
            normalized_date = date_mapping[date_lower]
            entities["date"] = normalized_date.strftime("%Y-%m-%d")

        # Buscar día de la semana ("próximo viernes", "el jueves")
        for day_name, target_weekday in weekday_mapping.items():
            if day_name in date_lower:
                # Calcular días hasta ese día de la semana
                current_weekday = today.weekday()
                days_ahead = (target_weekday - current_weekday) % 7

                if days_ahead == 0:
                    days_ahead = 7  # Próxima semana

                target_date = today + timedelta(days=days_ahead)
                entities["date"] = target_date.strftime("%Y-%m-%d")
                break

        result["entities"] = entities
        return result

    async def generate_response_with_slots(
        self, business_name: str, slots: List[Dict], service_name: str, date: str
    ) -> str:
        """
        Genera una respuesta natural ofreciendo slots disponibles

        Args:
            business_name: Nombre del negocio
            slots: Lista de slots disponibles
            service_name: Nombre del servicio
            date: Fecha en formato legible

        Returns:
            Mensaje formateado para el usuario
        """
        if not slots:
            return f"Lo siento, no tengo disponibilidad para {service_name} ese día. ¿Te gustaría otro día?"

        # Tomar los 3 primeros slots
        top_slots = slots[:3]

        lines = [f"¡Perfecto! Tengo estos horarios disponibles para {service_name}:"]
        lines.append("")

        for i, slot in enumerate(top_slots, 1):
            start_time = slot.get("start_time")
            marker = " ⭐" if slot.get("is_preferred") else ""
            lines.append(f"  {i}. {start_time}{marker}")

        lines.append("")
        lines.append("¿Cuál prefieres?")

        return "\n".join(lines)


# Singleton instance
nlu_engine = NLUEngine()

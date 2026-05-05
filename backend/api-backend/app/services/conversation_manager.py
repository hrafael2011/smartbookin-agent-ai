"""
Gestión de contexto de conversaciones usando PostgreSQL y SQLAlchemy
"""
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from sqlalchemy import delete
from sqlalchemy.future import select
from app.config import config
from app.core.database import AsyncSessionLocal
from app.models import ConversationState
from app.services import db_service


class ConversationManager:
    """Gestiona el contexto de conversaciones por cliente en base de datos PostgreSQL"""

    def __init__(self):
        self.ttl = config.CONVERSATION_TTL

    def _default_context(self, business_id: int, phone_number: str) -> Dict:
        return {
            "business_id": business_id,
            "customer_id": None,
            "customer_name": None,
            "phone_number": phone_number,
            "recent_messages": [],
            "current_intent": None,
            "pending_data": {},
            "state": "idle",
            "state_stack": [],
            "attempts": {},
            "last_activity": datetime.now(timezone.utc).isoformat(),
        }

    async def _hydrate_customer_from_db(
        self, business_id: int, phone_number: str, context: Dict
    ) -> Dict:
        """
        Completa customer_id / customer_name desde Customer si faltan en el contexto.
        Persiste cuando el contexto ya tenía fila activa (TTL válido) para no reconsultar en cada turno.
        """
        if context.get("customer_id"):
            return context
        cust = await db_service.get_customer_by_channel(business_id, phone_number)
        if not cust or not cust.get("id"):
            return context
        context = dict(context)
        context["customer_id"] = cust["id"]
        nm = cust.get("name")
        if nm and str(nm).strip():
            context["customer_name"] = str(nm).strip()
        return context

    async def get_context(self, business_id: int, phone_number: str) -> Dict:
        """
        Obtiene el contexto de conversación desde PostgreSQL usando SQLAlchemy
        """
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(ConversationState).filter(
                    ConversationState.business_id == business_id,
                    ConversationState.phone_number == phone_number
                )
            )
            state_record = result.scalars().first()
            state_data_response = state_record.context_data if state_record else None

        if state_data_response:
            context = state_data_response
            if not context:
                return await self._hydrate_customer_from_db(
                    business_id, phone_number, self._default_context(business_id, phone_number)
                )

            last_activity_str = context.get("last_activity")
            if last_activity_str:
                last_activity = datetime.fromisoformat(
                    last_activity_str.replace("Z", "+00:00")
                )
                if last_activity.tzinfo is None:
                    last_activity = last_activity.replace(tzinfo=timezone.utc)
                if (datetime.now(timezone.utc) - last_activity).total_seconds() < self.ttl:
                    if not context.get("customer_id"):
                        merged = await self._hydrate_customer_from_db(
                            business_id, phone_number, context
                        )
                        if merged.get("customer_id"):
                            await self.save_context(
                                business_id, phone_number, merged
                            )
                        return merged
                    return context

        base = self._default_context(business_id, phone_number)
        return await self._hydrate_customer_from_db(business_id, phone_number, base)

    async def save_context(self, business_id: int, phone_number: str, context: Dict):
        """Guarda el contexto completo llamando a SQLAlchemy"""
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(ConversationState).filter(
                    ConversationState.business_id == business_id,
                    ConversationState.phone_number == phone_number
                )
            )
            state_record = result.scalars().first()

            if state_record:
                state_record.context_data = context
            else:
                new_state = ConversationState(
                    business_id=business_id,
                    phone_number=phone_number,
                    context_data=context
                )
                db.add(new_state)
            
            await db.commit()

    async def save_message(
        self,
        business_id: int,
        phone_number: str,
        role: str,
        content: str,
        update_data: Optional[Dict] = None,
    ):
        """
        Guarda un mensaje en el historial de conversación
        """
        context = await self.get_context(business_id, phone_number)

        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        context["recent_messages"].append(message)

        # Mantener solo los últimos N mensajes
        context["recent_messages"] = context["recent_messages"][
            -config.MAX_CONTEXT_MESSAGES :
        ]

        context["last_activity"] = datetime.now(timezone.utc).isoformat()

        if update_data:
            context.update(update_data)

        await self.save_context(business_id, phone_number, context)

    async def update_context(
        self, business_id: int, phone_number: str, update_data: Dict
    ):
        """
        Actualiza datos del contexto sin agregar mensaje.
        Auto-pushes previous state onto state_stack on transitions (unless caller
        explicitly includes state_stack in update_data).
        """
        context = await self.get_context(business_id, phone_number)

        new_state = update_data.get("state")
        current_state = context.get("state") or "idle"
        if new_state and new_state != current_state and "state_stack" not in update_data:
            if new_state == "idle":
                context["state_stack"] = []
            elif current_state != "idle":
                stack = list(context.get("state_stack") or [])
                stack.append(current_state)
                if len(stack) > 10:
                    stack = stack[-10:]
                context["state_stack"] = stack

        context.update(update_data)
        context["last_activity"] = datetime.now(timezone.utc).isoformat()

        await self.save_context(business_id, phone_number, context)

    async def push_state(self, business_id: int, phone_number: str, state: str) -> None:
        """Push a state string onto state_stack (max 10 elements, oldest dropped)."""
        context = await self.get_context(business_id, phone_number)
        stack = list(context.get("state_stack") or [])
        stack.append(state)
        if len(stack) > 10:
            stack = stack[-10:]
        context["state_stack"] = stack
        context["last_activity"] = datetime.now(timezone.utc).isoformat()
        await self.save_context(business_id, phone_number, context)

    async def clear_pending_data(self, business_id: int, phone_number: str):
        """
        Limpia pending_data y resetea el intent
        """
        await self.update_context(
            business_id,
            phone_number,
            {
                "current_intent": None,
                "pending_data": {},
                "state": "idle",
            },
        )

    async def set_customer_info(
        self, business_id: int, phone_number: str, customer_id: int, customer_name: str
    ):
        """
        Guarda información del cliente en el contexto
        """
        await self.update_context(
            business_id,
            phone_number,
            {
                "customer_id": customer_id,
                "customer_name": customer_name,
            },
        )

    async def get_recent_messages_for_gpt(
        self, business_id: int, phone_number: str, limit: int = 5
    ) -> List[Dict]:
        """
        Obtiene mensajes recientes en formato para GPT
        """
        context = await self.get_context(business_id, phone_number)
        recent = context.get("recent_messages", [])[-limit:]

        return [{"role": msg["role"], "content": msg["content"]} for msg in recent]

    async def delete_context(self, business_id: int, phone_number: str):
        """Elimina la fila de estado para este negocio y canal (evita filas con JSON vacío)."""
        async with AsyncSessionLocal() as db:
            await db.execute(
                delete(ConversationState).where(
                    ConversationState.business_id == business_id,
                    ConversationState.phone_number == phone_number,
                )
            )
            await db.commit()

    async def delete_all_contexts_for_phone_number(self, phone_number: str) -> None:
        """Borra todas las filas de contexto para este identificador (ej. tg:chat_id) en cualquier negocio."""
        async with AsyncSessionLocal() as db:
            await db.execute(
                delete(ConversationState).where(ConversationState.phone_number == phone_number)
            )
            await db.commit()


# Singleton instance
conversation_manager = ConversationManager()

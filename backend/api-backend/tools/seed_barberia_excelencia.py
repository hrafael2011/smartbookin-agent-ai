"""
Crea dueño + negocio Barbería La Excelencia (servicios, horario, token Telegram).
Uso (desde api-backend/):
  DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5435/smartbooking python tools/seed_barberia_excelencia.py
"""
import asyncio
import os
import sys
from datetime import time

from sqlalchemy import delete
from sqlalchemy.future import select

sys.path.insert(0, ".")

from app.core.database import AsyncSessionLocal
from app.core.security import get_password_hash
from app.models import Business, Owner, ScheduleRule, Service
from app.services.telegram_link_service import generate_invite_token


OWNER_EMAIL = "barberia.excelencia.demo@local.test"
OWNER_PASSWORD = "ExcelenciaDemo2026!"
OWNER_NAME = "Dueño Barbería La Excelencia"

BUSINESS_NAME = "Barbería La Excelencia"
BUSINESS_PHONE = "+18295553005"
ADDRESS = "30 de Junio, Plaza Iberoamérica, local 305"

# day_of_week: mismo criterio que get_availability (_schedule_day_from_date): 0=dom … 6=sáb. Cerrado martes (2).
OPEN_DAYS = (0, 1, 3, 4, 5, 6)
DAY_START = time(9, 0)
DAY_END = time(21, 0)

SERVICES = [
    ("Corte", 600.0, 30),
    ("Cerquillos", 400.0, 20),
    ("Cejas", 100.0, 15),
    ("Afeitada", 200.0, 20),
]


async def main() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Owner).filter(Owner.email == OWNER_EMAIL))
        owner = result.scalars().first()
        if not owner:
            owner = Owner(
                name=OWNER_NAME,
                email=OWNER_EMAIL,
                phone="+18095553001",
                hashed_password=get_password_hash(OWNER_PASSWORD),
                email_verified=True,
            )
            db.add(owner)
            await db.commit()
            await db.refresh(owner)
            print(f"Dueño creado id={owner.id}")
        else:
            owner.hashed_password = get_password_hash(OWNER_PASSWORD)
            owner.email_verified = True
            owner.name = OWNER_NAME
            await db.commit()
            print(f"Dueño actualizado id={owner.id}")

        result = await db.execute(
            select(Business).filter(
                Business.owner_id == owner.id, Business.name == BUSINESS_NAME
            )
        )
        business = result.scalars().first()
        if not business:
            business = Business(
                name=BUSINESS_NAME,
                phone_number=BUSINESS_PHONE,
                address=ADDRESS,
                description="Barbería — cortes, cerquillos, cejas y afeitada.",
                category="barbershop",
                owner_id=owner.id,
                telegram_invite_token=generate_invite_token(),
            )
            db.add(business)
            await db.commit()
            await db.refresh(business)
            print(f"Negocio creado id={business.id}")
        else:
            business.address = ADDRESS
            business.phone_number = BUSINESS_PHONE
            business.description = "Barbería — cortes, cerquillos, cejas y afeitada."
            if not business.telegram_invite_token:
                business.telegram_invite_token = generate_invite_token()
            await db.commit()
            print(f"Negocio existente id={business.id}")

        await db.execute(delete(Service).where(Service.business_id == business.id))
        await db.execute(delete(ScheduleRule).where(ScheduleRule.business_id == business.id))
        await db.commit()

        for name, price, duration in SERVICES:
            db.add(
                Service(
                    name=name,
                    price=price,
                    duration_minutes=duration,
                    business_id=business.id,
                    is_active=True,
                )
            )
        for d in OPEN_DAYS:
            db.add(
                ScheduleRule(
                    business_id=business.id,
                    day_of_week=d,
                    start_time=DAY_START,
                    end_time=DAY_END,
                    is_available=True,
                )
            )
        await db.commit()

        await db.refresh(business)
        token = business.telegram_invite_token
        print(f"\n--- Credenciales panel ---\nEmail: {OWNER_EMAIL}\nPassword: {OWNER_PASSWORD}\n")
        print(f"Business ID: {business.id}")
        print(f"Invite token: {token}")
        bot = (os.getenv("TELEGRAM_BOT_USERNAME") or "appointmentsv1_bot").lstrip("@")
        print("\n--- Enlace Telegram (deep link) ---")
        print(f"https://t.me/{bot}?start={token}")


if __name__ == "__main__":
    asyncio.run(main())

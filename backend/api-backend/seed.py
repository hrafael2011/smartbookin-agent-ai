import asyncio
from sqlalchemy.future import select
from app.core.database import AsyncSessionLocal
from app.models import Owner, Business, Service
from passlib.hash import bcrypt

async def seed():
    async with AsyncSessionLocal() as db:
        # Check if owner exists
        result = await db.execute(select(Owner).filter(Owner.email == "test@example.com"))
        owner = result.scalars().first()
        
        if not owner:
            owner = Owner(
                name="Test Owner",
                email="test@example.com",
                hashed_password="$2b$12$I10SrJQnXDB2GpotkG6kc.l7rvfA0LJ32z2/7CjVbJPLlvlLBFcg."
            )
            db.add(owner)
            await db.commit()
            await db.refresh(owner)
            print(f"Created owner: {owner.id}")
        else:
            # Update password for testing
            owner.hashed_password = "$2b$12$I10SrJQnXDB2GpotkG6kc.l7rvfA0LJ32z2/7CjVbJPLlvlLBFcg."
            await db.commit()
            print(f"Updated owner password: {owner.id}")
        
        # Check if business exists
        result = await db.execute(select(Business).filter(Business.owner_id == owner.id))
        business = result.scalars().first()
        
        if not business:
            business = Business(
                name="Barbería Royale",
                phone_number="+18095551234",
                whatsapp_phone_number_id="WBID_TEST_001",
                address="Av. Churchill 123",
                owner_id=owner.id
            )
            db.add(business)
            await db.commit()
            await db.refresh(business)
            print(f"Created business: {business.id}")
            
        # Check if service exists
        result = await db.execute(select(Service).filter(Service.business_id == business.id))
        service = result.scalars().first()
        
        if not service:
            service = Service(
                name="Corte de Cabello",
                duration_minutes=30,
                price=500.0,
                business_id=business.id
            )
            db.add(service)
            await db.commit()
            print(f"Created service: {service.id}")
        
        print(f"Seed complete. Business ID: {business.id}")

if __name__ == "__main__":
    asyncio.run(seed())

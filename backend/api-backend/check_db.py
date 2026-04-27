import asyncio
from sqlalchemy.future import select
from app.core.database import AsyncSessionLocal
from app.models import Business, Customer, ConversationState

async def check():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Business))
        businesses = result.scalars().all()
        print(f"Businesses: {len(businesses)}")
        for b in businesses:
            print(f"  - {b.id}: {b.name}")
            
        result = await db.execute(select(Customer))
        customers = result.scalars().all()
        print(f"Customers: {len(customers)}")
        
        result = await db.execute(select(ConversationState))
        states = result.scalars().all()
        print(f"States: {len(states)}")

if __name__ == "__main__":
    asyncio.run(check())

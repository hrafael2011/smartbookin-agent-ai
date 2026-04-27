from typing import List
from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_db
from app.core.dependencies import get_current_owner
from app.models import Customer, Business, Owner
from app.schemas import CustomerCreate, CustomerOut

router = APIRouter()

@router.post("/{business_id}/customers", response_model=CustomerOut, status_code=status.HTTP_201_CREATED)
async def create_customer(business_id: int, customer_in: CustomerCreate, db: AsyncSession = Depends(get_db)):
    # Customers can be created publicly or by the business, no owner auth required for creation
    new_customer = Customer(**customer_in.model_dump(), business_id=business_id)
    db.add(new_customer)
    await db.commit()
    await db.refresh(new_customer)
    return new_customer

@router.get("/{business_id}/customers", response_model=List[CustomerOut])
async def get_customers(business_id: int, db: AsyncSession = Depends(get_db), current_owner: Owner = Depends(get_current_owner)):
    # Verify business belongs to owner
    result = await db.execute(select(Business).filter(Business.id == business_id, Business.owner_id == current_owner.id))
    if not result.scalars().first():
        raise HTTPException(status_code=404, detail="Business not found or unauthorized")
        
    result = await db.execute(select(Customer).filter(Customer.business_id == business_id))
    return result.scalars().all()


@router.get("/{business_id}/customers/{customer_id}", response_model=CustomerOut)
async def get_customer(
    business_id: int,
    customer_id: int,
    db: AsyncSession = Depends(get_db),
    current_owner: Owner = Depends(get_current_owner),
):
    result = await db.execute(
        select(Business).filter(Business.id == business_id, Business.owner_id == current_owner.id)
    )
    if not result.scalars().first():
        raise HTTPException(status_code=404, detail="Business not found or unauthorized")

    result = await db.execute(
        select(Customer).filter(Customer.id == customer_id, Customer.business_id == business_id)
    )
    customer = result.scalars().first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.patch("/{business_id}/customers/{customer_id}", response_model=CustomerOut)
async def update_customer(
    business_id: int,
    customer_id: int,
    customer_in: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    current_owner: Owner = Depends(get_current_owner),
):
    result = await db.execute(
        select(Business).filter(Business.id == business_id, Business.owner_id == current_owner.id)
    )
    if not result.scalars().first():
        raise HTTPException(status_code=404, detail="Business not found or unauthorized")

    result = await db.execute(
        select(Customer).filter(Customer.id == customer_id, Customer.business_id == business_id)
    )
    customer = result.scalars().first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Keep unknown UI fields ignored (email/notes/is_active) for backward compatibility.
    if "name" in customer_in:
        customer.name = customer_in["name"]
    if "phone_number" in customer_in:
        customer.phone_number = customer_in["phone_number"]
    if "phone" in customer_in:
        customer.phone_number = customer_in["phone"]

    await db.commit()
    await db.refresh(customer)
    return customer


@router.delete("/{business_id}/customers/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_customer(
    business_id: int,
    customer_id: int,
    db: AsyncSession = Depends(get_db),
    current_owner: Owner = Depends(get_current_owner),
):
    result = await db.execute(
        select(Business).filter(Business.id == business_id, Business.owner_id == current_owner.id)
    )
    if not result.scalars().first():
        raise HTTPException(status_code=404, detail="Business not found or unauthorized")

    result = await db.execute(
        select(Customer).filter(Customer.id == customer_id, Customer.business_id == business_id)
    )
    customer = result.scalars().first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    await db.delete(customer)
    await db.commit()
    return None

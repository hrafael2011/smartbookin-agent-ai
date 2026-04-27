from datetime import date, datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_db
from app.core.dependencies import get_current_owner
from app.models import (
    Business,
    Owner,
    ScheduleException,
    ScheduleRule,
    TimeBlock,
)
from app.schemas import (
    ScheduleExceptionCreate,
    ScheduleExceptionOut,
    ScheduleExceptionRestore,
    ScheduleExceptionUpdate,
    ScheduleRuleCreate,
    ScheduleRuleOut,
    TimeBlockCreate,
    TimeBlockOut,
)
from app.services.schedule_logic import ranges_overlap, validate_exception_fields

router = APIRouter()


async def _get_owned_business(
    business_id: int, db: AsyncSession, current_owner: Owner
) -> Business:
    result = await db.execute(
        select(Business).filter(
            Business.id == business_id, Business.owner_id == current_owner.id
        )
    )
    business = result.scalars().first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found or access denied")
    return business


async def _assert_no_exception_overlap(
    *,
    db: AsyncSession,
    business_id: int,
    exception_date: date,
    all_day: bool,
    start_time,
    end_time,
    exclude_exception_id: Optional[int] = None,
) -> None:
    query = select(ScheduleException).filter(
        ScheduleException.business_id == business_id,
        ScheduleException.date == exception_date,
        ScheduleException.deleted_at.is_(None),
    )
    if exclude_exception_id is not None:
        query = query.filter(ScheduleException.id != exclude_exception_id)

    result = await db.execute(query)
    existing = result.scalars().all()
    if not existing:
        return

    if all_day:
        raise HTTPException(
            status_code=409,
            detail="Exception overlaps with another active exception on this date",
        )

    for item in existing:
        if item.all_day:
            raise HTTPException(
                status_code=409,
                detail="Exception overlaps with another active exception on this date",
            )

        if ranges_overlap(start_time, end_time, item.start_time, item.end_time):
            raise HTTPException(
                status_code=409,
                detail="Exception overlaps with another active exception on this date",
            )


def _validate_exception_or_422(
    exception_type: str, all_day: bool, start_time, end_time
) -> None:
    validation_error = validate_exception_fields(
        exception_type=exception_type,
        all_day=all_day,
        start_time=start_time,
        end_time=end_time,
    )
    if validation_error:
        raise HTTPException(status_code=422, detail=validation_error)


# --- Schedule Rules ---


@router.get("/schedule-rules/", response_model=List[ScheduleRuleOut])
async def get_schedule_rules(
    business_id: int,
    db: AsyncSession = Depends(get_db),
    current_owner: Owner = Depends(get_current_owner),
):
    await _get_owned_business(business_id, db, current_owner)

    result = await db.execute(
        select(ScheduleRule)
        .filter(ScheduleRule.business_id == business_id)
        .order_by(ScheduleRule.day_of_week.asc(), ScheduleRule.id.asc())
    )
    return result.scalars().all()


@router.post("/schedule-rules/", response_model=ScheduleRuleOut, status_code=status.HTTP_201_CREATED)
async def create_schedule_rule(
    business_id: int,
    rule_in: ScheduleRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_owner: Owner = Depends(get_current_owner),
):
    await _get_owned_business(business_id, db, current_owner)

    result = await db.execute(
        select(ScheduleRule)
        .filter(
            ScheduleRule.business_id == business_id,
            ScheduleRule.day_of_week == rule_in.day_of_week,
        )
        .order_by(ScheduleRule.id.asc())
    )
    existing_rules = result.scalars().all()

    if existing_rules:
        rule = existing_rules[0]
        rule.start_time = rule_in.start_time
        rule.end_time = rule_in.end_time
        rule.is_available = rule_in.is_available

        # Defensive cleanup for old duplicated records by day.
        for duplicate in existing_rules[1:]:
            await db.delete(duplicate)
    else:
        rule = ScheduleRule(**rule_in.model_dump(), business_id=business_id)
        db.add(rule)

    await db.commit()
    await db.refresh(rule)
    return rule


@router.delete("/schedule-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    current_owner: Owner = Depends(get_current_owner),
):
    result = await db.execute(select(ScheduleRule).filter(ScheduleRule.id == rule_id))
    rule = result.scalars().first()
    if not rule:
        raise HTTPException(status_code=404, detail="Schedule rule not found")

    await _get_owned_business(rule.business_id, db, current_owner)

    await db.delete(rule)
    await db.commit()
    return None


# --- Time Blocks ---


@router.get("/time-blocks/", response_model=List[TimeBlockOut])
async def get_time_blocks(
    business_id: int,
    db: AsyncSession = Depends(get_db),
    current_owner: Owner = Depends(get_current_owner),
):
    await _get_owned_business(business_id, db, current_owner)

    result = await db.execute(
        select(TimeBlock)
        .filter(TimeBlock.business_id == business_id)
        .order_by(TimeBlock.start_at.asc())
    )
    return result.scalars().all()


@router.post("/time-blocks/", response_model=TimeBlockOut, status_code=status.HTTP_201_CREATED)
async def create_time_block(
    business_id: int,
    block_in: TimeBlockCreate,
    db: AsyncSession = Depends(get_db),
    current_owner: Owner = Depends(get_current_owner),
):
    await _get_owned_business(business_id, db, current_owner)

    new_block = TimeBlock(**block_in.model_dump(), business_id=business_id)
    db.add(new_block)
    await db.commit()
    await db.refresh(new_block)
    return new_block


@router.delete("/time-blocks/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_time_block(
    block_id: int,
    db: AsyncSession = Depends(get_db),
    current_owner: Owner = Depends(get_current_owner),
):
    result = await db.execute(select(TimeBlock).filter(TimeBlock.id == block_id))
    block = result.scalars().first()
    if not block:
        raise HTTPException(status_code=404, detail="Time block not found")

    await _get_owned_business(block.business_id, db, current_owner)

    await db.delete(block)
    await db.commit()
    return None


# --- Schedule Exceptions ---


@router.get("/schedule-exceptions/", response_model=List[ScheduleExceptionOut])
async def get_schedule_exceptions(
    business_id: int,
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    include_deleted: bool = False,
    db: AsyncSession = Depends(get_db),
    current_owner: Owner = Depends(get_current_owner),
):
    await _get_owned_business(business_id, db, current_owner)

    query = select(ScheduleException).filter(ScheduleException.business_id == business_id)
    if from_date:
        query = query.filter(ScheduleException.date >= from_date)
    if to_date:
        query = query.filter(ScheduleException.date <= to_date)
    if not include_deleted:
        query = query.filter(ScheduleException.deleted_at.is_(None))

    result = await db.execute(
        query.order_by(
            ScheduleException.date.asc(),
            ScheduleException.all_day.desc(),
            ScheduleException.start_time.asc(),
            ScheduleException.id.asc(),
        )
    )
    return result.scalars().all()


@router.post(
    "/schedule-exceptions/",
    response_model=ScheduleExceptionOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_schedule_exception(
    business_id: int,
    exception_in: ScheduleExceptionCreate,
    db: AsyncSession = Depends(get_db),
    current_owner: Owner = Depends(get_current_owner),
):
    await _get_owned_business(business_id, db, current_owner)

    _validate_exception_or_422(
        exception_in.type, exception_in.all_day, exception_in.start_time, exception_in.end_time
    )

    await _assert_no_exception_overlap(
        db=db,
        business_id=business_id,
        exception_date=exception_in.date,
        all_day=exception_in.all_day,
        start_time=exception_in.start_time,
        end_time=exception_in.end_time,
    )

    new_exception = ScheduleException(
        **exception_in.model_dump(),
        business_id=business_id,
    )
    db.add(new_exception)
    await db.commit()
    await db.refresh(new_exception)
    return new_exception


@router.patch("/schedule-exceptions/{exception_id}", response_model=ScheduleExceptionOut)
async def update_schedule_exception(
    exception_id: int,
    exception_in: ScheduleExceptionUpdate,
    db: AsyncSession = Depends(get_db),
    current_owner: Owner = Depends(get_current_owner),
):
    result = await db.execute(
        select(ScheduleException).filter(ScheduleException.id == exception_id)
    )
    schedule_exception = result.scalars().first()
    if not schedule_exception:
        raise HTTPException(status_code=404, detail="Schedule exception not found")

    await _get_owned_business(schedule_exception.business_id, db, current_owner)

    if schedule_exception.deleted_at is not None:
        raise HTTPException(
            status_code=400,
            detail="Cannot update an archived schedule exception. Restore it first.",
        )

    update_payload = exception_in.model_dump(exclude_unset=True)
    updated_type = update_payload.get("type", schedule_exception.type)
    updated_all_day = update_payload.get("all_day", schedule_exception.all_day)
    updated_start_time = update_payload.get("start_time", schedule_exception.start_time)
    updated_end_time = update_payload.get("end_time", schedule_exception.end_time)
    updated_date = update_payload.get("date", schedule_exception.date)

    _validate_exception_or_422(
        updated_type, updated_all_day, updated_start_time, updated_end_time
    )

    await _assert_no_exception_overlap(
        db=db,
        business_id=schedule_exception.business_id,
        exception_date=updated_date,
        all_day=updated_all_day,
        start_time=updated_start_time,
        end_time=updated_end_time,
        exclude_exception_id=schedule_exception.id,
    )

    for key, value in update_payload.items():
        setattr(schedule_exception, key, value)
    schedule_exception.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(schedule_exception)
    return schedule_exception


@router.delete("/schedule-exceptions/{exception_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_schedule_exception(
    exception_id: int,
    db: AsyncSession = Depends(get_db),
    current_owner: Owner = Depends(get_current_owner),
):
    result = await db.execute(
        select(ScheduleException).filter(ScheduleException.id == exception_id)
    )
    schedule_exception = result.scalars().first()
    if not schedule_exception:
        raise HTTPException(status_code=404, detail="Schedule exception not found")

    await _get_owned_business(schedule_exception.business_id, db, current_owner)

    if schedule_exception.deleted_at is None:
        schedule_exception.deleted_at = datetime.now(timezone.utc)
        schedule_exception.deleted_by = current_owner.id
        schedule_exception.updated_at = datetime.now(timezone.utc)
        await db.commit()

    return None


@router.post("/schedule-exceptions/{exception_id}/restore", response_model=ScheduleExceptionOut)
async def restore_schedule_exception(
    exception_id: int,
    _payload: Optional[ScheduleExceptionRestore] = None,
    db: AsyncSession = Depends(get_db),
    current_owner: Owner = Depends(get_current_owner),
):
    result = await db.execute(
        select(ScheduleException).filter(ScheduleException.id == exception_id)
    )
    schedule_exception = result.scalars().first()
    if not schedule_exception:
        raise HTTPException(status_code=404, detail="Schedule exception not found")

    await _get_owned_business(schedule_exception.business_id, db, current_owner)

    if schedule_exception.deleted_at is not None:
        await _assert_no_exception_overlap(
            db=db,
            business_id=schedule_exception.business_id,
            exception_date=schedule_exception.date,
            all_day=schedule_exception.all_day,
            start_time=schedule_exception.start_time,
            end_time=schedule_exception.end_time,
            exclude_exception_id=schedule_exception.id,
        )
        schedule_exception.deleted_at = None
        schedule_exception.deleted_by = None
        schedule_exception.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(schedule_exception)

    return schedule_exception

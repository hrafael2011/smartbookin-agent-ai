import pytest
from fastapi import HTTPException

from app.api.businesses import create_business
from app.schemas import BusinessCreate


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def first(self):
        return self.value


class _ExecuteResult:
    def __init__(self, value):
        self.value = value

    def scalars(self):
        return _ScalarResult(self.value)


class _FakeOwner:
    id = 7


class _FakeDb:
    def __init__(self, existing_business_id=None):
        self.existing_business_id = existing_business_id
        self.added = None
        self.committed = False
        self.refreshed = False

    async def execute(self, *_args, **_kwargs):
        return _ExecuteResult(self.existing_business_id)

    def add(self, item):
        self.added = item

    async def commit(self):
        self.committed = True

    async def refresh(self, item):
        self.refreshed = True
        item.id = 99


def _business_payload():
    return BusinessCreate(
        name="Barberia Demo",
        phone_number="8095551111",
        category="barbershop",
        address="Calle 1",
    )


@pytest.mark.asyncio
async def test_create_business_allowed_when_owner_has_no_business():
    db = _FakeDb(existing_business_id=None)

    created = await create_business(_business_payload(), db=db, current_owner=_FakeOwner())

    assert created.owner_id == _FakeOwner.id
    assert db.added is created
    assert db.committed is True
    assert db.refreshed is True


@pytest.mark.asyncio
async def test_create_business_blocks_second_business_for_mvp():
    db = _FakeDb(existing_business_id=1)

    with pytest.raises(HTTPException) as exc:
        await create_business(_business_payload(), db=db, current_owner=_FakeOwner())

    assert exc.value.status_code == 409
    assert "un negocio por dueño" in exc.value.detail
    assert db.added is None
    assert db.committed is False

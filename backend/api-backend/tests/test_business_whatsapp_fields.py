"""
Registro del tenant WhatsApp: Business acepta/exponen whatsapp_phone_number_id,
waba_id y config_json vía PATCH/GET; duplicados → 409; ids vacíos → None.
"""
from datetime import datetime

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.api.businesses import create_business, get_business, update_business
from app.schemas import BusinessCreate, BusinessOut, BusinessUpdate


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


class _FakeBusiness:
    """Business mínimo: acepta setattr y sirve para serializar BusinessOut."""

    def __init__(self, **kwargs):
        self.id = 1
        self.owner_id = _FakeOwner.id
        self.created_at = datetime(2026, 1, 1)
        for key, value in kwargs.items():
            setattr(self, key, value)


class _FakeDb:
    """business=None → el owner no tiene negocio (create pasa); pasar uno para update/get."""

    def __init__(self, business=None, commit_error=None):
        self.business = business
        self.commit_error = commit_error
        self.committed = False
        self.added = None

    async def execute(self, *_args, **_kwargs):
        return _ExecuteResult(self.business)

    def add(self, item):
        self.added = item

    async def commit(self):
        if self.commit_error:
            raise self.commit_error
        self.committed = True

    async def refresh(self, item):
        return item

    async def rollback(self):
        self.rolled_back = True


@pytest.mark.asyncio
async def test_update_business_accepts_whatsapp_fields():
    db = _FakeDb(business=_FakeBusiness())

    updated = await update_business(
        1,
        BusinessUpdate(
            whatsapp_phone_number_id="WBID_001",
            waba_id="WABA_001",
            config_json={"wa_template": "appointment_reminder"},
        ),
        db=db,
        current_owner=_FakeOwner(),
    )

    assert updated.whatsapp_phone_number_id == "WBID_001"
    assert updated.waba_id == "WABA_001"
    assert updated.config_json == {"wa_template": "appointment_reminder"}
    assert db.committed is True


@pytest.mark.asyncio
async def test_create_business_persists_whatsapp_fields():
    db = _FakeDb(business=None)

    created = await create_business(
        BusinessCreate(
            name="Demo",
            phone_number="8095551111",
            whatsapp_phone_number_id="WBID_002",
            waba_id="WABA_002",
        ),
        db=db,
        current_owner=_FakeOwner(),
    )

    assert db.added.whatsapp_phone_number_id == "WBID_002"
    assert db.added.waba_id == "WABA_002"


@pytest.mark.asyncio
async def test_update_business_cleans_blank_wa_ids_to_none():
    db = _FakeDb(business=_FakeBusiness())

    updated = await update_business(
        1,
        BusinessUpdate(whatsapp_phone_number_id="   ", waba_id=""),
        db=db,
        current_owner=_FakeOwner(),
    )

    assert updated.whatsapp_phone_number_id is None
    assert updated.waba_id is None


@pytest.mark.asyncio
async def test_update_business_rejects_wa_id_over_64_chars():
    with pytest.raises(ValidationError):
        BusinessUpdate(whatsapp_phone_number_id="W" * 65)


@pytest.mark.asyncio
async def test_update_business_duplicate_wa_id_returns_409():
    db = _FakeDb(
        business=_FakeBusiness(),
        commit_error=IntegrityError("stmt", {}, Exception("dup")),
    )

    with pytest.raises(HTTPException) as exc:
        await update_business(
            1,
            BusinessUpdate(whatsapp_phone_number_id="WBID_DUP"),
            db=db,
            current_owner=_FakeOwner(),
        )

    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_get_business_exposes_whatsapp_fields():
    db = _FakeDb(
        business=_FakeBusiness(
            whatsapp_phone_number_id="WBID_001",
            waba_id="WABA_001",
            config_json={"wa_template": "appointment_reminder"},
        )
    )

    result = await get_business(1, db=db, current_owner=_FakeOwner())

    assert result.whatsapp_phone_number_id == "WBID_001"
    assert result.waba_id == "WABA_001"
    assert result.config_json == {"wa_template": "appointment_reminder"}


def test_business_out_serializes_whatsapp_fields():
    out = BusinessOut.model_validate(
        _FakeBusiness(
            name="Demo",
            phone_number="8095551111",
            whatsapp_phone_number_id="WBID_001",
            waba_id="WABA_001",
            config_json={"wa_template": "appointment_reminder"},
        )
    )

    assert out.whatsapp_phone_number_id == "WBID_001"
    assert out.waba_id == "WABA_001"
    assert out.config_json == {"wa_template": "appointment_reminder"}

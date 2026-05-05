import pytest

from app.api.services import _validate_service_timing
from app.models import Service
from app.schemas import ServiceCreate


def test_service_model_has_buffer_minutes_field():
    assert hasattr(Service, "buffer_minutes")
    assert Service.__table__.c.buffer_minutes.default.arg == 0


def test_buffer_minutes_default_is_zero():
    service = Service(name="Corte", duration_minutes=30, price=500)
    assert service.buffer_minutes is None
    payload = ServiceCreate(name="Corte", duration_minutes=30, price=500)
    assert payload.buffer_minutes == 0


def test_update_service_buffer_minutes_valid():
    _validate_service_timing(
        {"buffer_minutes": 15},
        current_duration=30,
        current_buffer=0,
    )


def test_update_service_buffer_minutes_negative_rejected():
    with pytest.raises(Exception) as exc:
        _validate_service_timing(
            {"buffer_minutes": -1},
            current_duration=30,
            current_buffer=0,
        )
    assert getattr(exc.value, "status_code", None) == 400


def test_update_service_buffer_minutes_exceeds_max_rejected():
    with pytest.raises(Exception) as exc:
        _validate_service_timing(
            {"buffer_minutes": 121},
            current_duration=30,
            current_buffer=0,
        )
    assert getattr(exc.value, "status_code", None) == 400


def test_update_service_duration_plus_buffer_exceeds_480_rejected():
    with pytest.raises(Exception) as exc:
        _validate_service_timing(
            {"duration_minutes": 400},
            current_duration=30,
            current_buffer=100,
        )
    assert getattr(exc.value, "status_code", None) == 400

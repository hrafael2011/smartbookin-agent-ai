"""API routers package."""

from . import appointments, auth, businesses, customers, dashboard, owners, schedules, services

__all__ = [
    "auth",
    "owners",
    "businesses",
    "services",
    "customers",
    "appointments",
    "schedules",
    "dashboard",
]

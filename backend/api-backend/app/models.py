from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text, JSON, Time, Float, Date
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.core.database import Base

class Owner(Base):
    __tablename__ = "owners"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    phone = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)
    email_verified = Column(Boolean, default=False, nullable=False)
    verification_token = Column(String, nullable=True)
    verification_token_expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    businesses = relationship("Business", back_populates="owner", cascade="all, delete")
    refresh_tokens = relationship(
        "RefreshToken", back_populates="owner", cascade="all, delete-orphan"
    )
    deleted_schedule_exceptions = relationship(
        "ScheduleException",
        back_populates="deleted_by_owner",
        foreign_keys="ScheduleException.deleted_by",
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    owner = relationship("Owner", back_populates="refresh_tokens")


class Business(Base):
    __tablename__ = "businesses"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone_number = Column(String, unique=True, nullable=False)  # Business Contact Number
    whatsapp_phone_number_id = Column(String, unique=True, nullable=True)  # Meta Phone Number ID
    category = Column(String, nullable=True, default="barbershop") # barbershop, medical, spa, etc.
    description = Column(Text, nullable=True)
    address = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True)
    daily_notification_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    telegram_invite_token = Column(String, unique=True, nullable=True, index=True)
    telegram_first_contact_at = Column(DateTime(timezone=True), nullable=True)

    owner_id = Column(Integer, ForeignKey("owners.id"))
    owner = relationship("Owner", back_populates="businesses")

    services = relationship("Service", back_populates="business", cascade="all, delete")
    customers = relationship("Customer", back_populates="business", cascade="all, delete")
    appointments = relationship("Appointment", back_populates="business", cascade="all, delete")
    waitlist_entries = relationship("WaitlistEntry", back_populates="business", cascade="all, delete")
    conversation_states = relationship("ConversationState", back_populates="business", cascade="all, delete")
    schedule_rules = relationship("ScheduleRule", back_populates="business", cascade="all, delete")
    time_blocks = relationship("TimeBlock", back_populates="business", cascade="all, delete")
    schedule_exceptions = relationship("ScheduleException", back_populates="business", cascade="all, delete")
    telegram_user_bindings = relationship(
        "TelegramUserBinding", back_populates="business", cascade="all, delete"
    )


class TelegramUserBinding(Base):
    __tablename__ = "telegram_user_bindings"

    id = Column(Integer, primary_key=True, index=True)
    telegram_user_id = Column(String, unique=True, index=True, nullable=False)
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    business = relationship("Business", back_populates="telegram_user_bindings")


class ScheduleRule(Base):
    __tablename__ = "schedule_rules"

    id = Column(Integer, primary_key=True, index=True)
    day_of_week = Column(Integer, nullable=False) # 0: Monday, 6: Sunday
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    is_available = Column(Boolean, default=True)

    business_id = Column(Integer, ForeignKey("businesses.id"))
    business = relationship("Business", back_populates="schedule_rules")

class TimeBlock(Base):
    __tablename__ = "time_blocks"

    id = Column(Integer, primary_key=True, index=True)
    start_at = Column(DateTime(timezone=True), nullable=False)
    end_at = Column(DateTime(timezone=True), nullable=False)
    reason = Column(String, nullable=True)

    business_id = Column(Integer, ForeignKey("businesses.id"))
    business = relationship("Business", back_populates="time_blocks")


class ScheduleException(Base):
    __tablename__ = "schedule_exceptions"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False)
    type = Column(String, nullable=False)  # block | open
    all_day = Column(Boolean, default=True)
    start_time = Column(Time, nullable=True)
    end_time = Column(Time, nullable=True)
    reason = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        onupdate=lambda: datetime.now(timezone.utc),
        default=lambda: datetime.now(timezone.utc),
    )
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    business = relationship("Business", back_populates="schedule_exceptions")

    deleted_by = Column(Integer, ForeignKey("owners.id"), nullable=True)
    deleted_by_owner = relationship(
        "Owner", back_populates="deleted_schedule_exceptions", foreign_keys=[deleted_by]
    )

class Service(Base):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    duration_minutes = Column(Integer, nullable=False)
    price = Column(Float, nullable=False, default=0.0)
    is_active = Column(Boolean, default=True)

    business_id = Column(Integer, ForeignKey("businesses.id"))
    business = relationship("Business", back_populates="services")

    appointments = relationship("Appointment", back_populates="service")

class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=True) # Sometimes we just have the phone
    phone_number = Column(String, index=True, nullable=False)
    
    business_id = Column(Integer, ForeignKey("businesses.id"))
    business = relationship("Business", back_populates="customers")

    appointments = relationship("Appointment", back_populates="customer", cascade="all, delete")
    waitlist_entries = relationship("WaitlistEntry", back_populates="customer", cascade="all, delete")

class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime(timezone=True), nullable=False)
    status = Column(String, default="P") # P: Pending, C: Confirmed, A: Canceled, D: Done
    reminder_24h_sent = Column(Boolean, default=False)
    reminder_2h_sent = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    business_id = Column(Integer, ForeignKey("businesses.id"))
    business = relationship("Business", back_populates="appointments")

    customer_id = Column(Integer, ForeignKey("customers.id"))
    customer = relationship("Customer", back_populates="appointments")

    service_id = Column(Integer, ForeignKey("services.id"))
    service = relationship("Service", back_populates="appointments")

class WaitlistEntry(Base):
    __tablename__ = "waitlist_entries"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime(timezone=True), nullable=False)
    status = Column(String, default="waiting") # waiting, notified, expired, booked

    business_id = Column(Integer, ForeignKey("businesses.id"))
    business = relationship("Business", back_populates="waitlist_entries")

    customer_id = Column(Integer, ForeignKey("customers.id"))
    customer = relationship("Customer", back_populates="waitlist_entries")

class ConversationState(Base):
    __tablename__ = "conversation_states"

    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String, index=True, nullable=False)
    context_data = Column(JSON, default=dict)
    updated_at = Column(DateTime(timezone=True), onupdate=lambda: datetime.now(timezone.utc), default=lambda: datetime.now(timezone.utc))

    business_id = Column(Integer, ForeignKey("businesses.id"))
    business = relationship("Business", back_populates="conversation_states")

from pydantic import BaseModel, ConfigDict, EmailStr, Field
from typing import Optional, List
from datetime import date, datetime, time

# --- Token Schemas ---
class Token(BaseModel):
    access: str = Field(alias="access_token")
    refresh: str
    user: "OwnerOut"

    model_config = ConfigDict(populate_by_name=True)

class TokenData(BaseModel):
    email: Optional[str] = None

# --- Owner Schemas ---
class OwnerBase(BaseModel):
    name: str
    # str (no EmailStr): dominios de demo tipo .test / .local son rechazados por
    # email-validator al serializar Owner en /auth/token y rompen el login con 500.
    email: str
    phone: Optional[str] = None

class OwnerCreate(OwnerBase):
    password: str

class OwnerOut(OwnerBase):
    id: int
    email_verified: bool = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RegisterResult(BaseModel):
    message: str
    access_token: Optional[str] = None
    refresh: Optional[str] = None
    user: Optional[OwnerOut] = None


class VerifyEmailBody(BaseModel):
    token: str


class RefreshTokenBody(BaseModel):
    refresh: str


class RefreshTokenResponse(BaseModel):
    access_token: str
    refresh: str
    token_type: str = "bearer"


class ResendVerificationBody(BaseModel):
    email: EmailStr

# --- Business Schemas ---
class BusinessBase(BaseModel):
    name: str
    phone_number: str
    category: Optional[str] = "barbershop"
    description: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_active: bool = True
    daily_notification_enabled: bool = True

class BusinessCreate(BusinessBase):
    pass

class BusinessUpdate(BaseModel):
    name: Optional[str] = None
    phone_number: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_active: Optional[bool] = None
    daily_notification_enabled: Optional[bool] = None

class BusinessOut(BusinessBase):
    id: int
    owner_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TelegramActivationOut(BaseModel):
    deep_link: str
    invite_token: str
    bot_username: str
    has_first_contact: bool


class OwnerTelegramActivationOut(BaseModel):
    deep_link: str
    activation_token: str
    payload: str
    bot_username: str
    has_active_binding: bool
    activation_expires_at: datetime

# --- Schedule Schemas ---
class ScheduleRuleBase(BaseModel):
    day_of_week: int
    start_time: time
    end_time: time
    is_available: bool = True

class ScheduleRuleCreate(ScheduleRuleBase):
    pass

class ScheduleRuleOut(ScheduleRuleBase):
    id: int
    business_id: int
    
    model_config = ConfigDict(from_attributes=True)


class ScheduleExceptionBase(BaseModel):
    date: date
    type: str
    all_day: bool = True
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    reason: Optional[str] = None


class ScheduleExceptionCreate(ScheduleExceptionBase):
    pass


class ScheduleExceptionUpdate(BaseModel):
    date: Optional[date] = None
    type: Optional[str] = None
    all_day: Optional[bool] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    reason: Optional[str] = None


class ScheduleExceptionRestore(BaseModel):
    reason: Optional[str] = None


class ScheduleExceptionOut(ScheduleExceptionBase):
    id: int
    business_id: int
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

# --- TimeBlock Schemas ---
class TimeBlockBase(BaseModel):
    start_at: datetime
    end_at: datetime
    reason: Optional[str] = None

class TimeBlockCreate(TimeBlockBase):
    pass

class TimeBlockOut(TimeBlockBase):
    id: int
    business_id: int
    
    model_config = ConfigDict(from_attributes=True)

# --- Service Schemas ---
class ServiceBase(BaseModel):
    name: str
    description: Optional[str] = None
    duration_minutes: int
    price: float = 0.0
    is_active: bool = True

class ServiceCreate(ServiceBase):
    pass

class ServiceOut(ServiceBase):
    id: int
    business_id: int
    
    model_config = ConfigDict(from_attributes=True)

# --- Customer Schemas ---
class CustomerBase(BaseModel):
    name: Optional[str] = None
    phone_number: str

class CustomerCreate(CustomerBase):
    pass

class CustomerOut(CustomerBase):
    id: int
    business_id: int
    
    model_config = ConfigDict(from_attributes=True)

# --- Appointment Schemas ---
class AppointmentBase(BaseModel):
    date: datetime
    status: str = "P" # P: Pending, C: Confirmed, A: Canceled, D: Done
    
class AppointmentCreate(AppointmentBase):
    service_id: int
    customer_id: int

class AppointmentOut(AppointmentBase):
    id: int
    business_id: int
    service_id: int
    customer_id: int
    reminder_24h_sent: bool
    reminder_2h_sent: bool
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

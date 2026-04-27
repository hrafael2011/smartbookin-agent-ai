/**
 * SmartBooking AI - TypeScript Types
 */

// ============================================================================
// AUTH TYPES
// ============================================================================

export interface User {
  id: string
  email: string
  name: string
  role: 'owner' | 'staff'
  email_verified?: boolean
  created_at?: string
}

export interface LoginCredentials {
  email: string
  password: string
}

export interface LoginResponse {
  access: string
  refresh: string
  user: User
}

export interface RegisterPayload {
  name: string
  email: string
  password: string
  phone?: string
}

export interface RegisterApiResponse {
  message: string
  access_token?: string
  refresh?: string
  user?: User
}

// ============================================================================
// OWNER & BUSINESS TYPES
// ============================================================================

export interface Owner {
  id: number
  name: string
  email: string
  phone?: string
  created_at: string
  updated_at: string
}

export interface Business {
  id: number
  owner: number
  name: string
  category: string
  description?: string
  phone: string
  email?: string
  address?: string
  latitude?: number
  longitude?: number
  timezone: string
  whatsapp_phone_number_id?: string
  is_active: boolean
  daily_notification_enabled: boolean
  created_at: string
  updated_at: string
}

export interface BusinessFormData {
  name: string
  phone: string
  category: string
  description?: string
  address?: string
}

// ============================================================================
// SERVICE TYPES
// ============================================================================

export interface Service {
  id: number
  business: number
  business_name?: string
  name: string
  description?: string
  duration_minutes: number // minutes
  price: string // decimal
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface ServiceFormData {
  name: string
  description?: string
  duration_minutes: number
  price: number | string
  is_active: boolean
}

// ============================================================================
// SCHEDULE TYPES
// ============================================================================

export type DayOfWeek = 0 | 1 | 2 | 3 | 4 | 5 | 6

export interface ScheduleRule {
  id: number
  business: number
  day_of_week: number
  start_time: string // HH:MM format
  end_time: string // HH:MM format
  is_available: boolean
  created_at: string
  updated_at: string
}

export interface ScheduleFormData {
  day_of_week: number
  start_time: string
  end_time: string
  is_available: boolean
}

export type ScheduleExceptionType = 'block' | 'open'

export interface ScheduleException {
  id: number
  business_id: number
  date: string
  type: ScheduleExceptionType
  all_day: boolean
  start_time?: string | null
  end_time?: string | null
  reason?: string | null
  created_at: string
  updated_at: string
  deleted_at?: string | null
  deleted_by?: number | null
}

export interface ScheduleExceptionFormData {
  date: string
  type: ScheduleExceptionType
  all_day: boolean
  start_time?: string
  end_time?: string
  reason?: string
}

export interface TimeBlock {
  id: number
  business_id: number
  start_at: string
  end_at: string
  reason?: string
}

export interface TimeBlockFormData {
  start_at: string
  end_at: string
  reason?: string
}

// ============================================================================
// CUSTOMER TYPES
// ============================================================================

export interface Customer {
  id: number
  business: number
  business_name?: string
  name: string
  phone: string
  email?: string
  notes?: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface CustomerFormData {
  name: string
  phone: string
  email?: string
  notes?: string
  is_active?: boolean
}

// ============================================================================
// APPOINTMENT TYPES
// ============================================================================

export type AppointmentStatus =
  | 'pending'
  | 'scheduled'
  | 'confirmed'
  | 'pending_confirmation'
  | 'completed'
  | 'cancelled'
  | 'no_show'

export interface Appointment {
  id: number
  business: number
  business_name?: string
  customer: {
    id: number
    name: string
    phone: string
  }
  service: {
    id: number
    name: string
    duration_minutes: number
    price: string
  }
  scheduled_at: string // ISO datetime
  status: AppointmentStatus
  notes?: string
  cancellation_notes?: string
  reminder_24h_sent: boolean
  reminder_2h_sent: boolean
  created_at: string
  updated_at: string
}

export interface AppointmentFormData {
  customer_id: number | string
  service_id: number | string
  scheduled_at: string
  notes?: string
}

// ============================================================================
// AVAILABILITY TYPES
// ============================================================================

export interface TimeSlot {
  start_time: string // "09:00 AM"
  start_datetime: string // ISO datetime
  end_datetime: string // ISO datetime
  is_preferred: boolean
}

export interface AvailabilityResponse {
  date: string
  service_id: number
  service_name: string
  available_slots: TimeSlot[]
}

export interface AvailabilityParams {
  business_id: number
  service_id: number
  date: string // YYYY-MM-DD
  preferred_time?: string
}

// ============================================================================
// WAITLIST TYPES
// ============================================================================

export type WaitlistStatus = 'pending' | 'offered' | 'accepted' | 'expired'

export interface WaitlistEntry {
  id: number
  business: number
  customer: number
  customer_name?: string
  customer_phone?: string
  service: number
  service_name?: string
  preferred_date?: string
  preferred_time?: string
  status: WaitlistStatus
  offered_at?: string
  created_at: string
  updated_at: string
}

// ============================================================================
// DASHBOARD METRICS TYPES
// ============================================================================

export interface DashboardMetrics {
  today: {
    total_appointments: number
    confirmed: number
    pending: number
    cancelled: number
    revenue: string
  }
  week: {
    total_appointments: number
    revenue: string
    occupancy_rate: number
  }
  month: {
    total_appointments: number
    revenue: string
    new_customers: number
  }
  top_services: Array<{
    service_name: string
    count: number
    revenue: string
  }>
  recent_appointments: Appointment[]
  upcoming_appointments: Appointment[]
}

// ============================================================================
// API RESPONSE TYPES
// ============================================================================

export interface PaginatedResponse<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export interface ApiError {
  detail?: string
  [key: string]: any
}

// ============================================================================
// CALENDAR EVENT TYPES (for react-big-calendar)
// ============================================================================

export interface CalendarEvent {
  id: number
  title: string
  start: Date
  end: Date
  resource: Appointment
}

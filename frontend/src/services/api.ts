/**
 * API Client - Axios configuration and API calls
 */
import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'
import { toast } from 'sonner'
import type {
  LoginCredentials,
  LoginResponse,
  RegisterApiResponse,
  RegisterPayload,
  Business,
  BusinessFormData,
  Service,
  ServiceFormData,
  Customer,
  CustomerFormData,
  Appointment,
  AppointmentFormData,
  ScheduleRule,
  ScheduleFormData,
  ScheduleException,
  ScheduleExceptionFormData,
  AvailabilityResponse,
  AvailabilityParams,
  WaitlistEntry,
  DashboardMetrics,
  OwnerTelegramActivation,
  PaginatedResponse,
  TelegramActivation,
  TimeBlock,
  TimeBlockFormData,
} from '@/types'

const API_BASE_URL =
  (import.meta.env?.VITE_API_URL as string | undefined) ||
  (import.meta.env?.VITE_API_BASE_URL as string | undefined) ||
  '/api'

/** Cliente sin interceptores (refresh token) */
const apiPublic = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
})

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
})

type RawBusiness = {
  id: number
  owner_id?: number
  name: string
  phone_number?: string
  category?: string
  description?: string | null
  address?: string | null
  latitude?: number | null
  longitude?: number | null
  whatsapp_phone_number_id?: string | null
  is_active?: boolean
  daily_notification_enabled?: boolean
  created_at?: string
}

type RawService = {
  id: number
  business_id: number
  name: string
  description?: string | null
  duration_minutes: number
  price: number | string
  is_active?: boolean
}

type RawCustomer = {
  id: number
  business_id: number
  name?: string | null
  phone_number: string
}

type RawAppointment = {
  id: number
  business_id: number
  customer_id: number
  service_id: number
  date: string
  status: string
  reminder_24h_sent: boolean
  reminder_2h_sent: boolean
  created_at: string
}

type RawScheduleException = {
  id: number
  business_id: number
  date: string
  type: 'block' | 'open'
  all_day: boolean
  start_time?: string | null
  end_time?: string | null
  reason?: string | null
  created_at: string
  updated_at: string
  deleted_at?: string | null
  deleted_by?: number | null
}

const nowIso = () => new Date().toISOString()

const statusFromApi = (status: string): Appointment['status'] => {
  const map: Record<string, Appointment['status']> = {
    P: 'pending',
    C: 'confirmed',
    A: 'cancelled',
    D: 'completed',
    pending: 'pending',
    confirmed: 'confirmed',
    cancelled: 'cancelled',
    canceled: 'cancelled',
    completed: 'completed',
  }
  return map[status] || 'pending'
}

const statusToApi = (status: string): string => {
  const map: Record<string, string> = {
    pending: 'P',
    confirmed: 'C',
    cancelled: 'A',
    canceled: 'A',
    completed: 'D',
  }
  return map[status] || status
}

const mapBusiness = (raw: RawBusiness): Business => ({
  id: raw.id,
  owner: raw.owner_id || 0,
  name: raw.name,
  category: raw.category || 'barbershop',
  description: raw.description || undefined,
  phone: raw.phone_number || '',
  email: undefined,
  address: raw.address || undefined,
  latitude: raw.latitude || undefined,
  longitude: raw.longitude || undefined,
  timezone: 'America/Santo_Domingo',
  whatsapp_phone_number_id: raw.whatsapp_phone_number_id || undefined,
  is_active: raw.is_active ?? true,
  daily_notification_enabled: raw.daily_notification_enabled ?? true,
  created_at: raw.created_at || nowIso(),
  updated_at: raw.created_at || nowIso(),
})

const mapService = (raw: RawService): Service => ({
  id: raw.id,
  business: raw.business_id,
  business_name: undefined,
  name: raw.name,
  description: raw.description || undefined,
  duration_minutes: raw.duration_minutes,
  price: String(raw.price ?? 0),
  is_active: raw.is_active ?? true,
  created_at: nowIso(),
  updated_at: nowIso(),
})

const mapCustomer = (raw: RawCustomer): Customer => ({
  id: raw.id,
  business: raw.business_id,
  business_name: undefined,
  name: raw.name || 'Cliente',
  phone: raw.phone_number,
  email: undefined,
  notes: undefined,
  is_active: true,
  created_at: nowIso(),
  updated_at: nowIso(),
})

const mapAppointment = (
  raw: RawAppointment,
  customerById: Map<number, Customer>,
  serviceById: Map<number, Service>
): Appointment => {
  const customer = customerById.get(raw.customer_id)
  const service = serviceById.get(raw.service_id)

  return {
    id: raw.id,
    business: raw.business_id,
    business_name: undefined,
    customer: {
      id: raw.customer_id,
      name: customer?.name || ('Cliente #' + raw.customer_id),
      phone: customer?.phone || '',
    },
    service: {
      id: raw.service_id,
      name: service?.name || ('Servicio #' + raw.service_id),
      duration_minutes: service?.duration_minutes || 30,
      price: service?.price || '0',
    },
    scheduled_at: raw.date,
    status: statusFromApi(raw.status),
    notes: undefined,
    cancellation_notes: undefined,
    reminder_24h_sent: raw.reminder_24h_sent,
    reminder_2h_sent: raw.reminder_2h_sent,
    created_at: raw.created_at,
    updated_at: raw.created_at,
  }
}

const mapScheduleException = (raw: RawScheduleException): ScheduleException => ({
  id: raw.id,
  business_id: raw.business_id,
  date: raw.date,
  type: raw.type,
  all_day: raw.all_day,
  start_time: raw.start_time ?? null,
  end_time: raw.end_time ?? null,
  reason: raw.reason ?? null,
  created_at: raw.created_at,
  updated_at: raw.updated_at,
  deleted_at: raw.deleted_at ?? null,
  deleted_by: raw.deleted_by ?? null,
})

async function fetchCustomersAndServicesMaps(businessId: number): Promise<{
  customerById: Map<number, Customer>
  serviceById: Map<number, Service>
}> {
  const [customersRes, servicesRes] = await Promise.all([
    api.get<RawCustomer[]>('/businesses/' + businessId + '/customers'),
    api.get<RawService[]>('/businesses/' + businessId + '/services'),
  ])

  const customers = customersRes.data.map(mapCustomer)
  const services = servicesRes.data.map(mapService)

  return {
    customerById: new Map(customers.map((c) => [c.id, c])),
    serviceById: new Map(services.map((s) => [s.id, s])),
  }
}

api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('access_token')
    if (token && config.headers) {
      config.headers.Authorization = 'Bearer ' + token
    }
    return config
  },
  (error) => Promise.reject(error)
)

function isAuthPath(url: string | undefined): boolean {
  if (!url) return false
  return (
    url.includes('/auth/token') ||
    url.includes('/auth/refresh') ||
    url.includes('/auth/register') ||
    url.includes('/auth/verify-email') ||
    url.includes('/auth/logout')
  )
}

function getApiErrorMessage(error: AxiosError): string | null {
  if (!error.response) {
    return 'No se pudo conectar con el servidor. Revisa tu conexión.'
  }

  const data = error.response.data as { detail?: unknown; message?: unknown } | undefined
  const detail = data?.detail || data?.message
  if (typeof detail === 'string') {
    return detail
  }

  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: unknown } | undefined
    if (typeof first?.msg === 'string') {
      return first.msg
    }
  }

  const statusMessages: Record<number, string> = {
    400: 'La información enviada no es válida.',
    403: 'No tienes permiso para realizar esta acción.',
    404: 'No se encontró el recurso solicitado.',
    409: 'La operación entra en conflicto con información existente.',
    422: 'Revisa los campos del formulario.',
  }

  if (error.response.status >= 500) {
    return 'Error en el servidor. Por favor, intenta más tarde.'
  }

  return statusMessages[error.response.status] || null
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & {
      _retry?: boolean
    }
    const reqUrl = String(originalRequest?.url || '')

    if (
      error.response?.status === 401 &&
      originalRequest &&
      !originalRequest._retry &&
      !isAuthPath(reqUrl)
    ) {
      originalRequest._retry = true
      const refresh = localStorage.getItem('refresh_token')
      if (refresh) {
        try {
          const { data } = await apiPublic.post<{
            access_token: string
            refresh?: string
          }>('/auth/refresh', {
            refresh,
          })
          localStorage.setItem('access_token', data.access_token)
          if (data.refresh) {
            localStorage.setItem('refresh_token', data.refresh)
          }
          if (originalRequest.headers) {
            originalRequest.headers.Authorization = 'Bearer ' + data.access_token
          }
          return api(originalRequest)
        } catch {
          /* cae al logout */
        }
      }
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      window.location.href = '/login'
    }

    const message = getApiErrorMessage(error)
    if (message && !isAuthPath(reqUrl)) {
      toast.error(message)
    }

    return Promise.reject(error)
  }
)

function mapOwnerToUser(raw: Record<string, unknown>): LoginResponse['user'] {
  return {
    id: String(raw.id),
    email: String(raw.email),
    name: String(raw.name),
    role: 'owner',
    email_verified: raw.email_verified === true,
    created_at: raw.created_at ? String(raw.created_at) : undefined,
  }
}

export const authAPI = {
  register: async (payload: RegisterPayload): Promise<RegisterApiResponse> => {
    const regBody: Record<string, unknown> = {
      name: payload.name,
      email: payload.email,
      password: payload.password,
    }
    if (payload.phone?.trim()) {
      regBody.phone = payload.phone.trim()
    }
    const response = await api.post<{
      message: string
      access_token?: string
      refresh?: string
      user?: Record<string, unknown>
    }>('/auth/register', regBody)
    const d = response.data
    return {
      message: d.message,
      access_token: d.access_token,
      refresh: d.refresh,
      user: d.user ? mapOwnerToUser(d.user) : undefined,
    }
  },

  verifyEmail: async (token: string): Promise<void> => {
    await api.post('/auth/verify-email', { token })
  },

  resendVerification: async (email: string): Promise<void> => {
    await apiPublic.post('/auth/resend-verification', { email })
  },

  login: async (credentials: LoginCredentials): Promise<LoginResponse> => {
    const params = new URLSearchParams()
    params.append('username', credentials.email)
    params.append('password', credentials.password)

    const response = await api.post<any>('/auth/token', params, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    })

    return {
      access: response.data.access_token,
      refresh: response.data.refresh,
      user: mapOwnerToUser(response.data.user as Record<string, unknown>),
    }
  },

  logout: async (): Promise<void> => {
    try {
      await api.post('/auth/logout')
    } catch {
      /* sesión ya inválida */
    } finally {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
    }
  },

  refreshToken: async (refresh: string): Promise<{ access: string; refresh?: string }> => {
    const { data } = await apiPublic.post<{
      access_token: string
      refresh: string
    }>('/auth/refresh', {
      refresh,
    })
    return { access: data.access_token, refresh: data.refresh }
  },
}

export const businessAPI = {
  list: async (): Promise<Business[]> => {
    const response = await api.get<RawBusiness[]>('/businesses/')
    return response.data.map(mapBusiness)
  },

  create: async (data: BusinessFormData): Promise<Business> => {
    const response = await api.post<RawBusiness>('/businesses/', {
      name: data.name,
      phone_number: data.phone,
      category: data.category,
      description: data.description || undefined,
      address: data.address || undefined,
    })
    return mapBusiness(response.data)
  },

  get: async (id: number): Promise<Business> => {
    const response = await api.get<RawBusiness>('/businesses/' + id)
    return mapBusiness(response.data)
  },

  update: async (id: number, data: Partial<Business>): Promise<Business> => {
    const payload: Record<string, unknown> = { ...data }
    if ('phone' in payload) {
      payload.phone_number = payload.phone
      delete payload.phone
    }
    if ('owner' in payload) {
      payload.owner_id = payload.owner
      delete payload.owner
    }

    const response = await api.patch<RawBusiness>('/businesses/' + id, payload)
    return mapBusiness(response.data)
  },
}

export const servicesAPI = {
  list: async (businessId?: number): Promise<Service[]> => {
    if (!businessId) return []
    const response = await api.get<RawService[]>('/businesses/' + businessId + '/services')
    return response.data.map(mapService)
  },

  get: async (id: number, businessId?: number): Promise<Service> => {
    if (!businessId) throw new Error('businessId is required')
    const response = await api.get<RawService>(
      '/businesses/' + businessId + '/services/' + id
    )
    return mapService(response.data)
  },

  create: async (data: ServiceFormData & { business: number }): Promise<Service> => {
    const response = await api.post<RawService>(
      '/businesses/' + data.business + '/services',
      {
        name: data.name,
        description: data.description,
        duration_minutes: Number(data.duration_minutes),
        price: Number(data.price),
        is_active: data.is_active,
      }
    )
    return mapService(response.data)
  },

  update: async (
    id: number,
    data: Partial<ServiceFormData>,
    businessId?: number
  ): Promise<Service> => {
    if (!businessId) throw new Error('businessId is required')
    const response = await api.patch<RawService>(
      '/businesses/' + businessId + '/services/' + id,
      {
        ...data,
        price: data.price !== undefined ? Number(data.price) : undefined,
      }
    )
    return mapService(response.data)
  },

  delete: async (id: number, businessId?: number): Promise<void> => {
    if (!businessId) throw new Error('businessId is required')
    await api.delete('/businesses/' + businessId + '/services/' + id)
  },
}

export const customersAPI = {
  list: async (
    businessId?: number,
    _page?: number
  ): Promise<PaginatedResponse<Customer>> => {
    if (!businessId) {
      return {
        count: 0,
        next: null,
        previous: null,
        results: [],
      }
    }

    const response = await api.get<RawCustomer[]>('/businesses/' + businessId + '/customers')
    const results = response.data.map(mapCustomer)

    return {
      count: results.length,
      next: null,
      previous: null,
      results,
    }
  },

  get: async (id: number, businessId?: number): Promise<Customer> => {
    if (!businessId) throw new Error('businessId is required')
    const response = await api.get<RawCustomer>(
      '/businesses/' + businessId + '/customers/' + id
    )
    return mapCustomer(response.data)
  },

  create: async (data: CustomerFormData & { business: number }): Promise<Customer> => {
    const response = await api.post<RawCustomer>(
      '/businesses/' + data.business + '/customers',
      {
        name: data.name,
        phone_number: data.phone,
      }
    )
    return mapCustomer(response.data)
  },

  update: async (
    id: number,
    data: Partial<CustomerFormData>,
    businessId?: number
  ): Promise<Customer> => {
    if (!businessId) throw new Error('businessId is required')
    const response = await api.patch<RawCustomer>(
      '/businesses/' + businessId + '/customers/' + id,
      {
        name: data.name,
        phone_number: data.phone,
      }
    )
    return mapCustomer(response.data)
  },

  delete: async (id: number, businessId?: number): Promise<void> => {
    if (!businessId) throw new Error('businessId is required')
    await api.delete('/businesses/' + businessId + '/customers/' + id)
  },

  getAppointments: async (_customerId: number, _upcoming = false): Promise<Appointment[]> => {
    return []
  },
}

export const appointmentsAPI = {
  list: async (
    businessId?: number,
    dateFrom?: string,
    dateTo?: string,
    status?: string
  ): Promise<Appointment[]> => {
    if (!businessId) return []

    const params: Record<string, string> = {}
    if (dateFrom) params.date_from = dateFrom
    if (dateTo) params.date_to = dateTo
    if (status) params.status = statusToApi(status)

    const [appointmentsRes, lookups] = await Promise.all([
      api.get<RawAppointment[]>('/businesses/' + businessId + '/appointments', { params }),
      fetchCustomersAndServicesMaps(businessId),
    ])

    return appointmentsRes.data.map((raw) =>
      mapAppointment(raw, lookups.customerById, lookups.serviceById)
    )
  },

  get: async (id: number, businessId?: number): Promise<Appointment> => {
    if (!businessId) throw new Error('businessId is required')

    const [appointmentRes, lookups] = await Promise.all([
      api.get<RawAppointment>('/businesses/' + businessId + '/appointments/' + id),
      fetchCustomersAndServicesMaps(businessId),
    ])

    return mapAppointment(appointmentRes.data, lookups.customerById, lookups.serviceById)
  },

  create: async (
    data: AppointmentFormData & { business: number }
  ): Promise<Appointment> => {
    const payload = {
      date: data.scheduled_at,
      status: 'P',
      service_id: Number(data.service_id),
      customer_id: Number(data.customer_id),
    }

    const response = await api.post<RawAppointment>(
      '/businesses/' + data.business + '/appointments',
      payload
    )

    const lookups = await fetchCustomersAndServicesMaps(data.business)
    return mapAppointment(response.data, lookups.customerById, lookups.serviceById)
  },

  update: async (
    id: number,
    data: Partial<AppointmentFormData>,
    businessId?: number
  ): Promise<Appointment> => {
    if (!businessId) throw new Error('businessId is required')

    const payload: Record<string, unknown> = {}
    if (data.scheduled_at) payload.scheduled_at = data.scheduled_at
    if (data.customer_id !== undefined) payload.customer_id = Number(data.customer_id)
    if (data.service_id !== undefined) payload.service_id = Number(data.service_id)

    const response = await api.patch<RawAppointment>(
      '/businesses/' + businessId + '/appointments/' + id,
      payload
    )

    const lookups = await fetchCustomersAndServicesMaps(businessId)
    return mapAppointment(response.data, lookups.customerById, lookups.serviceById)
  },

  delete: async (id: number, businessId?: number): Promise<void> => {
    if (!businessId) throw new Error('businessId is required')
    await api.delete('/businesses/' + businessId + '/appointments/' + id)
  },

  cancel: async (id: number, _notes?: string, businessId?: number): Promise<Appointment> => {
    if (!businessId) throw new Error('businessId is required')

    const response = await api.post<RawAppointment>(
      '/businesses/' + businessId + '/appointments/' + id + '/cancel',
      {}
    )

    const lookups = await fetchCustomersAndServicesMaps(businessId)
    return mapAppointment(response.data, lookups.customerById, lookups.serviceById)
  },

  getAvailability: async (params: AvailabilityParams): Promise<AvailabilityResponse> => {
    const baseDate = params.date
    return {
      date: baseDate,
      service_id: params.service_id,
      service_name: 'Servicio',
      available_slots: [
        {
          start_time: '09:00 AM',
          start_datetime: baseDate + 'T09:00:00',
          end_datetime: baseDate + 'T09:30:00',
          is_preferred: !params.preferred_time || params.preferred_time.startsWith('09'),
        },
        {
          start_time: '02:00 PM',
          start_datetime: baseDate + 'T14:00:00',
          end_datetime: baseDate + 'T14:30:00',
          is_preferred: !!params.preferred_time && params.preferred_time.startsWith('14'),
        },
      ],
    }
  },
}

export const scheduleAPI = {
  list: async (businessId: number): Promise<ScheduleRule[]> => {
    const response = await api.get<any[]>('/schedule-rules/', {
      params: { business_id: businessId },
    })

    return (response.data || []).map((rule) => ({
      id: rule.id,
      business: rule.business_id,
      day_of_week: rule.day_of_week,
      start_time: rule.start_time,
      end_time: rule.end_time,
      is_available: rule.is_available,
      created_at: nowIso(),
      updated_at: nowIso(),
    }))
  },

  get: async (id: number): Promise<ScheduleRule> => {
    throw new Error('Schedule get by id not implemented. id=' + id)
  },

  create: async (
    data: ScheduleFormData & { business: number }
  ): Promise<ScheduleRule> => {
    const { business, ...ruleData } = data
    const response = await api.post<any>('/schedule-rules/', ruleData, {
      params: { business_id: business },
    })

    const rule = response.data
    return {
      id: rule.id,
      business: rule.business_id,
      day_of_week: rule.day_of_week,
      start_time: rule.start_time,
      end_time: rule.end_time,
      is_available: rule.is_available,
      created_at: nowIso(),
      updated_at: nowIso(),
    }
  },

  update: async (_id: number, _data: Partial<ScheduleFormData>): Promise<ScheduleRule> => {
    throw new Error('Schedule update endpoint not implemented in backend')
  },

  delete: async (id: number): Promise<void> => {
    await api.delete('/schedule-rules/' + id)
  },

  listExceptions: async (
    businessId: number,
    options?: { from?: string; to?: string; includeDeleted?: boolean }
  ): Promise<ScheduleException[]> => {
    const response = await api.get<RawScheduleException[]>('/schedule-exceptions/', {
      params: {
        business_id: businessId,
        from: options?.from,
        to: options?.to,
        include_deleted: options?.includeDeleted ?? false,
      },
    })
    return (response.data || []).map(mapScheduleException)
  },

  createException: async (
    data: ScheduleExceptionFormData & { business: number }
  ): Promise<ScheduleException> => {
    const { business, ...payload } = data
    const response = await api.post<RawScheduleException>('/schedule-exceptions/', payload, {
      params: { business_id: business },
    })
    return mapScheduleException(response.data)
  },

  updateException: async (
    id: number,
    data: Partial<ScheduleExceptionFormData>
  ): Promise<ScheduleException> => {
    const response = await api.patch<RawScheduleException>(
      '/schedule-exceptions/' + id,
      data
    )
    return mapScheduleException(response.data)
  },

  archiveException: async (id: number): Promise<void> => {
    await api.delete('/schedule-exceptions/' + id)
  },

  restoreException: async (id: number, reason?: string): Promise<ScheduleException> => {
    const response = await api.post<RawScheduleException>(
      '/schedule-exceptions/' + id + '/restore',
      { reason: reason || null }
    )
    return mapScheduleException(response.data)
  },
}

export const waitlistAPI = {
  list: async (_businessId: number): Promise<WaitlistEntry[]> => {
    return []
  },
}

export const timeBlocksAPI = {
  list: async (businessId: number): Promise<TimeBlock[]> => {
    const response = await api.get<TimeBlock[]>('/time-blocks/', {
      params: { business_id: businessId },
    })
    return response.data
  },

  create: async (
    businessId: number,
    data: TimeBlockFormData
  ): Promise<TimeBlock> => {
    const response = await api.post<TimeBlock>('/time-blocks/', data, {
      params: { business_id: businessId },
    })
    return response.data
  },

  delete: async (id: number): Promise<void> => {
    await api.delete('/time-blocks/' + id)
  },
}

export const dashboardAPI = {
  getMetrics: async (businessId: number): Promise<DashboardMetrics> => {
    const response = await api.get<DashboardMetrics>('/dashboard/metrics/', {
      params: { business_id: businessId },
    })
    return response.data
  },
}

export const telegramAPI = {
  getActivation: async (businessId: number): Promise<TelegramActivation> => {
    const response = await api.get<TelegramActivation>(
      '/businesses/' + businessId + '/telegram'
    )
    return response.data
  },
  rotateInvite: async (businessId: number): Promise<TelegramActivation> => {
    const response = await api.post<TelegramActivation>(
      '/businesses/' + businessId + '/telegram/rotate-invite'
    )
    return response.data
  },
}

export const ownerTelegramAPI = {
  getActivation: async (businessId: number): Promise<OwnerTelegramActivation> => {
    const response = await api.get<OwnerTelegramActivation>(
      '/businesses/' + businessId + '/owner-telegram'
    )
    return response.data
  },
}

export default api

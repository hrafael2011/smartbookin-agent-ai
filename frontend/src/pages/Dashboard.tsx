/**
 * Dashboard Page - Main metrics and overview
 */
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useBusinessStore } from '@/store/businessStore'
import { dashboardAPI, appointmentsAPI, servicesAPI, scheduleAPI, telegramAPI } from '@/services/api'
import type { DashboardMetrics, Appointment, Service, ScheduleRule, TelegramActivation } from '@/types'
import { formatCurrency, formatDate, formatTime } from '@/utils/formatters'
import {
  Calendar,
  DollarSign,
  Users,
  TrendingUp,
  Clock,
  CalendarDays,
  CreditCard,
  CheckCircle2,
  Circle,
  MessageCircle,
  Scissors,
  CalendarClock,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Skeleton } from '@/components/ui/Skeleton'

export default function Dashboard() {
  const { currentBusiness } = useBusinessStore()
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null)
  const [todayAppointments, setTodayAppointments] = useState<Appointment[]>([])
  const [services, setServices] = useState<Service[]>([])
  const [scheduleRules, setScheduleRules] = useState<ScheduleRule[]>([])
  const [telegramActivation, setTelegramActivation] = useState<TelegramActivation | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    if (currentBusiness) {
      loadDashboardData()
    }
  }, [currentBusiness])

  const loadDashboardData = async () => {
    if (!currentBusiness) return

    setIsLoading(true)
    try {
      const today = new Date().toISOString().split('T')[0]
      const [
        metricsResult,
        appointmentsResult,
        servicesResult,
        scheduleResult,
        telegramResult,
      ] = await Promise.allSettled([
        dashboardAPI.getMetrics(currentBusiness.id),
        appointmentsAPI.list(currentBusiness.id, today, today),
        servicesAPI.list(currentBusiness.id),
        scheduleAPI.list(currentBusiness.id),
        telegramAPI.getActivation(currentBusiness.id),
      ])

      if (metricsResult.status === 'fulfilled') setMetrics(metricsResult.value)
      if (appointmentsResult.status === 'fulfilled') setTodayAppointments(appointmentsResult.value)
      if (servicesResult.status === 'fulfilled') setServices(servicesResult.value)
      if (scheduleResult.status === 'fulfilled') setScheduleRules(scheduleResult.value)
      if (telegramResult.status === 'fulfilled') setTelegramActivation(telegramResult.value)
    } catch (error) {
      console.error('Error loading dashboard:', error)
    } finally {
      setIsLoading(false)
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-8 animate-fade-in">
        <div className="flex justify-between items-center">
          <div className="space-y-2">
            <Skeleton className="h-10 w-48" />
            <Skeleton className="h-4 w-64" />
          </div>
          <div className="flex gap-3">
            <Skeleton className="h-9 w-28" />
            <Skeleton className="h-9 w-28" />
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {[1, 2, 3, 4].map((i) => (
            <Card key={i} className="h-32">
              <CardContent className="p-6 space-y-4">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-8 w-16" />
              </CardContent>
            </Card>
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card className="h-96">
            <CardContent className="p-6 space-y-4">
              <Skeleton className="h-6 w-32" />
              <div className="space-y-4 pt-4">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="flex gap-4">
                    <Skeleton className="h-12 w-12 rounded-lg" />
                    <div className="space-y-2 flex-1">
                      <Skeleton className="h-4 w-32" />
                      <Skeleton className="h-3 w-48" />
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
          <Card className="h-96">
            <CardContent className="p-6 space-y-4">
              <Skeleton className="h-6 w-32" />
              <div className="space-y-6 pt-4">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="flex justify-between">
                    <div className="flex gap-4">
                      <Skeleton className="h-8 w-8 rounded-full" />
                      <div className="space-y-2">
                        <Skeleton className="h-4 w-32" />
                        <Skeleton className="h-3 w-24" />
                      </div>
                    </div>
                    <Skeleton className="h-5 w-16" />
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    )
  }

  if (!metrics) {
    return (
      <div className="flex flex-col items-center justify-center h-[50vh] text-center space-y-4">
        <div className="p-4 bg-muted rounded-full">
          <CalendarDays className="w-8 h-8 text-muted-foreground" />
        </div>
        <div>
          <h2 className="text-xl font-semibold">No hay datos disponibles</h2>
          <p className="text-muted-foreground">Selecciona un negocio o contacta soporte.</p>
        </div>
      </div>
    )
  }

  const hasServices = services.some((service) => service.is_active)
  const hasSchedule = scheduleRules.some((rule) => rule.is_available)
  const hasTelegramLink = Boolean(telegramActivation?.deep_link || telegramActivation?.invite_token)
  const hasTestAppointment = todayAppointments.length > 0 || metrics.week.total_appointments > 0
  const setupSteps = [
    {
      label: 'Negocio creado',
      description: currentBusiness?.name || 'Tu negocio ya está listo',
      done: Boolean(currentBusiness),
      href: '/dashboard',
      icon: CheckCircle2,
    },
    {
      label: 'Crear servicios',
      description: 'Agrega al menos un servicio activo',
      done: hasServices,
      href: '/services',
      icon: Scissors,
    },
    {
      label: 'Configurar horarios',
      description: 'Define cuándo atiendes',
      done: hasSchedule,
      href: '/schedule',
      icon: CalendarClock,
    },
    {
      label: 'Activar Telegram',
      description: 'Copia el enlace para tus clientes',
      done: hasTelegramLink,
      href: '/telegram',
      icon: MessageCircle,
    },
    {
      label: 'Primera cita',
      description: 'Crea o recibe una cita de prueba',
      done: hasTestAppointment,
      href: '/appointments',
      icon: CalendarDays,
    },
  ]
  const completedSteps = setupSteps.filter((step) => step.done).length
  const setupComplete = completedSteps === setupSteps.length

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Dashboard</h1>
          <p className="text-muted-foreground mt-1">
            {currentBusiness?.name} • {formatDate(new Date())}
          </p>
        </div>
        <div className="flex gap-3">
          <Link to="/calendar">
            <Button variant="outline" size="sm">
              <CalendarDays className="w-4 h-4 mr-2" />
              Ver Calendario
            </Button>
          </Link>
          <Link to="/appointments">
            <Button size="sm">
              Nueva Cita
            </Button>
          </Link>
        </div>
      </div>

      {!setupComplete && (
        <Card>
          <CardHeader className="border-b border-border/40">
            <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
              <div>
                <CardTitle>Configura tu negocio</CardTitle>
                <p className="mt-1 text-sm text-muted-foreground">
                  Completa estos pasos para empezar a recibir citas.
                </p>
              </div>
              <Badge variant="outline">
                {completedSteps}/{setupSteps.length} completados
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            <div className="divide-y divide-border/50">
              {setupSteps.map((step) => (
                <Link
                  key={step.label}
                  to={step.href}
                  className="flex items-center justify-between gap-4 p-4 transition-colors hover:bg-muted/40"
                >
                  <div className="flex items-center gap-3">
                    <div className={step.done ? 'text-green-600' : 'text-muted-foreground'}>
                      {step.done ? (
                        <CheckCircle2 className="h-5 w-5" />
                      ) : (
                        <Circle className="h-5 w-5" />
                      )}
                    </div>
                    <div>
                      <div className="font-medium text-foreground">{step.label}</div>
                      <div className="text-sm text-muted-foreground">{step.description}</div>
                    </div>
                  </div>
                  <step.icon className="h-5 w-5 text-muted-foreground" />
                </Link>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {/* Appointments Today */}
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Citas Hoy</p>
                <div className="flex items-baseline gap-2">
                  <span className="text-3xl font-bold">{metrics.today.total_appointments}</span>
                </div>
              </div>
              <div className="p-3 bg-primary/10 rounded-xl">
                <Calendar className="w-5 h-5 text-primary" />
              </div>
            </div>
            <div className="mt-4 flex items-center text-sm">
              <Badge variant="success" className="mr-2">
                {metrics.today.confirmed}
              </Badge>
              <span className="text-muted-foreground">confirmadas</span>
            </div>
          </CardContent>
        </Card>

        {/* Revenue Today */}
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Ingresos Hoy</p>
                <div className="flex items-baseline gap-2">
                  <span className="text-3xl font-bold">{formatCurrency(metrics.today.revenue)}</span>
                </div>
              </div>
              <div className="p-3 bg-green-500/10 rounded-xl">
                <DollarSign className="w-5 h-5 text-green-600 dark:text-green-400" />
              </div>
            </div>
            <div className="mt-4 flex items-center text-sm text-muted-foreground">
              <TrendingUp className="w-4 h-4 text-green-500 mr-1" />
              <span className="text-green-600 dark:text-green-400 font-medium mr-1">
                {metrics.week.occupancy_rate}%
              </span>
              ocupación
            </div>
          </CardContent>
        </Card>

        {/* Weekly Stats */}
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Semana Actual</p>
                <div className="flex items-baseline gap-2">
                  <span className="text-3xl font-bold">{metrics.week.total_appointments}</span>
                  <span className="text-sm text-muted-foreground">citas</span>
                </div>
              </div>
              <div className="p-3 bg-secondary/10 rounded-xl">
                <TrendingUp className="w-5 h-5 text-secondary" />
              </div>
            </div>
            <div className="mt-4 flex items-center text-sm text-muted-foreground">
              <CreditCard className="w-4 h-4 mr-1 text-muted-foreground" />
              {formatCurrency(metrics.week.revenue)} est.
            </div>
          </CardContent>
        </Card>

        {/* New Customers */}
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Nuevos Clientes</p>
                <div className="flex items-baseline gap-2">
                  <span className="text-3xl font-bold">{metrics.month.new_customers}</span>
                </div>
              </div>
              <div className="p-3 bg-orange-500/10 rounded-xl">
                <Users className="w-5 h-5 text-orange-600 dark:text-orange-400" />
              </div>
            </div>
            <div className="mt-4 flex items-center text-sm text-muted-foreground">
              <span className="inline-block w-2 h-2 rounded-full bg-green-500 mr-2"></span>
              Este mes
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Today's Schedule List */}
        <Card className="h-full">
          <CardHeader className="border-b border-border/40 bg-muted/40 backdrop-blur">
            <div className="flex items-center justify-between">
              <CardTitle>Agenda de Hoy</CardTitle>
              <Badge variant="outline">{todayAppointments.length} Citas</Badge>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {todayAppointments.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center mb-3">
                  <Clock className="w-6 h-6 text-muted-foreground" />
                </div>
                <p className="text-muted-foreground">No tienes citas programadas hoy</p>
              </div>
            ) : (
              <div className="divide-y divide-border/50">
                {todayAppointments.map((appointment) => (
                  <div
                    key={appointment.id}
                    className="flex items-center justify-between p-4 hover:bg-muted/30 transition-colors"
                  >
                    <div className="flex items-center gap-4">
                      <div className="flex flex-col items-center justify-center w-14 h-14 rounded-lg bg-primary/5 border border-primary/10">
                        <span className="text-xs font-bold text-primary uppercase">
                          {formatTime(appointment.scheduled_at).split(' ')[1]}
                        </span>
                        <span className="text-lg font-bold text-foreground">
                          {formatTime(appointment.scheduled_at).split(' ')[0]}
                        </span>
                      </div>
                      <div>
                        <p className="font-semibold text-foreground">{appointment.customer.name}</p>
                        <p className="text-sm text-muted-foreground flex items-center">
                          {appointment.service.name}
                        </p>
                      </div>
                    </div>
                    <div>
                      <Badge
                        variant={
                          appointment.status === 'confirmed' ? 'success' :
                            appointment.status === 'cancelled' ? 'destructive' : 'warning'
                        }
                      >
                        {appointment.status === 'confirmed' ? 'Confirmada' :
                          appointment.status === 'cancelled' ? 'Cancelada' : 'Pendiente'}
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Top Services */}
        <Card className="h-full">
          <CardHeader className="border-b border-border/40">
            <CardTitle>Servicios Populares</CardTitle>
          </CardHeader>
          <CardContent className="p-6">
            {metrics.top_services.length === 0 ? (
              <p className="text-muted-foreground text-center py-8">
                No hay suficientes datos aún
              </p>
            ) : (
              <div className="space-y-6">
                {metrics.top_services.map((service, index) => (
                  <div key={index} className="group flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className="w-8 h-8 rounded-full bg-secondary/10 text-secondary flex items-center justify-center text-xs font-bold">
                        #{index + 1}
                      </div>
                      <div>
                        <p className="font-medium text-foreground group-hover:text-primary transition-colors">
                          {service.service_name}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {service.count} reservas totales
                        </p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="font-semibold text-foreground">
                        {formatCurrency(service.revenue)}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

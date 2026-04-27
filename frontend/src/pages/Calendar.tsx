import { useState, useEffect, useMemo } from 'react';
import { Calendar as BigCalendar, dateFnsLocalizer, View } from 'react-big-calendar';
import { format, parse, startOfWeek, getDay } from 'date-fns';
import { es } from 'date-fns/locale';
import 'react-big-calendar/lib/css/react-big-calendar.css';
import { Plus, CalendarClock } from 'lucide-react';
import { toast } from 'sonner';
import { Button, Modal, Select, Input, Badge, Card, CardContent, EmptyState } from '@/components/ui';
import { appointmentsAPI, customersAPI, servicesAPI, scheduleAPI } from '@/services/api';
import { Appointment, AppointmentFormData, Customer, Service, CalendarEvent, ScheduleRule } from '@/types';
import { formatCurrency, formatPhone } from '@/utils/formatters';

const locales = {
  es: es,
};

const localizer = dateFnsLocalizer({
  format,
  parse,
  startOfWeek,
  getDay,
  locales,
});

import { useBusinessStore } from '@/store/businessStore';

export function Calendar() {
  const { currentBusiness } = useBusinessStore();
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [services, setServices] = useState<Service[]>([]);
  const [scheduleRules, setScheduleRules] = useState<ScheduleRule[]>([]);
  const [view, setView] = useState<View>('month');
  const [date, setDate] = useState(new Date());
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState<Appointment | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [showQuickCustomer, setShowQuickCustomer] = useState(false);
  const [quickCustomer, setQuickCustomer] = useState({ name: '', phone: '' });
  const [formData, setFormData] = useState<AppointmentFormData>({
    customer_id: '',
    service_id: '',
    scheduled_at: '',
    notes: '',
  });

  const hasActiveServices = services.length > 0;
  const hasCustomers = customers.length > 0;
  const hasAvailableSchedule = scheduleRules.some((rule) => rule.is_available);
  const canCreateAppointment = hasActiveServices && hasCustomers && hasAvailableSchedule;

  useEffect(() => {
    if (currentBusiness) {
      loadData();
    }
  }, [currentBusiness]);

  const loadData = async () => {
    if (!currentBusiness) return;
    try {
      setIsLoading(true);
      const [appointmentsResponse, customersResponse, servicesResponse, schedulesResponse] = await Promise.allSettled([
        appointmentsAPI.list(currentBusiness.id),
        customersAPI.list(currentBusiness.id),
        servicesAPI.list(currentBusiness.id),
        scheduleAPI.list(currentBusiness.id),
      ]);

      if (appointmentsResponse.status === 'fulfilled') {
        setAppointments(appointmentsResponse.value || []);
      }

      if (customersResponse.status === 'fulfilled') {
        const data = customersResponse.value;
        // Handle paginated or list response
        const customerList = Array.isArray(data) ? data : (data as any).results || [];
        setCustomers(customerList);
      }

      if (servicesResponse.status === 'fulfilled') {
        setServices((servicesResponse.value || []).filter(s => s.is_active));
      }

      if (schedulesResponse.status === 'fulfilled') {
        setScheduleRules(schedulesResponse.value || []);
      }
    } catch (error) {
      console.error('Error loading data:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const events: CalendarEvent[] = useMemo(() => {
    if (!appointments) return [];
    return appointments.map((apt) => {
      // Validate dates
      const startDate = new Date(apt.scheduled_at);
      const duration = apt.service?.duration_minutes || 30;
      const endDate = new Date(startDate.getTime() + duration * 60000);

      return {
        id: apt.id,
        title: `${apt.customer?.name || 'Cliente'} - ${apt.service?.name || 'Servicio'}`,
        start: isNaN(startDate.getTime()) ? new Date() : startDate,
        end: isNaN(endDate.getTime()) ? new Date() : endDate,
        resource: apt,
      };
    });
  }, [appointments]);

  const handleSelectSlot = ({ start }: { start: Date; end: Date }) => {
    if (!canCreateAppointment) {
      if (!hasActiveServices) {
        toast.error('Crea al menos un servicio activo antes de registrar citas');
      } else if (!hasAvailableSchedule) {
        toast.error('Configura al menos un día disponible antes de registrar citas');
      } else if (!hasCustomers) {
        toast.error('Crea al menos un cliente antes de registrar citas manuales');
      }
      return;
    }

    setSelectedEvent(null);
    setFormData({
      customer_id: '',
      service_id: '',
      scheduled_at: format(start, "yyyy-MM-dd'T'HH:mm"),
      notes: '',
    });
    setIsModalOpen(true);
  };

  const handleSelectEvent = (event: CalendarEvent) => {
    setSelectedEvent(event.resource);
    setIsModalOpen(true);
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
    setSelectedEvent(null);
    setShowQuickCustomer(false);
    setQuickCustomer({ name: '', phone: '' });
  };

  const handleCreateQuickCustomer = async () => {
    if (!currentBusiness) return;
    const name = quickCustomer.name.trim();
    const phone = quickCustomer.phone.trim();
    if (!name || !phone) {
      toast.error('Nombre y teléfono del cliente son obligatorios');
      return;
    }

    setIsLoading(true);
    try {
      const created = await customersAPI.create({
        business: currentBusiness.id,
        name,
        phone,
        email: '',
        is_active: true,
      });
      setCustomers((prev) => [...prev, created]);
      setFormData((prev) => ({ ...prev, customer_id: created.id }));
      setShowQuickCustomer(false);
      setQuickCustomer({ name: '', phone: '' });
      toast.success('Cliente creado y seleccionado');
    } catch (error) {
      console.error('Error creating quick customer:', error);
      toast.error('No se pudo crear el cliente');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      if (!currentBusiness) return;
      await appointmentsAPI.create({ ...formData, business: currentBusiness.id });
      await loadData();
      toast.success('Cita creada correctamente');
      handleCloseModal();
    } catch (error) {
      console.error('Error creating appointment:', error);
      toast.error('Error al crear la cita');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCancel = async () => {
    if (!selectedEvent || !currentBusiness) return;
    if (!confirm('¿Estás seguro de que quieres cancelar esta cita?')) return;

    try {
      await appointmentsAPI.cancel(selectedEvent.id, undefined, currentBusiness.id);
      await loadData();
      toast.success('Cita cancelada correctamente');
      handleCloseModal();
    } catch (error) {
      console.error('Error canceling appointment:', error);
      toast.error('Error al cancelar la cita');
    }
  };

  const eventStyleGetter = (event: CalendarEvent) => {
    const appointment = event.resource;
    let backgroundColor = '#3b82f6'; // default blue

    switch (appointment.status) {
      case 'pending':
        backgroundColor = '#f59e0b'; // orange
        break;
      case 'confirmed':
        backgroundColor = '#3b82f6'; // blue
        break;
      case 'completed':
        backgroundColor = '#10b981'; // green
        break;
      case 'cancelled':
        backgroundColor = '#ef4444'; // red
        break;
    }

    return {
      style: {
        backgroundColor,
        borderRadius: '4px',
        opacity: 0.8,
        color: 'white',
        border: '0px',
        display: 'block',
      },
    };
  };

  const getStatusBadge = (status: string) => {
    const variants: Record<string, 'success' | 'warning' | 'destructive' | 'info' | 'default'> = {
      pending: 'warning',
      confirmed: 'info',
      completed: 'success',
      cancelled: 'destructive',
    };

    const labels: Record<string, string> = {
      pending: 'Pendiente',
      confirmed: 'Confirmada',
      completed: 'Completada',
      cancelled: 'Cancelada',
    };

    return <Badge variant={variants[status] || 'default'}>{labels[status] || status}</Badge>;
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-foreground">Calendario</h1>
        <Button
          onClick={() => handleSelectSlot({ start: new Date(), end: new Date() })}
          disabled={!canCreateAppointment}
        >
          <Plus className="mr-2 h-4 w-4" />
          Nueva Cita
        </Button>
      </div>

      {/* Legend */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex gap-4 items-center">
            <span className="text-sm font-medium">Leyenda:</span>
            <div className="flex gap-4 flex-wrap">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: '#f59e0b' }}></div>
                <span className="text-xs">Pendiente</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: '#3b82f6' }}></div>
                <span className="text-xs">Confirmada</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: '#10b981' }}></div>
                <span className="text-xs">Completada</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: '#ef4444' }}></div>
                <span className="text-xs">Cancelada</span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Calendar */}
      <Card>
        <CardContent className="pt-6">
          {!canCreateAppointment && events.length === 0 ? (
            <EmptyState
              icon={<CalendarClock className="h-6 w-6" />}
              title="Calendario listo para tus citas"
              description="Completa servicios, horarios y clientes para crear citas manuales. Las citas de Telegram también aparecerán aquí."
            />
          ) : (
            <div className="h-[500px] md:h-[700px]">
              <BigCalendar
                localizer={localizer}
                events={events}
                startAccessor="start"
                endAccessor="end"
                view={view}
                onView={setView}
                date={date}
                onNavigate={setDate}
                onSelectSlot={handleSelectSlot}
                onSelectEvent={handleSelectEvent}
                eventPropGetter={eventStyleGetter}
                selectable
                culture="es"
                messages={{
                  next: 'Sig.',
                  previous: 'Ant.',
                  today: 'Hoy',
                  month: 'Mes',
                  week: 'Sem.',
                  day: 'Día',
                  agenda: 'Ag.',
                  date: 'Fecha',
                  time: 'Hora',
                  event: 'Evento',
                  noEventsInRange: 'Sin citas',
                }}
              />
            </div>
          )}
        </CardContent>
      </Card>

      {/* Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={handleCloseModal}
        title={selectedEvent ? 'Detalles de la Cita' : 'Nueva Cita'}
        size="lg"
      >
        {selectedEvent ? (
          // View appointment details
          <div className="space-y-4">
            <div>
              <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Cliente</label>
              <p className="text-lg font-semibold">{selectedEvent.customer.name}</p>
              <p className="text-sm text-muted-foreground">{formatPhone(selectedEvent.customer.phone)}</p>
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Servicio</label>
              <p className="font-medium">{selectedEvent.service.name}</p>
              <p className="text-sm text-muted-foreground">
                {selectedEvent.service.duration_minutes} min • {formatCurrency(selectedEvent.service.price)}
              </p>
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Fecha y Hora</label>
              <p className="font-medium">
                {format(new Date(selectedEvent.scheduled_at), 'PPPPp', { locale: es })}
              </p>
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Estado</label>
              <div className="mt-1">{getStatusBadge(selectedEvent.status)}</div>
            </div>
            {selectedEvent.notes && (
              <div>
                <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Notas</label>
                <p className="text-sm border-l-2 border-primary/20 pl-3 py-1 italic">{selectedEvent.notes}</p>
              </div>
            )}
            <div className="flex justify-end gap-3 pt-6 border-t border-border/50">
              <Button variant="outline" onClick={handleCloseModal}>
                Cerrar
              </Button>
              {(selectedEvent.status === 'pending' || selectedEvent.status === 'confirmed') && (
                <Button variant="danger" onClick={handleCancel}>
                  Cancelar Cita
                </Button>
              )}
            </div>
          </div>
        ) : (
          // Create new appointment
          <form onSubmit={handleSubmit} className="space-y-4">
            <Select
              label="Cliente"
              value={formData.customer_id}
              onChange={(e) => setFormData({ ...formData, customer_id: e.target.value })}
              options={[
                { value: '', label: 'Seleccionar cliente...' },
                ...customers.map((c) => ({ value: c.id, label: `${c.name} - ${formatPhone(c.phone)}` })),
              ]}
              required
            />
            <div className="rounded-lg border border-border/50 bg-muted/30 p-4 space-y-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-medium text-foreground">Cliente rápido</div>
                  <div className="text-xs text-muted-foreground">
                    Crea un cliente sin salir de esta cita.
                  </div>
                </div>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => setShowQuickCustomer((prev) => !prev)}
                >
                  {showQuickCustomer ? 'Ocultar' : 'Crear cliente'}
                </Button>
              </div>
              {showQuickCustomer && (
                <div className="grid gap-3 md:grid-cols-[1fr_1fr_auto] md:items-end">
                  <Input
                    label="Nombre"
                    value={quickCustomer.name}
                    onChange={(e) => setQuickCustomer({ ...quickCustomer, name: e.target.value })}
                  />
                  <Input
                    label="Teléfono"
                    value={quickCustomer.phone}
                    onChange={(e) => setQuickCustomer({ ...quickCustomer, phone: e.target.value })}
                  />
                  <Button
                    type="button"
                    variant="secondary"
                    isLoading={isLoading}
                    onClick={handleCreateQuickCustomer}
                  >
                    Agregar
                  </Button>
                </div>
              )}
            </div>
            <Select
              label="Servicio"
              value={formData.service_id}
              onChange={(e) => setFormData({ ...formData, service_id: e.target.value })}
              options={[
                { value: '', label: 'Seleccionar servicio...' },
                ...services.map((s) => ({
                  value: s.id,
                  label: `${s.name} - ${s.duration_minutes}min - ${formatCurrency(s.price)}`
                })),
              ]}
              required
            />
            <Input
              label="Fecha y Hora"
              type="datetime-local"
              value={formData.scheduled_at}
              onChange={(e) => setFormData({ ...formData, scheduled_at: e.target.value })}
              required
            />
            <div>
              <label className="block text-sm font-medium mb-1.5">
                Notas (opcional)
              </label>
              <textarea
                value={formData.notes}
                onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                placeholder="Notas adicionales..."
              />
            </div>
            <div className="flex justify-end gap-3 pt-6 border-t border-border/50">
              <Button type="button" variant="outline" onClick={handleCloseModal}>
                Cancelar
              </Button>
              <Button type="submit" isLoading={isLoading}>
                Crear Cita
              </Button>
            </div>
          </form>
        )}
      </Modal>
    </div>
  );
}

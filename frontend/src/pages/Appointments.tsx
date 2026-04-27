import { useState, useEffect } from 'react';
import { Plus, Edit2, Trash2, Search, Calendar as CalendarIcon, Clock, CalendarClock, Users, Scissors } from 'lucide-react';
import { toast } from 'sonner';
import { Button, Input, Modal, Select, Card, CardContent, Table, TableHeader, TableBody, TableRow, TableHead, TableCell, Badge, Skeleton, ConfirmationModal, EmptyState } from '@/components/ui';
import { appointmentsAPI, customersAPI, servicesAPI, scheduleAPI } from '@/services/api';
import { Appointment, AppointmentFormData, Customer, Service, ScheduleRule } from '@/types';
import { formatCurrency, formatPhone } from '@/utils/formatters';
import { format } from 'date-fns';

import { useBusinessStore } from '@/store/businessStore';

export function Appointments() {
  const { currentBusiness } = useBusinessStore();
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [filteredAppointments, setFilteredAppointments] = useState<Appointment[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [services, setServices] = useState<Service[]>([]);
  const [scheduleRules, setScheduleRules] = useState<ScheduleRule[]>([]);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isConfirmModalOpen, setIsConfirmModalOpen] = useState(false);
  const [appointmentToCancel, setAppointmentToCancel] = useState<number | null>(null);
  const [editingAppointment, setEditingAppointment] = useState<Appointment | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
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

  useEffect(() => {
    let filtered = appointments;

    // Filter by search
    if (searchQuery.trim() !== '') {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter((apt) => {
        const customerName = apt.customer?.name ?? '';
        const customerPhone = apt.customer?.phone ?? '';
        const serviceName = apt.service?.name ?? '';
        return (
          customerName.toLowerCase().includes(query) ||
          customerPhone.includes(query) ||
          serviceName.toLowerCase().includes(query)
        );
      });
    }

    // Filter by status
    if (statusFilter !== 'all') {
      filtered = filtered.filter((apt) => apt.status === statusFilter);
    }

    setFilteredAppointments(filtered);
  }, [searchQuery, statusFilter, appointments]);

  const loadData = async () => {
    if (!currentBusiness) return;
    try {
      setIsLoading(true);
      const [appointmentsData, customersData, servicesData, schedulesData] = await Promise.allSettled([
        appointmentsAPI.list(currentBusiness.id),
        customersAPI.list(currentBusiness.id),
        servicesAPI.list(currentBusiness.id),
        scheduleAPI.list(currentBusiness.id),
      ]);

      if (appointmentsData.status === 'fulfilled') {
        const data = appointmentsData.value || [];
        setAppointments(data);
        setFilteredAppointments(data);
      }

      if (customersData.status === 'fulfilled') {
        const data = customersData.value;
        const customerList = Array.isArray(data) ? data : (data as any).results || [];
        setCustomers(customerList);
      }

      if (servicesData.status === 'fulfilled') {
        setServices((servicesData.value || []).filter(s => s.is_active));
      }

      if (schedulesData.status === 'fulfilled') {
        setScheduleRules(schedulesData.value || []);
      }
    } catch (error) {
      console.error('Error loading data:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleOpenModal = (appointment?: Appointment) => {
    if (!appointment && !canCreateAppointment) {
      if (!hasActiveServices) {
        toast.error('Crea al menos un servicio activo antes de registrar citas');
      } else if (!hasAvailableSchedule) {
        toast.error('Configura al menos un día disponible antes de registrar citas');
      } else if (!hasCustomers) {
        toast.error('Crea al menos un cliente antes de registrar citas manuales');
      }
      return;
    }

    if (appointment) {
      setEditingAppointment(appointment);
      setFormData({
        customer_id: appointment.customer.id,
        service_id: appointment.service.id,
        scheduled_at: format(new Date(appointment.scheduled_at), "yyyy-MM-dd'T'HH:mm"),
        notes: appointment.notes || '',
      });
    } else {
      setEditingAppointment(null);
      setFormData({
        customer_id: '',
        service_id: '',
        scheduled_at: '',
        notes: '',
      });
    }
    setIsModalOpen(true);
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
    setEditingAppointment(null);
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
      if (editingAppointment) {
        if (!currentBusiness) return;
        await appointmentsAPI.update(editingAppointment.id, formData, currentBusiness.id);
      } else {
        if (!currentBusiness) return;
        await appointmentsAPI.create({ ...formData, business: currentBusiness.id });
      }
      await loadData();
      toast.success(editingAppointment ? 'Cita actualizada correctamente' : 'Cita creada correctamente');
      handleCloseModal();
    } catch (error) {
      console.error('Error saving appointment:', error);
      toast.error('Error al guardar la cita');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCancelClick = (id: number) => {
    setAppointmentToCancel(id);
    setIsConfirmModalOpen(true);
  };

  const handleConfirmCancel = async () => {
    if (!appointmentToCancel || !currentBusiness) return;
    setIsLoading(true);
    try {
      await appointmentsAPI.cancel(appointmentToCancel, undefined, currentBusiness.id);
      await loadData();
      toast.success('Cita cancelada correctamente');
      setIsConfirmModalOpen(false);
    } catch (error) {
      console.error('Error canceling appointment:', error);
      toast.error('Error al cancelar la cita');
    } finally {
      setIsLoading(false);
      setAppointmentToCancel(null);
    }
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
        <h1 className="text-3xl font-bold text-foreground">Citas</h1>
        <Button onClick={() => handleOpenModal()} disabled={!canCreateAppointment}>
          <Plus className="mr-2 h-4 w-4" />
          Nueva Cita
        </Button>
      </div>

      {!canCreateAppointment && (
        <Card>
          <CardContent className="p-5">
            <div className="grid gap-3 md:grid-cols-3">
              <div className="flex items-center gap-3 text-sm">
                <Scissors className={hasActiveServices ? 'h-5 w-5 text-green-600' : 'h-5 w-5 text-muted-foreground'} />
                <span className={hasActiveServices ? 'text-foreground' : 'text-muted-foreground'}>
                  Servicio activo
                </span>
              </div>
              <div className="flex items-center gap-3 text-sm">
                <CalendarClock className={hasAvailableSchedule ? 'h-5 w-5 text-green-600' : 'h-5 w-5 text-muted-foreground'} />
                <span className={hasAvailableSchedule ? 'text-foreground' : 'text-muted-foreground'}>
                  Horario disponible
                </span>
              </div>
              <div className="flex items-center gap-3 text-sm">
                <Users className={hasCustomers ? 'h-5 w-5 text-green-600' : 'h-5 w-5 text-muted-foreground'} />
                <span className={hasCustomers ? 'text-foreground' : 'text-muted-foreground'}>
                  Cliente registrado
                </span>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Buscar por cliente, teléfono o servicio..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>
            <Select
              className="w-full md:w-48"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              options={[
                { value: 'all', label: 'Todos los estados' },
                { value: 'pending', label: 'Pendientes' },
                { value: 'confirmed', label: 'Confirmadas' },
                { value: 'completed', label: 'Completadas' },
                { value: 'cancelled', label: 'Canceladas' },
              ]}
            />
          </div>
        </CardContent>
      </Card>

      {/* Appointments Table / Cards */}
      <div>
        {/* Table View - Hidden on mobile */}
        <div className="hidden md:block">
          <Card>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="pl-6">Cliente</TableHead>
                      <TableHead>Servicio</TableHead>
                      <TableHead>Fecha y Hora</TableHead>
                      <TableHead>Estado</TableHead>
                      <TableHead>Precio</TableHead>
                      <TableHead className="text-right pr-6">Acciones</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {isLoading ? (
                      [1, 2, 3, 4, 5].map((i) => (
                        <TableRow key={i}>
                          <TableCell className="pl-6"><Skeleton className="h-10 w-32" /></TableCell>
                          <TableCell><Skeleton className="h-10 w-24" /></TableCell>
                          <TableCell><Skeleton className="h-10 w-40" /></TableCell>
                          <TableCell><Skeleton className="h-6 w-20" /></TableCell>
                          <TableCell><Skeleton className="h-6 w-16" /></TableCell>
                          <TableCell className="text-right pr-6"><Skeleton className="h-8 w-16 ml-auto" /></TableCell>
                        </TableRow>
                      ))
                    ) : filteredAppointments.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={6} className="text-center text-muted-foreground py-12">
                          {searchQuery || statusFilter !== 'all' ? (
                            'No se encontraron citas'
                          ) : (
                            <EmptyState
                              icon={<CalendarIcon className="h-6 w-6" />}
                              title="Todavía no hay citas"
                              description="Crea una cita manual cuando tengas cliente, servicio y horario, o comparte tu enlace de Telegram."
                              actionLabel={canCreateAppointment ? 'Nueva cita' : undefined}
                              onAction={canCreateAppointment ? () => handleOpenModal() : undefined}
                            />
                          )}
                        </TableCell>
                      </TableRow>
                    ) : (
                      filteredAppointments.map((appointment) => (
                        <TableRow key={appointment.id} className="hover:bg-muted/30 transition-colors">
                          <TableCell className="pl-6">
                            <div>
                              <div className="font-semibold text-foreground">{appointment.customer?.name || 'Cliente'}</div>
                              <div className="text-xs text-muted-foreground">{formatPhone(appointment.customer?.phone || '')}</div>
                            </div>
                          </TableCell>
                          <TableCell>
                            <div>
                              <div className="font-medium text-foreground">{appointment.service?.name || 'Servicio'}</div>
                              <div className="text-xs text-muted-foreground">{appointment.service?.duration_minutes || 0} min</div>
                            </div>
                          </TableCell>
                          <TableCell>
                            <div className="flex items-center gap-2">
                              <CalendarIcon className="h-3.5 w-3.5 text-primary" />
                              <div>
                                <div className="text-sm font-medium">{format(new Date(appointment.scheduled_at), 'dd/MM/yyyy')}</div>
                                <div className="text-xs text-muted-foreground flex items-center gap-1">
                                  <Clock className="h-3 w-3" />
                                  {format(new Date(appointment.scheduled_at), 'HH:mm')}
                                </div>
                              </div>
                            </div>
                          </TableCell>
                          <TableCell>{getStatusBadge(appointment.status)}</TableCell>
                          <TableCell className="font-semibold text-foreground">{formatCurrency(appointment.service?.price || 0)}</TableCell>
                          <TableCell className="text-right pr-6">
                            <div className="flex justify-end gap-2">
                              {appointment.status === 'pending' && (
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  className="h-8 w-8 p-0"
                                  aria-label="Editar cita"
                                  onClick={() => handleOpenModal(appointment)}
                                >
                                  <Edit2 className="h-4 w-4" />
                                </Button>
                              )}
                              {(appointment.status === 'pending' || appointment.status === 'confirmed') && (
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  className="h-8 w-8 p-0 text-destructive hover:text-destructive hover:bg-destructive/10"
                                  aria-label="Cancelar cita"
                                  onClick={() => handleCancelClick(appointment.id)}
                                >
                                  <Trash2 className="h-4 w-4" />
                                </Button>
                              )}
                            </div>
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Card View - Visible only on mobile */}
        <div className="grid grid-cols-1 gap-4 md:hidden">
          {isLoading ? (
            [1, 2, 3].map((i) => (
              <Card key={i} className="h-48">
                <CardContent className="p-4 space-y-4">
                  <div className="flex justify-between items-start">
                    <div className="space-y-2">
                      <Skeleton className="h-6 w-32" />
                      <Skeleton className="h-4 w-24" />
                    </div>
                    <Skeleton className="h-6 w-20" />
                  </div>
                  <Skeleton className="h-12 w-full" />
                  <Skeleton className="h-10 w-full" />
                </CardContent>
              </Card>
            ))
          ) : filteredAppointments.length === 0 ? (
            <Card>
              <CardContent>
                {searchQuery || statusFilter !== 'all' ? (
                  <div className="py-10 text-center text-muted-foreground">No se encontraron citas</div>
                ) : (
                  <EmptyState
                    icon={<CalendarIcon className="h-6 w-6" />}
                    title="Todavía no hay citas"
                    description="Cuando tus clientes agenden por Telegram o crees citas manuales, aparecerán aquí."
                    actionLabel={canCreateAppointment ? 'Nueva cita' : undefined}
                    onAction={canCreateAppointment ? () => handleOpenModal() : undefined}
                  />
                )}
              </CardContent>
            </Card>
          ) : (
            filteredAppointments.map((appointment) => (
              <Card key={appointment.id} className="overflow-hidden border-l-4 border-l-primary">
                <CardContent className="p-4 space-y-4">
                  <div className="flex justify-between items-start">
                    <div>
                      <div className="font-bold text-lg text-foreground">{appointment.customer?.name || 'Cliente'}</div>
                      <div className="text-sm text-muted-foreground">{formatPhone(appointment.customer?.phone || '')}</div>
                    </div>
                    {getStatusBadge(appointment.status)}
                  </div>

                  <div className="grid grid-cols-2 gap-4 py-3 border-y border-border/40">
                    <div>
                      <div className="text-xs text-muted-foreground uppercase font-semibold">Servicio</div>
                      <div className="text-sm font-medium">{appointment.service?.name}</div>
                      <div className="text-xs text-muted-foreground">{appointment.service?.duration_minutes} min</div>
                    </div>
                    <div className="text-right">
                      <div className="text-xs text-muted-foreground uppercase font-semibold">Precio</div>
                      <div className="text-sm font-bold text-primary">{formatCurrency(appointment.service?.price || 0)}</div>
                    </div>
                  </div>

                  <div className="flex justify-between items-center bg-muted/30 -mx-4 -mb-4 p-4 mt-2">
                    <div className="flex items-center gap-2">
                      <CalendarIcon className="h-4 w-4 text-primary" />
                      <span className="text-sm font-medium">{format(new Date(appointment.scheduled_at), 'dd/MM/yyyy')} a las {format(new Date(appointment.scheduled_at), 'HH:mm')}</span>
                    </div>
                    <div className="flex gap-2">
                      {appointment.status === 'pending' && (
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-8 w-8 p-0"
                          onClick={() => handleOpenModal(appointment)}
                        >
                          <Edit2 className="h-4 w-4" />
                        </Button>
                      )}
                      {(appointment.status === 'pending' || appointment.status === 'confirmed') && (
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-8 w-8 p-0 text-destructive hover:bg-destructive/5"
                          onClick={() => handleCancelClick(appointment.id)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))
          )}
        </div>
      </div>

      {/* Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={handleCloseModal}
        title={editingAppointment ? 'Editar Cita' : 'Nueva Cita'}
        size="lg"
      >
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
          {!editingAppointment && (
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
          )}
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
            <label className="block text-sm font-medium text-foreground mb-1.5">
              Notas (opcional)
            </label>
            <textarea
              value={formData.notes}
              onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
              className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              placeholder="Notas adicionales sobre la cita..."
            />
          </div>
          <div className="flex justify-end gap-3 pt-6 border-t border-border/50">
            <Button type="button" variant="outline" onClick={handleCloseModal}>
              Cancelar
            </Button>
            <Button type="submit" isLoading={isLoading}>
              {editingAppointment ? 'Actualizar' : 'Crear'}
            </Button>
          </div>
        </form>
      </Modal>

      <ConfirmationModal
        isOpen={isConfirmModalOpen}
        onClose={() => setIsConfirmModalOpen(false)}
        onConfirm={handleConfirmCancel}
        title="Cancelar Cita"
        message="¿Estás seguro de que deseas cancelar esta cita? Esta acción no se puede deshacer."
        confirmText="Sí, cancelar cita"
        cancelText="No, mantener"
        isLoading={isLoading}
      />
    </div>
  );
}

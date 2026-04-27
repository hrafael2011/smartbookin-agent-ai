import { useState, useEffect } from 'react';
import { Plus, Edit2, Trash2, Scissors } from 'lucide-react';
import { toast } from 'sonner';
import { Button, Input, Modal, Card, CardContent, Table, TableHeader, TableBody, TableRow, TableHead, TableCell, Badge, Skeleton, ConfirmationModal, EmptyState } from '@/components/ui';
import { servicesAPI } from '@/services/api';
import { useBusinessStore } from '@/store/businessStore';
import { Service, ServiceFormData } from '@/types';
import { formatCurrency } from '@/utils/formatters';

export function Services() {
  const { currentBusiness } = useBusinessStore();
  const [services, setServices] = useState<Service[]>([]);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isConfirmModalOpen, setIsConfirmModalOpen] = useState(false);
  const [serviceToDelete, setServiceToDelete] = useState<number | null>(null);
  const [editingService, setEditingService] = useState<Service | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [formData, setFormData] = useState<ServiceFormData>({
    name: '',
    description: '',
    duration_minutes: 30,
    price: 0,
    is_active: true,
  });

  useEffect(() => {
    if (currentBusiness) {
      loadServices();
    }
  }, [currentBusiness]);

  const loadServices = async () => {
    if (!currentBusiness) return;
    try {
      const data = await servicesAPI.list(currentBusiness.id);
      setServices(data);
    } catch (error) {
      console.error('Error loading services:', error);
    }
  };

  const handleOpenModal = (service?: Service) => {
    if (service) {
      setEditingService(service);
      setFormData({
        name: service.name,
        description: service.description || '',
        duration_minutes: service.duration_minutes,
        price: service.price,
        is_active: service.is_active,
      });
    } else {
      setEditingService(null);
      setFormData({
        name: '',
        description: '',
        duration_minutes: 30,
        price: 0,
        is_active: true,
      });
    }
    setIsModalOpen(true);
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
    setEditingService(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      if (!formData.name.trim()) {
        toast.error('El nombre del servicio es obligatorio');
        return;
      }
      if (Number(formData.duration_minutes) <= 0) {
        toast.error('La duración debe ser mayor a cero');
        return;
      }
      if (Number(formData.price) < 0) {
        toast.error('El precio no puede ser negativo');
        return;
      }

      if (editingService) {
        if (!currentBusiness) return;
        await servicesAPI.update(editingService.id, formData, currentBusiness.id);
      } else {
        if (!currentBusiness) return;
        await servicesAPI.create({ ...formData, business: currentBusiness.id });
      }
      await loadServices();
      toast.success(editingService ? 'Servicio actualizado correctamente' : 'Servicio creado correctamente');
      handleCloseModal();
    } catch (error) {
      console.error('Error saving service:', error);
      toast.error('Error al guardar el servicio');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeleteClick = (id: number) => {
    setServiceToDelete(id);
    setIsConfirmModalOpen(true);
  };

  const handleConfirmDelete = async () => {
    if (!serviceToDelete || !currentBusiness) return;
    setIsLoading(true);
    try {
      await servicesAPI.delete(serviceToDelete, currentBusiness.id);
      await loadServices();
      toast.success('Servicio eliminado correctamente');
      setIsConfirmModalOpen(false);
    } catch (error) {
      console.error('Error deleting service:', error);
      toast.error('Error al eliminar el servicio');
    } finally {
      setIsLoading(false);
      setServiceToDelete(null);
    }
  };

  const handleToggleActive = async (service: Service) => {
    if (!currentBusiness) return;
    try {
      await servicesAPI.update(service.id, { is_active: !service.is_active }, currentBusiness.id);
      await loadServices();
      toast.success(`Servicio ${!service.is_active ? 'activado' : 'desactivado'} correctamente`);
    } catch (error) {
      console.error('Error toggling service:', error);
      toast.error('Error al cambiar el estado del servicio');
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-foreground">Servicios</h1>
        <Button onClick={() => handleOpenModal()}>
          <Plus className="mr-2 h-4 w-4" />
          Nuevo Servicio
        </Button>
      </div>

      {/* Services Table / Cards */}
      <div>
        {/* Table View - Hidden on mobile */}
        <div className="hidden md:block">
          <Card>
            <CardContent className="pt-6">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Nombre</TableHead>
                    <TableHead>Descripción</TableHead>
                    <TableHead>Duración</TableHead>
                    <TableHead>Precio</TableHead>
                    <TableHead>Estado</TableHead>
                    <TableHead className="text-right">Acciones</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {isLoading ? (
                    [1, 2, 3, 4].map((i) => (
                      <TableRow key={i}>
                        <TableCell><Skeleton className="h-10 w-32" /></TableCell>
                        <TableCell><Skeleton className="h-10 w-40" /></TableCell>
                        <TableCell><Skeleton className="h-10 w-20" /></TableCell>
                        <TableCell><Skeleton className="h-10 w-24" /></TableCell>
                        <TableCell><Skeleton className="h-6 w-16" /></TableCell>
                        <TableCell className="text-right"><Skeleton className="h-8 w-16 ml-auto" /></TableCell>
                      </TableRow>
                    ))
                  ) : services.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
                        <EmptyState
                          icon={<Scissors className="h-6 w-6" />}
                          title="Crea tu primer servicio"
                          description="Los servicios son lo que tus clientes podrán reservar por Telegram o desde el panel."
                          actionLabel="Nuevo servicio"
                          onAction={() => handleOpenModal()}
                        />
                      </TableCell>
                    </TableRow>
                  ) : (
                    services.map((service) => (
                      <TableRow key={service.id}>
                        <TableCell className="font-medium">{service.name}</TableCell>
                        <TableCell className="text-muted-foreground">{service.description || '-'}</TableCell>
                        <TableCell>{service.duration_minutes} min</TableCell>
                        <TableCell>{formatCurrency(service.price)}</TableCell>
                        <TableCell>
                          <Badge variant={service.is_active ? 'success' : 'default'}>
                            {service.is_active ? 'Activo' : 'Inactivo'}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-2">
                            <Button
                              size="sm"
                              variant="ghost"
                              aria-label="Editar servicio"
                              onClick={() => handleOpenModal(service)}
                            >
                              <Edit2 className="h-4 w-4" />
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => handleToggleActive(service)}
                            >
                              {service.is_active ? 'Desactivar' : 'Activar'}
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              aria-label="Eliminar servicio"
                              onClick={() => handleDeleteClick(service.id)}
                            >
                              <Trash2 className="h-4 w-4 text-destructive" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
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
                      <Skeleton className="h-4 w-40" />
                    </div>
                    <Skeleton className="h-6 w-16" />
                  </div>
                  <Skeleton className="h-12 w-full" />
                  <Skeleton className="h-10 w-full" />
                </CardContent>
              </Card>
            ))
          ) : services.length === 0 ? (
            <Card>
              <CardContent>
                <EmptyState
                  icon={<Scissors className="h-6 w-6" />}
                  title="Crea tu primer servicio"
                  description="Agrega duración y precio para que el sistema pueda organizar las citas."
                  actionLabel="Nuevo servicio"
                  onAction={() => handleOpenModal()}
                />
              </CardContent>
            </Card>
          ) : (
            services.map((service) => (
              <Card key={service.id} className={`overflow-hidden border-l-4 ${service.is_active ? 'border-l-primary' : 'border-l-muted-foreground'}`}>
                <CardContent className="p-4 space-y-4">
                  <div className="flex justify-between items-start">
                    <div>
                      <div className="font-bold text-lg text-foreground">{service.name}</div>
                      <div className="text-sm text-muted-foreground">{service.description || 'Sin descripción'}</div>
                    </div>
                    <Badge variant={service.is_active ? 'success' : 'default'}>
                      {service.is_active ? 'Activo' : 'Inactivo'}
                    </Badge>
                  </div>

                  <div className="grid grid-cols-2 gap-4 py-3 border-y border-border/40">
                    <div>
                      <div className="text-xs text-muted-foreground uppercase font-semibold">Duración</div>
                      <div className="text-sm font-medium">{service.duration_minutes} min</div>
                    </div>
                    <div className="text-right">
                      <div className="text-xs text-muted-foreground uppercase font-semibold">Precio</div>
                      <div className="text-sm font-bold text-primary">{formatCurrency(service.price)}</div>
                    </div>
                  </div>

                  <div className="flex justify-end gap-2 pt-2">
                    <Button
                      size="sm"
                      variant="outline"
                      className="flex-1"
                      onClick={() => handleOpenModal(service)}
                    >
                      <Edit2 className="h-4 w-4 mr-2" />
                      Editar
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="flex-1"
                      onClick={() => handleToggleActive(service)}
                    >
                      {service.is_active ? 'Desactivar' : 'Activar'}
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="text-destructive border-destructive/20 hover:bg-destructive/5"
                      onClick={() => handleDeleteClick(service.id)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
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
        title={editingService ? 'Editar Servicio' : 'Nuevo Servicio'}
      >
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="Nombre del servicio"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            required
          />
          <Input
            label="Descripción"
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
          />
          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Duración (minutos)"
              type="number"
              min="5"
              step="5"
              value={formData.duration_minutes}
              onChange={(e) => setFormData({ ...formData, duration_minutes: Number(e.target.value) })}
              required
            />
            <Input
              label="Precio (RD$)"
              type="number"
              min="0"
              step="0.01"
              value={formData.price}
              onChange={(e) => setFormData({ ...formData, price: Number(e.target.value) })}
              required
            />
          </div>
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="is_active"
              checked={formData.is_active}
              onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
              className="h-4 w-4 rounded border-gray-300"
            />
            <label htmlFor="is_active" className="text-sm font-medium text-foreground">
              Servicio activo
            </label>
          </div>
          <div className="flex justify-end gap-3 pt-4">
            <Button type="button" variant="outline" onClick={handleCloseModal}>
              Cancelar
            </Button>
            <Button type="submit" isLoading={isLoading}>
              {editingService ? 'Actualizar' : 'Crear'}
            </Button>
          </div>
        </form>
      </Modal>

      <ConfirmationModal
        isOpen={isConfirmModalOpen}
        onClose={() => setIsConfirmModalOpen(false)}
        onConfirm={handleConfirmDelete}
        title="Eliminar Servicio"
        message="¿Estás seguro de que deseas eliminar este servicio? Esto podría afectar a las citas futuras programadas con este servicio."
        confirmText="Sí, eliminar servicio"
        cancelText="No, cancelar"
        isLoading={isLoading}
      />
    </div>
  );
}

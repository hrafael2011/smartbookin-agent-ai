import { useState, useEffect } from 'react';
import { Plus, Edit2, Trash2, Search, Phone, Mail, Users } from 'lucide-react';
import { toast } from 'sonner';
import { customersAPI } from '@/services/api';
import { useBusinessStore } from '@/store/businessStore';
import { Customer, CustomerFormData } from '@/types';
import { formatPhone } from '@/utils/formatters';
import { Button, Input, Modal, Card, CardContent, Table, TableHeader, TableBody, TableRow, TableHead, TableCell, Skeleton, ConfirmationModal, EmptyState } from '@/components/ui';

export function Customers() {
  const { currentBusiness } = useBusinessStore();
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [filteredCustomers, setFilteredCustomers] = useState<Customer[]>([]);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isConfirmModalOpen, setIsConfirmModalOpen] = useState(false);
  const [customerToDelete, setCustomerToDelete] = useState<number | null>(null);
  const [editingCustomer, setEditingCustomer] = useState<Customer | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [formData, setFormData] = useState<CustomerFormData>({
    name: '',
    phone: '',
    email: '',
    is_active: true,
  });

  useEffect(() => {
    if (currentBusiness) {
      loadCustomers();
    }
  }, [currentBusiness]);

  useEffect(() => {
    if (searchQuery.trim() === '') {
      setFilteredCustomers(customers);
    } else {
      const query = searchQuery.toLowerCase();
      setFilteredCustomers(
        customers.filter(
          (customer) =>
            customer.name.toLowerCase().includes(query) ||
            customer.phone.includes(query) ||
            (customer.email && customer.email.toLowerCase().includes(query))
        )
      );
    }
  }, [searchQuery, customers]);

  const loadCustomers = async () => {
    if (!currentBusiness) return;
    try {
      const data = await customersAPI.list(currentBusiness.id);
      setCustomers(data.results || data);
      setFilteredCustomers(data.results || data);
    } catch (error) {
      console.error('Error loading customers:', error);
    }
  };

  const handleOpenModal = (customer?: Customer) => {
    if (customer) {
      setEditingCustomer(customer);
      setFormData({
        name: customer.name,
        phone: customer.phone,
        email: customer.email || '',
        is_active: customer.is_active,
      });
    } else {
      setEditingCustomer(null);
      setFormData({
        name: '',
        phone: '',
        email: '',
        is_active: true,
      });
    }
    setIsModalOpen(true);
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
    setEditingCustomer(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      if (!formData.name.trim()) {
        toast.error('El nombre del cliente es obligatorio');
        return;
      }
      if (!formData.phone.trim()) {
        toast.error('El teléfono del cliente es obligatorio');
        return;
      }

      if (editingCustomer) {
        if (!currentBusiness) return;
        await customersAPI.update(editingCustomer.id, formData, currentBusiness.id);
      } else {
        if (!currentBusiness) return;
        await customersAPI.create({ ...formData, business: currentBusiness.id });
      }
      await loadCustomers();
      toast.success(editingCustomer ? 'Cliente actualizado correctamente' : 'Cliente creado correctamente');
      handleCloseModal();
    } catch (error) {
      console.error('Error saving customer:', error);
      toast.error('Error al guardar el cliente');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeleteClick = (id: number) => {
    setCustomerToDelete(id);
    setIsConfirmModalOpen(true);
  };

  const handleConfirmDelete = async () => {
    if (!customerToDelete || !currentBusiness) return;
    setIsLoading(true);
    try {
      await customersAPI.delete(customerToDelete, currentBusiness.id);
      await loadCustomers();
      toast.success('Cliente eliminado correctamente');
      setIsConfirmModalOpen(false);
    } catch (error) {
      console.error('Error deleting customer:', error);
      toast.error('Error al eliminar el cliente');
    } finally {
      setIsLoading(false);
      setCustomerToDelete(null);
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-foreground">Clientes</h1>
        <Button onClick={() => handleOpenModal()}>
          <Plus className="mr-2 h-4 w-4" />
          Nuevo Cliente
        </Button>
      </div>

      {/* Search Bar */}
      <Card>
        <CardContent className="pt-6">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Buscar por nombre, teléfono o email..."
              value={searchQuery}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSearchQuery(e.target.value)}
              className="pl-10"
            />
          </div>
        </CardContent>
      </Card>

      {/* Customers Table / Cards */}
      <div>
        {/* Table View - Hidden on mobile */}
        <div className="hidden md:block">
          <Card>
            <CardContent className="pt-6">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Nombre</TableHead>
                    <TableHead>Teléfono</TableHead>
                    <TableHead>Email</TableHead>
                    <TableHead>Registrado</TableHead>
                    <TableHead className="text-right">Acciones</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {isLoading ? (
                    [1, 2, 3, 4, 5].map((i) => (
                      <TableRow key={i}>
                        <TableCell className="pl-6"><Skeleton className="h-10 w-32" /></TableCell>
                        <TableCell><Skeleton className="h-10 w-24" /></TableCell>
                        <TableCell><Skeleton className="h-10 w-40" /></TableCell>
                        <TableCell className="text-right pr-6"><Skeleton className="h-8 w-16 ml-auto" /></TableCell>
                      </TableRow>
                    ))
                  ) : filteredCustomers.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={5} className="text-center text-muted-foreground py-8">
                        {searchQuery ? (
                          'No se encontraron clientes'
                        ) : (
                          <EmptyState
                            icon={<Users className="h-6 w-6" />}
                            title="Aún no tienes clientes"
                            description="Puedes crearlos manualmente o dejar que aparezcan cuando un cliente escriba por Telegram."
                            actionLabel="Nuevo cliente"
                            onAction={() => handleOpenModal()}
                          />
                        )}
                      </TableCell>
                    </TableRow>
                  ) : (
                    filteredCustomers.map((customer) => (
                      <TableRow key={customer.id}>
                        <TableCell className="font-medium">{customer.name}</TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <Phone className="h-4 w-4 text-muted-foreground" />
                            {formatPhone(customer.phone)}
                          </div>
                        </TableCell>
                        <TableCell>
                          {customer.email ? (
                            <div className="flex items-center gap-2">
                              <Mail className="h-4 w-4 text-muted-foreground" />
                              {customer.email}
                            </div>
                          ) : (
                            <span className="text-muted-foreground">-</span>
                          )}
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {new Date(customer.created_at).toLocaleDateString('es-DO')}
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-2">
                            <Button
                              size="sm"
                              variant="ghost"
                              aria-label="Editar cliente"
                              onClick={() => handleOpenModal(customer)}
                            >
                              <Edit2 className="h-4 w-4" />
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              aria-label="Eliminar cliente"
                              onClick={() => handleDeleteClick(customer.id)}
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
              <Card key={i} className="h-40">
                <CardContent className="p-4 space-y-4">
                  <div className="flex justify-between items-start">
                    <div className="space-y-2">
                      <Skeleton className="h-6 w-32" />
                      <Skeleton className="h-4 w-24" />
                    </div>
                    <Skeleton className="h-8 w-8 rounded-full" />
                  </div>
                  <Skeleton className="h-10 w-full" />
                </CardContent>
              </Card>
            ))
          ) : filteredCustomers.length === 0 ? (
            <Card>
              <CardContent>
                {searchQuery ? (
                  <div className="py-8 text-center text-muted-foreground">No se encontraron clientes</div>
                ) : (
                  <EmptyState
                    icon={<Users className="h-6 w-6" />}
                    title="Aún no tienes clientes"
                    description="Registra un cliente manualmente para crear citas desde el panel."
                    actionLabel="Nuevo cliente"
                    onAction={() => handleOpenModal()}
                  />
                )}
              </CardContent>
            </Card>
          ) : (
            filteredCustomers.map((customer) => (
              <Card key={customer.id} className="overflow-hidden border-l-4 border-l-primary/50">
                <CardContent className="p-4 space-y-3">
                  <div className="flex justify-between items-start">
                    <div>
                      <div className="font-bold text-lg text-foreground">{customer.name}</div>
                      <div className="text-xs text-muted-foreground">Registrado: {new Date(customer.created_at).toLocaleDateString('es-DO')}</div>
                    </div>
                    <div className="flex gap-1">
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-8 w-8 p-0"
                        onClick={() => handleOpenModal(customer)}
                      >
                        <Edit2 className="h-4 w-4" />
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-8 w-8 p-0 text-destructive"
                        onClick={() => handleDeleteClick(customer.id)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>

                  <div className="space-y-2 pt-2 border-t border-border/40">
                    <div className="flex items-center gap-3 text-sm">
                      <div className="p-1.5 bg-primary/10 rounded-md">
                        <Phone className="h-3.5 w-3.5 text-primary" />
                      </div>
                      <span className="font-medium">{formatPhone(customer.phone)}</span>
                    </div>
                    {customer.email && (
                      <div className="flex items-center gap-3 text-sm text-muted-foreground">
                        <div className="p-1.5 bg-muted rounded-md">
                          <Mail className="h-3.5 w-3.5" />
                        </div>
                        <span className="truncate">{customer.email}</span>
                      </div>
                    )}
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
        title={editingCustomer ? 'Editar Cliente' : 'Nuevo Cliente'}
      >
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="Nombre completo"
            value={formData.name}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData({ ...formData, name: e.target.value })}
            required
          />
          <Input
            label="Teléfono"
            type="tel"
            placeholder="+1 809 555 1234"
            value={formData.phone}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData({ ...formData, phone: e.target.value })}
            required
          />
          <Input
            label="Email (opcional)"
            type="email"
            value={formData.email}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData({ ...formData, email: e.target.value })}
          />
          <div className="flex justify-end gap-3 pt-4">
            <Button type="button" variant="outline" onClick={handleCloseModal}>
              Cancelar
            </Button>
            <Button type="submit" isLoading={isLoading}>
              {editingCustomer ? 'Actualizar' : 'Crear'}
            </Button>
          </div>
        </form>
      </Modal>

      <ConfirmationModal
        isOpen={isConfirmModalOpen}
        onClose={() => setIsConfirmModalOpen(false)}
        onConfirm={handleConfirmDelete}
        title="Eliminar Cliente"
        message="¿Estás seguro de que deseas eliminar este cliente? Esta acción no se puede deshacer y eliminará todo su historial."
        confirmText="Sí, eliminar cliente"
        cancelText="No, cancelar"
        isLoading={isLoading}
      />
    </div>
  );
}

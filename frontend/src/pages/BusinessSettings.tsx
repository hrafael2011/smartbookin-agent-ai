import { useEffect, useState } from 'react'
import { Building2, Save } from 'lucide-react'
import { toast } from 'sonner'
import { Button, Card, CardContent, CardHeader, CardTitle, EmptyState, Input, Select } from '@/components/ui'
import { useBusinessStore } from '@/store/businessStore'

const categoryOptions = [
  { value: 'barbershop', label: 'Barbería' },
  { value: 'beauty_salon', label: 'Salón de belleza' },
  { value: 'medical', label: 'Consulta médica' },
  { value: 'dental', label: 'Clínica dental' },
  { value: 'professional', label: 'Servicio profesional' },
  { value: 'other', label: 'Otro' },
]

export default function BusinessSettings() {
  const { currentBusiness, updateBusiness } = useBusinessStore()
  const [isSaving, setIsSaving] = useState(false)
  const [formData, setFormData] = useState({
    name: '',
    phone: '',
    category: 'barbershop',
    description: '',
    address: '',
  })

  useEffect(() => {
    if (!currentBusiness) return
    setFormData({
      name: currentBusiness.name || '',
      phone: currentBusiness.phone || '',
      category: currentBusiness.category || 'barbershop',
      description: currentBusiness.description || '',
      address: currentBusiness.address || '',
    })
  }, [currentBusiness])

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!currentBusiness) return

    if (!formData.name.trim()) {
      toast.error('El nombre del negocio es obligatorio')
      return
    }

    setIsSaving(true)
    try {
      await updateBusiness(currentBusiness.id, {
        name: formData.name.trim(),
        phone: formData.phone.trim(),
        category: formData.category,
        description: formData.description.trim() || undefined,
        address: formData.address.trim() || undefined,
      })
      toast.success('Negocio actualizado correctamente')
    } catch (error) {
      console.error('Error updating business:', error)
      toast.error('No se pudo actualizar el negocio')
    } finally {
      setIsSaving(false)
    }
  }

  if (!currentBusiness) {
    return (
      <div className="p-6 max-w-2xl">
        <EmptyState
          icon={<Building2 className="h-6 w-6" />}
          title="Crea un negocio primero"
          description="Cuando tengas un negocio activo, podrás editar sus datos desde aquí."
        />
      </div>
    )
  }

  return (
    <div className="p-6 max-w-3xl space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-foreground">Configuración</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Actualiza la información principal que verán tus clientes.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Building2 className="h-5 w-5 text-primary" />
            Datos del negocio
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="grid gap-4 md:grid-cols-2">
              <Input
                label="Nombre"
                value={formData.name}
                onChange={(event) => setFormData({ ...formData, name: event.target.value })}
                placeholder="Nombre del negocio"
              />
              <Input
                label="Teléfono"
                value={formData.phone}
                onChange={(event) => setFormData({ ...formData, phone: event.target.value })}
                placeholder="+1 809 000 0000"
              />
            </div>

            <Select
              label="Categoría"
              value={formData.category}
              onChange={(event) => setFormData({ ...formData, category: event.target.value })}
              options={categoryOptions}
            />

            <div>
              <label className="block text-sm font-semibold text-foreground mb-2">
                Dirección
              </label>
              <textarea
                value={formData.address}
                onChange={(event) => setFormData({ ...formData, address: event.target.value })}
                rows={2}
                className="w-full rounded-lg border-2 border-input bg-background px-4 py-3 text-sm transition-all duration-200 placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/20 focus-visible:border-primary hover:border-primary/40"
                placeholder="Dirección física o referencia"
              />
            </div>

            <div>
              <label className="block text-sm font-semibold text-foreground mb-2">
                Descripción
              </label>
              <textarea
                value={formData.description}
                onChange={(event) => setFormData({ ...formData, description: event.target.value })}
                rows={4}
                className="w-full rounded-lg border-2 border-input bg-background px-4 py-3 text-sm transition-all duration-200 placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/20 focus-visible:border-primary hover:border-primary/40"
                placeholder="Breve descripción para orientar al asistente y a tus clientes"
              />
            </div>

            <div className="flex justify-end">
              <Button type="submit" isLoading={isSaving}>
                <Save className="h-4 w-4" />
                Guardar cambios
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}

/**
 * Registro de dueño (fase prueba; verificación de email según backend)
 */
import { useState, FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { useBusinessStore } from '@/store/businessStore'
import { authAPI } from '@/services/api'
import { UserPlus, Loader2 } from 'lucide-react'
import { toast } from 'sonner'

export default function Register() {
  const navigate = useNavigate()
  const { fetchBusinesses } = useBusinessStore()
  const setUser = useAuthStore((s) => s.setUser)

  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [form, setForm] = useState({
    name: '',
    email: '',
    password: '',
    phone: '',
  })

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setIsLoading(true)
    try {
      const res = await authAPI.register({
        name: form.name.trim(),
        email: form.email.trim(),
        password: form.password,
        phone: form.phone.trim() || undefined,
      })

      if (res.access_token && res.refresh && res.user) {
        localStorage.setItem('access_token', res.access_token)
        localStorage.setItem('refresh_token', res.refresh)
        setUser(res.user)
        toast.success(res.message)
        await fetchBusinesses()
        navigate('/dashboard')
        return
      }

      toast.message(res.message)
      navigate('/login', {
        state: { registeredEmail: form.email.trim() },
      })
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || 'No se pudo registrar'
      setError(typeof msg === 'string' ? msg : 'Error de registro')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 via-indigo-50 to-violet-50 px-4 py-8">
      <div className="max-w-md w-full space-y-6 relative z-10">
        <div className="text-center">
          <h2 className="text-3xl font-bold text-foreground">Crear cuenta</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Registro para dueños de negocio (prueba)
          </p>
        </div>

        <div className="bg-card/80 backdrop-blur-lg rounded-2xl shadow-xl border border-border/50 p-8">
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="bg-destructive/10 border border-destructive/40 text-destructive text-sm px-3 py-2 rounded-lg">
                {error}
              </div>
            )}
            <div>
              <label htmlFor="name" className="block text-sm font-medium mb-1">
                Nombre
              </label>
              <input
                id="name"
                required
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="flex h-10 w-full rounded-lg border border-input bg-background px-3 text-sm"
              />
            </div>
            <div>
              <label htmlFor="email" className="block text-sm font-medium mb-1">
                Correo
              </label>
              <input
                id="email"
                type="email"
                required
                autoComplete="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                className="flex h-10 w-full rounded-lg border border-input bg-background px-3 text-sm"
              />
            </div>
            <div>
              <label htmlFor="phone" className="block text-sm font-medium mb-1">
                Teléfono (opcional)
              </label>
              <input
                id="phone"
                value={form.phone}
                onChange={(e) => setForm({ ...form, phone: e.target.value })}
                className="flex h-10 w-full rounded-lg border border-input bg-background px-3 text-sm"
              />
            </div>
            <div>
              <label htmlFor="password" className="block text-sm font-medium mb-1">
                Contraseña
              </label>
              <input
                id="password"
                type="password"
                required
                minLength={6}
                autoComplete="new-password"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                className="flex h-10 w-full rounded-lg border border-input bg-background px-3 text-sm"
              />
            </div>
            <button
              type="submit"
              disabled={isLoading}
              className="w-full h-11 rounded-lg bg-primary text-primary-foreground font-medium inline-flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {isLoading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <UserPlus className="w-5 h-5" />
              )}
              Registrarme
            </button>
          </form>
          <p className="mt-6 text-center text-sm text-muted-foreground">
            ¿Ya tenés cuenta?{' '}
            <Link to="/login" className="text-primary font-medium hover:underline">
              Iniciar sesión
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}

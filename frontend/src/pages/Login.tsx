/**
 * Login Page - Modern Authentication Design 2025 v2
 */
import { useState, FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { useBusinessStore } from '@/store/businessStore'
import { LogIn, Loader2, Sparkles } from 'lucide-react'

export default function Login() {
  const navigate = useNavigate()
  const location = useLocation()
  const registeredEmail = (location.state as { registeredEmail?: string } | null)
    ?.registeredEmail
  const { login, isLoading, error } = useAuthStore()
  const { fetchBusinesses } = useBusinessStore()

  const [credentials, setCredentials] = useState({
    email: '',
    password: '',
  })

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()

    try {
      await login(credentials)
      // Load businesses after successful login
      await fetchBusinesses()
      navigate('/dashboard')
    } catch (error) {
      // Error is handled by the store
      console.error('Login failed:', error)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 via-indigo-50 to-violet-50 px-4 py-8">
      {/* Background Decoration */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 -left-4 w-72 h-72 bg-primary/10 rounded-full mix-blend-multiply filter blur-xl animate-blob"></div>
        <div className="absolute top-0 -right-4 w-72 h-72 bg-secondary/10 rounded-full mix-blend-multiply filter blur-xl animate-blob animation-delay-2000"></div>
        <div className="absolute -bottom-8 left-20 w-72 h-72 bg-accent/10 rounded-full mix-blend-multiply filter blur-xl animate-blob animation-delay-4000"></div>
      </div>

      <div className="max-w-md w-full space-y-8 relative z-10">
        {/* Header */}
        <div className="text-center">
          <div className="flex justify-center mb-6">
            <div className="relative">
              <div className="w-20 h-20 bg-gradient-to-br from-primary to-secondary rounded-2xl flex items-center justify-center shadow-lg transform transition-transform hover:scale-105">
                <Sparkles className="w-10 h-10 text-white" />
              </div>
              <div className="absolute -top-1 -right-1 w-6 h-6 bg-accent rounded-full border-4 border-white animate-pulse"></div>
            </div>
          </div>
          <h2 className="text-4xl font-bold text-foreground bg-clip-text">
            SmartBooking AI
          </h2>
          <p className="mt-3 text-base text-muted-foreground font-medium">
            Sistema de agendamiento inteligente
          </p>
        </div>

        {/* Login Form Card */}
        <div className="bg-card/80 backdrop-blur-lg rounded-2xl shadow-2xl border border-border/50 overflow-hidden">
          <form onSubmit={handleSubmit} className="p-8 space-y-6">
            {/* Error Message */}
            {registeredEmail && (
              <div className="bg-primary/10 border border-primary/30 text-foreground px-4 py-3 rounded-lg text-sm">
                Cuenta creada para <span className="font-mono">{registeredEmail}</span>. Si el
                servidor exige verificación, revisá tu correo o pedí un nuevo enlace al
                administrador.
              </div>
            )}

            {error && (
              <div className="bg-destructive/10 border-2 border-destructive/50 text-destructive px-4 py-3 rounded-lg flex items-start gap-3 animate-in fade-in slide-in-from-top-2">
                <svg className="w-5 h-5 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd"/>
                </svg>
                <span className="text-sm font-semibold">{error}</span>
              </div>
            )}

            {/* Email Field */}
            <div>
              <label
                htmlFor="email"
                className="block text-sm font-semibold text-foreground mb-2"
              >
                Correo electrónico
              </label>
              <input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                required
                value={credentials.email}
                onChange={(e) =>
                  setCredentials({ ...credentials, email: e.target.value })
                }
                className="flex h-11 w-full rounded-lg border-2 border-input bg-background px-4 py-2 text-sm transition-all duration-200 placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/20 focus-visible:border-primary hover:border-primary/40"
                placeholder="tu@email.com"
              />
            </div>

            {/* Password Field */}
            <div>
              <label
                htmlFor="password"
                className="block text-sm font-semibold text-foreground mb-2"
              >
                Contraseña
              </label>
              <input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                required
                value={credentials.password}
                onChange={(e) =>
                  setCredentials({ ...credentials, password: e.target.value })
                }
                className="flex h-11 w-full rounded-lg border-2 border-input bg-background px-4 py-2 text-sm transition-all duration-200 placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/20 focus-visible:border-primary hover:border-primary/40"
                placeholder="••••••••"
              />
            </div>

            {/* Submit Button */}
            <div>
              <button
                type="submit"
                disabled={isLoading}
                className="w-full inline-flex items-center justify-center gap-2 rounded-lg font-semibold transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 shadow-sm h-12 px-6 text-base bg-primary text-primary-foreground hover:bg-primary/90 hover:shadow-md active:scale-[0.98]"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    Iniciando sesión...
                  </>
                ) : (
                  <>
                    <LogIn className="w-5 h-5" />
                    Iniciar sesión
                  </>
                )}
              </button>
            </div>

            <p className="text-center text-sm text-muted-foreground">
              ¿No tenés cuenta?{' '}
              <Link to="/register" className="text-primary font-semibold hover:underline">
                Registrate
              </Link>
            </p>
          </form>

          {/* Demo Credentials */}
          <div className="px-8 py-6 bg-muted/30 border-t border-border/50">
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="font-medium">Demo:</span>
              <span className="font-mono bg-background px-2 py-0.5 rounded">admin@smartbooking.com</span>
              <span>/</span>
              <span className="font-mono bg-background px-2 py-0.5 rounded">admin123</span>
            </div>
          </div>
        </div>

        {/* Footer */}
        <p className="text-center text-sm text-muted-foreground">
          &copy; 2025 SmartBooking AI. Todos los derechos reservados.
          <br />
          <span className="text-xs opacity-50">Build: {new Date().toISOString()}</span>
        </p>
      </div>

      <style>{`
        @keyframes blob {
          0%, 100% { transform: translate(0, 0) scale(1); }
          33% { transform: translate(30px, -50px) scale(1.1); }
          66% { transform: translate(-20px, 20px) scale(0.9); }
        }
        .animate-blob {
          animation: blob 7s infinite;
        }
        .animation-delay-2000 {
          animation-delay: 2s;
        }
        .animation-delay-4000 {
          animation-delay: 4s;
        }
      `}</style>
    </div>
  )
}

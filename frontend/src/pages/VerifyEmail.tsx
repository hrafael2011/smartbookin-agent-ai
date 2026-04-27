/**
 * Verificación de correo (token en query ?token=)
 */
import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { authAPI } from '@/services/api'
import { Loader2, CheckCircle2, XCircle } from 'lucide-react'

export default function VerifyEmail() {
  const [params] = useSearchParams()
  const token = params.get('token') || ''
  const [status, setStatus] = useState<'loading' | 'ok' | 'err'>('loading')
  const [message, setMessage] = useState('')

  useEffect(() => {
    if (!token) {
      setStatus('err')
      setMessage('Falta el token en la URL.')
      return
    }
    let cancelled = false
    ;(async () => {
      try {
        await authAPI.verifyEmail(token)
        if (!cancelled) {
          setStatus('ok')
          setMessage('Correo verificado. Ya podés iniciar sesión.')
        }
      } catch {
        if (!cancelled) {
          setStatus('err')
          setMessage('El enlace no es válido o expiró.')
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [token])

  return (
    <div className="min-h-screen flex items-center justify-center bg-muted/30 px-4">
      <div className="max-w-md w-full bg-card border border-border rounded-2xl p-8 text-center space-y-4">
        {status === 'loading' && (
          <>
            <Loader2 className="w-10 h-10 animate-spin mx-auto text-primary" />
            <p className="text-muted-foreground">Verificando correo…</p>
          </>
        )}
        {status === 'ok' && (
          <>
            <CheckCircle2 className="w-12 h-12 mx-auto text-green-600" />
            <p className="font-medium">{message}</p>
            <Link
              to="/login"
              className="inline-block mt-2 text-primary font-medium hover:underline"
            >
              Ir al inicio de sesión
            </Link>
          </>
        )}
        {status === 'err' && (
          <>
            <XCircle className="w-12 h-12 mx-auto text-destructive" />
            <p className="font-medium">{message}</p>
            <Link to="/login" className="inline-block text-primary font-medium hover:underline">
              Volver al login
            </Link>
          </>
        )}
      </div>
    </div>
  )
}

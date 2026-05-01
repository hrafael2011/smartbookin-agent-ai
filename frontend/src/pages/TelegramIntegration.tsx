/**
 * Telegram channels for customer booking and owner commands.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  AlertCircle,
  CheckCircle2,
  Copy,
  ExternalLink,
  KeyRound,
  Loader2,
  MessageCircle,
  RefreshCw,
  Send,
  ShieldCheck,
} from 'lucide-react'
import { toast } from 'sonner'

import { Button, EmptyState } from '@/components/ui'
import { ownerTelegramAPI, telegramAPI } from '@/services/api'
import { useBusinessStore } from '@/store/businessStore'

export default function TelegramIntegration() {
  const { currentBusiness } = useBusinessStore()
  const businessId = currentBusiness?.id
  const qc = useQueryClient()

  const customerQuery = useQuery({
    queryKey: ['telegram-activation', businessId],
    queryFn: () => telegramAPI.getActivation(businessId!),
    enabled: !!businessId,
  })

  const ownerQuery = useQuery({
    queryKey: ['owner-telegram-activation', businessId],
    queryFn: () => ownerTelegramAPI.getActivation(businessId!),
    enabled: !!businessId,
  })

  const rotate = useMutation({
    mutationFn: () => telegramAPI.rotateInvite(businessId!),
    onSuccess: (data) => {
      qc.setQueryData(['telegram-activation', businessId], data)
      toast.success('Se generó un nuevo código. Los enlaces anteriores dejan de valer.')
    },
    onError: () => toast.error('No se pudo rotar el código'),
  })

  const copy = (text: string, label: string) => {
    if (!text) {
      toast.error('Nada que copiar')
      return
    }
    void navigator.clipboard.writeText(text)
    toast.success(label + ' copiado')
  }

  const customerActivationMessage = customerQuery.data?.deep_link
    ? 'Hola, agenda tu cita en Telegram con ' + currentBusiness?.name + ': ' + customerQuery.data.deep_link
    : 'Hola, agenda tu cita en Telegram con ' + currentBusiness?.name + '. Escribe /start y pega este código: ' + (customerQuery.data?.invite_token || '')

  const ownerActivationMessage = ownerQuery.data?.deep_link
    ? 'Panel del dueño para ' + currentBusiness?.name + ': ' + ownerQuery.data.deep_link
    : 'Panel del dueño para ' + currentBusiness?.name + '. Escribe /start y pega este código: ' + (ownerQuery.data?.payload || '')

  const ownerExpiration = ownerQuery.data?.activation_expires_at
    ? new Date(ownerQuery.data.activation_expires_at).toLocaleString()
    : ''

  if (!businessId) {
    return (
      <div className="p-6 max-w-2xl">
        <EmptyState
          icon={<MessageCircle className="h-6 w-6" />}
          title="Crea un negocio primero"
          description="Cada negocio tiene sus canales de Telegram. Cuando crees uno, podrás activarlos desde aquí."
        />
      </div>
    )
  }

  return (
    <div className="p-6 max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <MessageCircle className="w-7 h-7 text-sky-500" />
          Telegram
        </h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Un bot para clientes y un canal separado para el dueño de{' '}
          <span className="font-medium text-foreground">{currentBusiness?.name}</span>.
        </p>
      </div>

      <section className="space-y-4 rounded-xl border border-border bg-card p-5">
        <div>
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Send className="h-5 w-5 text-sky-500" />
            Canal de clientes
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            Tus clientes usan este enlace para entrar al menú guiado de reservas.
          </p>
        </div>

        {customerQuery.isLoading && (
          <div className="flex items-center gap-2 text-muted-foreground">
            <Loader2 className="w-5 h-5 animate-spin" />
            Cargando...
          </div>
        )}

        {customerQuery.isError && (
          <p className="text-destructive text-sm">No se pudo cargar la configuración de Telegram.</p>
        )}

        {customerQuery.data && (
          <div className="space-y-5">
            {!customerQuery.data.bot_username && (
              <div className="text-amber-800 dark:text-amber-200 bg-amber-500/10 border border-amber-500/30 rounded-lg px-3 py-2 text-sm">
                Configurá <code className="text-xs">TELEGRAM_BOT_USERNAME</code> para generar el enlace
                directo. El código funciona igual pegándolo en el chat.
              </div>
            )}

            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-lg border border-border bg-muted/30 p-3">
                <Send className="h-5 w-5 text-sky-500" />
                <div className="mt-2 text-sm font-medium">Comparte</div>
                <div className="text-xs text-muted-foreground">Envía el enlace a tus clientes.</div>
              </div>
              <div className="rounded-lg border border-border bg-muted/30 p-3">
                <MessageCircle className="h-5 w-5 text-sky-500" />
                <div className="mt-2 text-sm font-medium">Cliente escribe</div>
                <div className="text-xs text-muted-foreground">Telegram lo vincula al negocio.</div>
              </div>
              <div className="rounded-lg border border-border bg-muted/30 p-3">
                <ShieldCheck className="h-5 w-5 text-green-600" />
                <div className="mt-2 text-sm font-medium">Citas activas</div>
                <div className="text-xs text-muted-foreground">El bot agenda con tus servicios.</div>
              </div>
            </div>

            <CopyBlock
              label="Enlace profundo"
              value={customerQuery.data.deep_link || '(definí TELEGRAM_BOT_USERNAME)'}
              disabled={!customerQuery.data.deep_link}
              onCopy={() => copy(customerQuery.data?.deep_link || '', 'Enlace')}
            />

            <CopyBlock
              label="Mensaje para clientes"
              value={customerActivationMessage}
              onCopy={() => copy(customerActivationMessage, 'Mensaje')}
              multiline
            />

            <CopyBlock
              label="Código / payload start"
              value={customerQuery.data.invite_token}
              onCopy={() => copy(customerQuery.data?.invite_token || '', 'Código')}
            />

            <div className="flex flex-wrap items-center gap-3 pt-2">
              <span
                className={
                  'text-sm font-medium ' +
                  (customerQuery.data.has_first_contact ? 'text-green-600' : 'text-muted-foreground')
                }
              >
                {customerQuery.data.has_first_contact
                  ? 'Ya hubo primer contacto por Telegram'
                  : 'Aún no hubo primer contacto'}
              </span>
              {customerQuery.data.deep_link && (
                <Button
                  type="button"
                  size="sm"
                  onClick={() => window.open(customerQuery.data.deep_link, '_blank', 'noopener,noreferrer')}
                >
                  <ExternalLink className="h-4 w-4" />
                  Abrir bot
                </Button>
              )}
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => copy(customerActivationMessage, 'Mensaje')}
              >
                <Copy className="h-4 w-4" />
                Copiar invitación
              </Button>
              <button
                type="button"
                disabled={rotate.isPending}
                onClick={() => rotate.mutate()}
                className="inline-flex items-center gap-2 text-sm px-3 py-2 rounded-lg border border-border hover:bg-muted disabled:opacity-50"
              >
                {rotate.isPending ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <RefreshCw className="w-4 h-4" />
                )}
                Regenerar código
              </button>
            </div>
          </div>
        )}
      </section>

      <section className="space-y-4 rounded-xl border border-border bg-card p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold flex items-center gap-2">
              <KeyRound className="h-5 w-5 text-emerald-600" />
              Canal del dueño
            </h2>
            <p className="text-sm text-muted-foreground mt-1">
              Acceso privado para consultar agenda, métricas y estado operativo desde Telegram.
            </p>
          </div>
          {ownerQuery.data && (
            <span
              className={
                'inline-flex items-center gap-1 rounded-md px-2.5 py-1 text-xs font-medium ' +
                (ownerQuery.data.has_active_binding
                  ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300'
                  : 'bg-amber-500/10 text-amber-700 dark:text-amber-300')
              }
            >
              {ownerQuery.data.has_active_binding ? (
                <CheckCircle2 className="h-3.5 w-3.5" />
              ) : (
                <AlertCircle className="h-3.5 w-3.5" />
              )}
              {ownerQuery.data.has_active_binding ? 'Activo' : 'Pendiente'}
            </span>
          )}
        </div>

        {ownerQuery.isLoading && (
          <div className="flex items-center gap-2 text-muted-foreground">
            <Loader2 className="w-5 h-5 animate-spin" />
            Cargando canal del dueño...
          </div>
        )}

        {ownerQuery.isError && (
          <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm text-amber-800 dark:text-amber-200">
            No se pudo cargar el canal del dueño. Si esta cuenta tiene más de un negocio heredado,
            soporte debe resolver el negocio activo antes de activarlo.
          </div>
        )}

        {ownerQuery.data && (
          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-lg border border-border bg-muted/30 p-3">
                <ShieldCheck className="h-5 w-5 text-emerald-600" />
                <div className="mt-2 text-sm font-medium">Acceso dueño</div>
                <div className="text-xs text-muted-foreground">No comparte permisos con clientes.</div>
              </div>
              <div className="rounded-lg border border-border bg-muted/30 p-3">
                <MessageCircle className="h-5 w-5 text-sky-500" />
                <div className="mt-2 text-sm font-medium">Menú guiado</div>
                <div className="text-xs text-muted-foreground">Agenda, métricas y navegación rápida.</div>
              </div>
              <div className="rounded-lg border border-border bg-muted/30 p-3">
                <KeyRound className="h-5 w-5 text-amber-600" />
                <div className="mt-2 text-sm font-medium">Token temporal</div>
                <div className="text-xs text-muted-foreground">Expira {ownerExpiration || 'pronto'}.</div>
              </div>
            </div>

            {!ownerQuery.data.bot_username && (
              <div className="text-amber-800 dark:text-amber-200 bg-amber-500/10 border border-amber-500/30 rounded-lg px-3 py-2 text-sm">
                Configurá <code className="text-xs">TELEGRAM_BOT_USERNAME</code> para generar el enlace
                directo del dueño. El payload funciona igual pegándolo en el bot.
              </div>
            )}

            <CopyBlock
              label="Enlace del dueño"
              value={ownerQuery.data.deep_link || '(definí TELEGRAM_BOT_USERNAME)'}
              disabled={!ownerQuery.data.deep_link}
              onCopy={() => copy(ownerQuery.data?.deep_link || '', 'Enlace del dueño')}
            />

            <CopyBlock
              label="Payload /start"
              value={ownerQuery.data.payload}
              onCopy={() => copy(ownerQuery.data?.payload || '', 'Payload del dueño')}
            />

            <div className="flex flex-wrap items-center gap-3 pt-1">
              {ownerQuery.data.deep_link && (
                <Button
                  type="button"
                  size="sm"
                  onClick={() => window.open(ownerQuery.data.deep_link, '_blank', 'noopener,noreferrer')}
                >
                  <ExternalLink className="h-4 w-4" />
                  Abrir panel
                </Button>
              )}
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => copy(ownerActivationMessage, 'Mensaje del dueño')}
              >
                <Copy className="h-4 w-4" />
                Copiar acceso
              </Button>
            </div>

            <p className="text-xs text-muted-foreground border-t border-border pt-4">
              El canal del dueño es de consulta en este MVP. Crear, cancelar o modificar citas queda
              reservado para una fase posterior con confirmación explícita.
            </p>
          </div>
        )}
      </section>
    </div>
  )
}

function CopyBlock({
  label,
  value,
  onCopy,
  disabled = false,
  multiline = false,
}: {
  label: string
  value: string
  onCopy: () => void
  disabled?: boolean
  multiline?: boolean
}) {
  return (
    <div>
      <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
        {label}
      </div>
      <div className="mt-1 flex flex-wrap gap-2 items-center">
        <code
          className={
            'flex-1 min-w-0 text-sm bg-muted px-3 py-2 rounded-lg ' +
            (multiline ? 'whitespace-pre-wrap break-words' : 'break-all')
          }
        >
          {value}
        </code>
        <button
          type="button"
          onClick={onCopy}
          disabled={disabled}
          className="p-2 rounded-lg border border-border hover:bg-muted disabled:opacity-50"
          title={'Copiar ' + label.toLowerCase()}
        >
          <Copy className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}

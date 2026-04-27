/**
 * Enlace y código de Telegram para el negocio actual (un solo bot multi-tenant)
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useBusinessStore } from '@/store/businessStore'
import { telegramAPI } from '@/services/api'
import { MessageCircle, Copy, RefreshCw, Loader2, ExternalLink, Send, ShieldCheck } from 'lucide-react'
import { toast } from 'sonner'
import { Button, EmptyState } from '@/components/ui'

export default function TelegramIntegration() {
  const { currentBusiness } = useBusinessStore()
  const businessId = currentBusiness?.id
  const qc = useQueryClient()

  const q = useQuery({
    queryKey: ['telegram-activation', businessId],
    queryFn: () => telegramAPI.getActivation(businessId!),
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

  const activationMessage = q.data?.deep_link
    ? 'Hola, agenda tu cita en Telegram con ' + currentBusiness?.name + ': ' + q.data.deep_link
    : 'Hola, agenda tu cita en Telegram con ' + currentBusiness?.name + '. Escribe /start y pega este código: ' + (q.data?.invite_token || '')

  if (!businessId) {
    return (
      <div className="p-6 max-w-2xl">
        <EmptyState
          icon={<MessageCircle className="h-6 w-6" />}
          title="Crea un negocio primero"
          description="Cada negocio tiene su propio enlace y código de Telegram. Cuando crees uno, podrás copiarlo desde aquí."
        />
      </div>
    )
  }

  return (
    <div className="p-6 max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <MessageCircle className="w-7 h-7 text-sky-500" />
          Telegram
        </h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Un solo bot para todos los negocios. Tus clientes usan tu enlace o código para
          vincularse solo a <span className="font-medium text-foreground">{currentBusiness?.name}</span>.
        </p>
      </div>

      {q.isLoading && (
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="w-5 h-5 animate-spin" />
          Cargando…
        </div>
      )}

      {q.isError && (
        <p className="text-destructive text-sm">No se pudo cargar la configuración de Telegram.</p>
      )}

      {q.data && (
        <div className="space-y-5 rounded-xl border border-border bg-card p-5">
          {!q.data.bot_username && (
            <div className="text-amber-800 dark:text-amber-200 bg-amber-500/10 border border-amber-500/30 rounded-lg px-3 py-2 text-sm">
              Configurá <code className="text-xs">TELEGRAM_BOT_USERNAME</code> en el servidor (sin @)
              para generar el enlace <code className="text-xs">t.me/...</code>. El código de abajo
              funciona igual para pegarlo en el chat.
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

          <div>
            <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              Enlace profundo
            </div>
            <div className="mt-1 flex flex-wrap gap-2 items-center">
              <code className="flex-1 min-w-0 break-all text-sm bg-muted px-3 py-2 rounded-lg">
                {q.data.deep_link || '(definí TELEGRAM_BOT_USERNAME)'}
              </code>
              <button
                type="button"
                onClick={() => copy(q.data.deep_link, 'Enlace')}
                disabled={!q.data.deep_link}
                className="p-2 rounded-lg border border-border hover:bg-muted"
                title="Copiar"
              >
                <Copy className="w-4 h-4" />
              </button>
            </div>
          </div>

          <div>
            <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              Mensaje para clientes
            </div>
            <div className="mt-1 flex flex-wrap gap-2 items-center">
              <code className="flex-1 min-w-0 whitespace-pre-wrap break-words text-sm bg-muted px-3 py-2 rounded-lg">
                {activationMessage}
              </code>
              <button
                type="button"
                onClick={() => copy(activationMessage, 'Mensaje')}
                className="p-2 rounded-lg border border-border hover:bg-muted"
                title="Copiar mensaje"
              >
                <Copy className="w-4 h-4" />
              </button>
            </div>
          </div>

          <div>
            <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              Código / payload start
            </div>
            <div className="mt-1 flex flex-wrap gap-2 items-center">
              <code className="flex-1 min-w-0 break-all text-sm bg-muted px-3 py-2 rounded-lg">
                {q.data.invite_token}
              </code>
              <button
                type="button"
                onClick={() => copy(q.data.invite_token, 'Código')}
                className="p-2 rounded-lg border border-border hover:bg-muted"
              >
                <Copy className="w-4 h-4" />
              </button>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3 pt-2">
            <span
              className={
                'text-sm font-medium ' +
                (q.data.has_first_contact ? 'text-green-600' : 'text-muted-foreground')
              }
            >
              {q.data.has_first_contact
                ? 'Ya hubo primer contacto por Telegram'
                : 'Aún no hubo primer contacto'}
            </span>
            {q.data.deep_link && (
              <Button
                type="button"
                size="sm"
                onClick={() => window.open(q.data.deep_link, '_blank', 'noopener,noreferrer')}
              >
                <ExternalLink className="h-4 w-4" />
                Abrir bot
              </Button>
            )}
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => copy(activationMessage, 'Mensaje')}
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

          <p className="text-xs text-muted-foreground border-t border-border pt-4">
            Comparte el enlace profundo con tus clientes. Después de que abran el enlace y escriban
            por primera vez, este estado cambiará a conectado. Los clientes pueden escribir{' '}
            <strong>/cambiar</strong> para asociarse a otro negocio usando un código nuevo.
          </p>
        </div>
      )}
    </div>
  )
}

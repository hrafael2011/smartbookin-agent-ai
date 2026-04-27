/**
 * Enlace y código de Telegram para el negocio actual (un solo bot multi-tenant)
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useBusinessStore } from '@/store/businessStore'
import { telegramAPI } from '@/services/api'
import { MessageCircle, Copy, RefreshCw, Loader2 } from 'lucide-react'
import { toast } from 'sonner'

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

  if (!businessId) {
    return (
      <div className="p-6 max-w-2xl">
        <p className="text-muted-foreground">Seleccioná un negocio en la barra lateral.</p>
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
        <div className="space-y-4 rounded-xl border border-border bg-card p-5">
          {!q.data.bot_username && (
            <div className="text-amber-800 dark:text-amber-200 bg-amber-500/10 border border-amber-500/30 rounded-lg px-3 py-2 text-sm">
              Configurá <code className="text-xs">TELEGRAM_BOT_USERNAME</code> en el servidor (sin @)
              para generar el enlace <code className="text-xs">t.me/...</code>. El código de abajo
              funciona igual para pegarlo en el chat.
            </div>
          )}

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
                className="p-2 rounded-lg border border-border hover:bg-muted"
                title="Copiar"
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
            Los clientes pueden escribir <strong>/cambiar</strong> en el bot para asociarse a otro
            negocio usando un código nuevo.
          </p>
        </div>
      )}
    </div>
  )
}

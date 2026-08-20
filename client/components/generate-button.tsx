'use client'

import { createContext, useContext, useRef, useState, type ReactNode } from 'react'
import { useRouter } from 'next/navigation'
import { Sparkles, X } from 'lucide-react'
import { toast } from 'react-toastify'
import { wsUrl } from '@/lib/api'
import { Spinner } from './primitives'
import { cn } from '@/lib/utils'
import { ChatMarkdown } from './chat-markdown'

const PROGRESS_TOAST = 'report-generating'

type Phase = 'idle' | 'sync' | 'writing'

type GenerateReportContextValue = {
  phase: Phase
  start: (onDone?: () => void) => void
}

const GenerateReportContext = createContext<GenerateReportContextValue | null>(null)

function useGenerateReport() {
  const ctx = useContext(GenerateReportContext)
  if (!ctx) {
    throw new Error('GenerateButton precisa do GenerateReportProvider')
  }
  return ctx
}

export function GenerateReportProvider({ children }: { children: ReactNode }) {
  const router = useRouter()
  const [phase, setPhase] = useState<Phase>('idle')
  const [draft, setDraft] = useState('')
  const [open, setOpen] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const finishedRef = useRef(false)
  const openRef = useRef(false)
  const onDoneRef = useRef<(() => void) | undefined>(undefined)
  openRef.current = open

  function dismissProgressToast() {
    toast.dismiss(PROGRESS_TOAST)
  }

  function showProgressToast() {
    toast.info('Relatório gerando em segundo plano. Clique para voltar.', {
      toastId: PROGRESS_TOAST,
      autoClose: false,
      closeOnClick: true,
      draggable: false,
      onClick: () => {
        setOpen(true)
        dismissProgressToast()
      },
    })
  }

  function minimize() {
    setOpen(false)
    if (!finishedRef.current) showProgressToast()
  }

  function finishOk(id: number | string | undefined) {
    finishedRef.current = true
    dismissProgressToast()
    setOpen(false)
    setPhase('idle')
    setDraft('')
    toast.success('Relatório gerado com sucesso.')
    onDoneRef.current?.()
    if (id != null) router.push(`/relatorios/${id}`)
    else router.push('/relatorios')
  }

  function fail(msg: string) {
    if (finishedRef.current) return
    finishedRef.current = true
    dismissProgressToast()
    setPhase('idle')
    toast.error(msg)
  }

  function start(onDone?: () => void) {
    if (onDone) onDoneRef.current = onDone
    if (phase !== 'idle') {
      setOpen(true)
      dismissProgressToast()
      return
    }
    finishedRef.current = false
    setOpen(true)
    setDraft('')
    setPhase('sync')

    let ws: WebSocket
    try {
      ws = new WebSocket(wsUrl('/ws/reports/generate'))
    } catch {
      fail('Geração indisponível.')
      setOpen(false)
      return
    }
    wsRef.current = ws

    ws.onmessage = (ev) => {
      let data: {
        type: string
        value?: string
        content?: string
        detail?: string
        report_id?: number | string
      }
      try {
        data = JSON.parse(ev.data)
      } catch {
        return
      }
      if (data.type === 'phase' && (data.value === 'sync' || data.value === 'writing')) {
        setPhase(data.value)
      } else if (data.type === 'narrative_delta') {
        setPhase('writing')
        setDraft((prev) => prev + (data.content || ''))
      } else if (data.type === 'done') {
        finishOk(data.report_id)
      } else if (data.type === 'error') {
        fail(data.detail || 'Falha ao gerar relatório.')
      }
    }

    ws.onerror = () => {
      fail('Falha ao gerar relatório.')
    }

    ws.onclose = () => {
      wsRef.current = null
      if (!finishedRef.current) fail('Conexão encerrada antes de terminar o relatório.')
    }
  }

  return (
    <GenerateReportContext.Provider value={{ phase, start }}>
      {children}
      {open ? (
        <div className="fixed inset-0 z-[60] flex items-end justify-center bg-black/50 p-4 sm:items-center">
          <div className="flex max-h-[85vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-border bg-chrome shadow-2xl">
            <header className="flex shrink-0 items-center justify-between border-b border-border px-4 py-3">
              <div className="flex items-center gap-2">
                {phase !== 'idle' ? <Spinner /> : null}
                <span className="text-sm font-medium text-foreground">
                  {phase === 'sync'
                    ? 'Sincronizando ClickUp…'
                    : phase === 'writing'
                      ? 'Escrevendo o diagnóstico…'
                      : 'Diagnóstico'}
                </span>
              </div>
              <button
                type="button"
                aria-label="Minimizar"
                className="rounded-md p-1 text-muted-foreground hover:bg-white/5 hover:text-foreground"
                onClick={minimize}
              >
                <X className="h-4 w-4" />
              </button>
            </header>
            <div className="min-h-[12rem] flex-1 overflow-y-auto px-5 py-4">
              {draft ? (
                <ChatMarkdown text={draft} />
              ) : (
                <p className="text-sm text-muted-foreground">
                  {phase === 'sync'
                    ? 'Buscando o board. O texto aparece assim que o analista começar a escrever.'
                    : 'Aguardando o primeiro trecho…'}
                </p>
              )}
            </div>
          </div>
        </div>
      ) : null}
    </GenerateReportContext.Provider>
  )
}

export function GenerateButton({
  variant = 'solid',
  onDone,
}: {
  variant?: 'ghost' | 'solid'
  onDone?: () => void
}) {
  const { phase, start } = useGenerateReport()
  const loading = phase !== 'idle'
  const label =
    phase === 'sync'
      ? 'Sincronizando ClickUp…'
      : phase === 'writing'
        ? 'Escrevendo o diagnóstico…'
        : 'Gerar Relatório'

  return (
    <button
      type="button"
      onClick={() => start(onDone)}
      className={cn(
        'flex min-w-0 items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
        variant === 'solid'
          ? 'bg-primary text-primary-foreground hover:opacity-90'
          : 'border border-border text-foreground hover:bg-[color:var(--accent-soft)]',
      )}
    >
      {loading ? <Spinner /> : <Sparkles className="h-4 w-4" />}
      {label}
    </button>
  )
}

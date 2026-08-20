'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import { usePathname } from 'next/navigation'
import { MessageSquare, X, Send } from 'lucide-react'
import { toast } from 'react-toastify'
import { api, wsUrl } from '@/lib/api'
import { cn } from '@/lib/utils'
import { ChatMarkdown } from './chat-markdown'

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

type ConnState = 'idle' | 'connecting' | 'open' | 'closed' | 'error'

function reportIdFromPath(path: string): number | undefined {
  const m = path.match(/^\/relatorios\/(\d+)/)
  return m ? Number(m[1]) : undefined
}

function fitTextarea(el: HTMLTextAreaElement | null) {
  if (!el) return
  el.style.height = '0px'
  el.style.height = `${Math.min(el.scrollHeight, 120)}px`
}

export function ChatWidget() {
  const pathname = usePathname()
  const reportId = reportIdFromPath(pathname || '')
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [conn, setConn] = useState<ConnState>('idle')

  const wsRef = useRef<WebSocket | null>(null)
  const retriedRef = useRef(false)
  const listRef = useRef<HTMLDivElement | null>(null)
  const inputRef = useRef<HTMLTextAreaElement | null>(null)

  const connect = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState <= 1) return
    setConn('connecting')
    let ws: WebSocket
    try {
      ws = new WebSocket(wsUrl('/ws/chat'))
    } catch {
      setConn('error')
      toast.error('Chat indisponível.')
      return
    }
    wsRef.current = ws

    ws.onopen = () => {
      setConn('open')
      retriedRef.current = false
      toast.info('Chat conectado.')
    }

    ws.onmessage = (ev) => {
      let data: { type: string; content?: string; detail?: string }
      try {
        data = JSON.parse(ev.data)
      } catch {
        return
      }
      if (data.type === 'assistant_delta') {
        setMessages((prev) => {
          const last = prev[prev.length - 1]
          if (last && last.role === 'assistant') {
            const copy = [...prev]
            copy[copy.length - 1] = {
              role: 'assistant',
              content: last.content + (data.content || ''),
            }
            return copy
          }
          return [...prev, { role: 'assistant', content: data.content || '' }]
        })
      } else if (data.type === 'error') {
        toast.error(data.detail || 'Erro no chat.')
      }
    }

    ws.onerror = () => {
      setConn('error')
    }

    ws.onclose = () => {
      setConn('closed')
      toast.info('Chat desconectado.')
      if (!retriedRef.current) {
        retriedRef.current = true
        setTimeout(() => {
          if (open) connect()
        }, 1500)
      }
    }
  }, [open])

  useEffect(() => {
    if (open) connect()
    return () => {
      if (!open && wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [open, connect])

  useEffect(() => {
    if (!open) return
    const q = reportId != null ? `?report_id=${reportId}` : ''
    api<{ messages?: ChatMessage[] }>(`/api/chat/history${q}`, { silent: true })
      .then((r) => setMessages(r.messages || []))
      .catch(() => setMessages([]))
  }, [open, reportId])

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    fitTextarea(inputRef.current)
  }, [input, open])

  function send() {
    const text = input.trim()
    if (!text) return
    const ws = wsRef.current
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      toast.error('Chat indisponível.')
      return
    }
    setMessages((prev) => [...prev, { role: 'user', content: text }])
    const payload: { type: string; content: string; report_id?: number } = {
      type: 'user',
      content: text,
    }
    if (reportId != null) payload.report_id = reportId
    ws.send(JSON.stringify(payload))
    setInput('')
    requestAnimationFrame(() => {
      fitTextarea(inputRef.current)
      inputRef.current?.focus()
    })
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (
      e.key === 'Enter' &&
      !e.shiftKey &&
      !e.nativeEvent.isComposing &&
      e.keyCode !== 229
    ) {
      e.preventDefault()
      send()
    }
  }

  const placeholder = reportId
    ? 'Pergunte sobre este relatório…'
    : 'Pergunte sobre o relatório ou as métricas…'
  const emptyHint = reportId
    ? 'Pergunte sobre este relatório. Pode usar **negrito** e emoji.'
    : 'Pergunte sobre o relatório ou as métricas. Pode usar **negrito** e emoji.'

  return (
    <>
      {open ? (
        <div className="fixed bottom-24 right-6 z-50 flex h-[32rem] w-[26rem] max-w-[calc(100vw-2rem)] flex-col overflow-hidden rounded-2xl border border-border bg-chrome shadow-2xl">
          <header className="flex shrink-0 items-center justify-between border-b border-border px-4 py-3">
            <div className="flex items-center gap-2">
              <span
                className={cn(
                  'h-2 w-2 rounded-full',
                  conn === 'open'
                    ? 'bg-success'
                    : conn === 'connecting'
                      ? 'bg-warn'
                      : 'bg-muted-foreground',
                )}
              />
              <span className="text-sm font-medium text-foreground">Analista</span>
            </div>
            <button
              type="button"
              onClick={() => setOpen(false)}
              aria-label="Fechar chat"
              className="rounded-md p-1 text-muted-foreground hover:bg-white/5 hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
          </header>

          <div ref={listRef} className="min-h-0 flex-1 space-y-3 overflow-y-auto px-3 py-4">
            {conn === 'error' ? (
              <p className="text-center text-sm text-muted-foreground">
                Chat indisponível.
              </p>
            ) : messages.length === 0 ? (
              <p className="px-2 text-center text-sm leading-6 text-muted-foreground">
                {emptyHint}
              </p>
            ) : (
              messages.map((m, i) => (
                <div
                  key={i}
                  className={cn(
                    'w-fit max-w-[88%] rounded-2xl px-3.5 py-2.5',
                    m.role === 'user'
                      ? 'ml-auto bg-primary text-primary-foreground'
                      : 'mr-auto bg-card text-foreground',
                  )}
                >
                  <ChatMarkdown text={m.content} />
                </div>
              ))
            )}
          </div>

          <div className="shrink-0 border-t border-border bg-chrome p-3">
            <div className="flex items-end gap-2">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={onKeyDown}
                rows={1}
                lang="pt-BR"
                enterKeyHint="send"
                autoComplete="off"
                spellCheck
                placeholder={placeholder}
                className="max-h-[7.5rem] min-h-11 min-w-0 flex-1 resize-none overflow-y-auto rounded-xl border border-white/15 bg-card px-3.5 py-2.5 text-sm leading-5 text-foreground outline-none placeholder:truncate placeholder:text-muted-foreground focus:border-primary"
              />
              <button
                type="button"
                onClick={send}
                aria-label="Enviar"
                className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary text-primary-foreground hover:opacity-90"
              >
                <Send className="h-4 w-4" />
              </button>
            </div>
            <p className="mt-1.5 px-0.5 text-[11px] leading-4 text-muted-foreground">
              Enter envia · Shift+Enter nova linha
            </p>
          </div>
        </div>
      ) : null}

      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label={open ? 'Fechar chat' : 'Abrir chat'}
        className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg transition-transform hover:scale-105"
      >
        {open ? <X className="h-6 w-6" /> : <MessageSquare className="h-6 w-6" />}
      </button>
    </>
  )
}

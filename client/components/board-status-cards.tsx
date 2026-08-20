'use client'

import { useEffect, useState } from 'react'
import { ExternalLink, X } from 'lucide-react'
import type { TaskRef } from '@/lib/humanize'
import { StatusBadge, TaskLink } from './primitives'
import { KpiCard } from './kpi-card'

export type BoardBucket = 'abertos' | 'pendente' | 'concluidos'

export function boardBucket(status?: string): BoardBucket {
  if (status === 'CONCLUIDO') return 'concluidos'
  if (status === 'A_FAZER') return 'pendente'
  return 'abertos'
}

const BUCKET_META: Record<
  BoardBucket,
  { label: string; sub: string; tone: 'default' | 'accent' | 'success' | 'warn'; title: string }
> = {
  abertos: {
    label: 'Abertos',
    sub: 'em andamento, revisão, bloqueado',
    tone: 'accent',
    title: 'Cards abertos',
  },
  pendente: {
    label: 'Pendente',
    sub: 'a fazer, na fila',
    tone: 'warn',
    title: 'Cards pendentes',
  },
  concluidos: {
    label: 'Concluído',
    sub: 'fechados no ClickUp',
    tone: 'success',
    title: 'Cards concluídos',
  },
}

export function BoardStatusCards({ tasks }: { tasks: TaskRef[] }) {
  const groups: Record<BoardBucket, TaskRef[]> = {
    abertos: [],
    pendente: [],
    concluidos: [],
  }
  for (const t of tasks) {
    groups[boardBucket(t.status_canonical)].push(t)
  }

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      {(['abertos', 'pendente', 'concluidos'] as BoardBucket[]).map((key) => (
        <BoardCard key={key} bucket={key} items={groups[key]} />
      ))}
    </div>
  )
}

function BoardCard({ bucket, items }: { bucket: BoardBucket; items: TaskRef[] }) {
  const meta = BUCKET_META[bucket]
  const [open, setOpen] = useState(false)

  return (
    <>
      <KpiCard
        label={meta.label}
        value={items.length}
        sub={meta.sub}
        tone={meta.tone}
        onClick={() => setOpen(true)}
      />
      {open ? (
        <TaskListModal title={meta.title} items={items} onClose={() => setOpen(false)} />
      ) : null}
    </>
  )
}

function TaskListModal({
  title,
  items,
  onClose,
}: {
  title: string
  items: TaskRef[]
  onClose: () => void
}) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-[80] flex items-center justify-center bg-black/70 p-4"
      onClick={onClose}
      role="presentation"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="flex max-h-[80vh] w-full max-w-lg flex-col overflow-hidden rounded-2xl border border-border bg-chrome shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between border-b border-border px-5 py-4">
          <div>
            <h2 className="text-base font-semibold text-foreground">{title}</h2>
            <p className="text-xs text-muted-foreground">
              {items.length} card{items.length === 1 ? '' : 's'}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Fechar"
            className="rounded-lg p-1 text-muted-foreground hover:bg-white/5 hover:text-foreground"
          >
            <X className="h-5 w-5" />
          </button>
        </header>
        <div className="flex-1 overflow-y-auto p-3">
          {items.length === 0 ? (
            <p className="px-2 py-8 text-center text-sm text-muted-foreground">
              Nenhum card neste grupo.
            </p>
          ) : (
            <ul className="grid gap-1">
              {items.map((t) => (
                <li
                  key={t.clickup_id}
                  className="flex items-center justify-between gap-3 rounded-lg px-3 py-2 hover:bg-white/[0.03]"
                >
                  <div className="min-w-0">
                    <TaskLink taskId={t.clickup_id} url={t.url} label={t.name} />
                    {t.status_raw ? (
                      <p className="mt-0.5 text-xs text-muted-foreground">
                        Status no ClickUp: {t.status_raw}
                      </p>
                    ) : null}
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <StatusBadge status={t.status_canonical || 'OUTRO'} />
                    {t.url ? (
                      <a
                        href={t.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs font-medium text-foreground hover:bg-white/5"
                      >
                        Ver no ClickUp
                        <ExternalLink className="h-3 w-3" />
                      </a>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}

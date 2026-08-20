'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, ExternalLink } from 'lucide-react'
import { api, fmtDateTime } from '@/lib/api'
import type { TaskDetail } from '@/lib/types'
import { Card, EmptyState, PageLoader, SectionTitle, StatusBadge } from './primitives'
import { DataTable, Row, Cell } from './data-table'

function normalizeAssignees(a: unknown): { id: string; username: string }[] {
  if (Array.isArray(a)) return a as { id: string; username: string }[]
  if (a && typeof a === 'object') return [a as { id: string; username: string }]
  return []
}

function Meta({ label, value }: { label: string; value?: string | null }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd className="mt-0.5 text-sm text-foreground">{value || '—'}</dd>
    </div>
  )
}

export function TaskView({ id }: { id: string }) {
  const [data, setData] = useState<TaskDetail | null>(null)
  const [status, setStatus] = useState<'loading' | 'ready' | 'notfound'>('loading')

  useEffect(() => {
    let active = true
    api<TaskDetail>(`/api/tasks/${id}`)
      .then((d) => {
        if (active) {
          setData(d)
          setStatus('ready')
        }
      })
      .catch(() => active && setStatus('notfound'))
    return () => {
      active = false
    }
  }, [id])

  if (status === 'loading') return <PageLoader />

  if (status === 'notfound' || !data) {
    return (
      <EmptyState
        title="Tarefa não encontrada."
        action={
          <Link
            href="/"
            className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
          >
            Voltar para a home
          </Link>
        }
      />
    )
  }

  const { task, comments, transitions } = data
  const assignees = normalizeAssignees(task.assignees)
  const recentComments = [...comments]
    .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
    .slice(0, 20)

  return (
    <div className="grid gap-6">
      <Link
        href="/"
        className="inline-flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        Voltar
      </Link>

      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-balance text-2xl font-semibold tracking-tight">
            {task.name}
          </h1>
          <p className="mt-1 font-mono text-sm text-muted-foreground">
            {task.custom_id || task.clickup_id}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge status={task.status_canonical} />
          {task.url ? (
            <a
              href={task.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 rounded-lg border border-border px-3 py-2 text-sm font-medium text-foreground hover:bg-[color:var(--accent-soft)]"
            >
              Abrir no ClickUp
              <ExternalLink className="h-4 w-4" />
            </a>
          ) : null}
        </div>
      </div>

      <Card>
        <dl className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <Meta label="Prioridade" value={task.prioridade} />
          <Meta label="Contexto" value={task.contexto} />
          <Meta label="Área" value={task.area} />
          <Meta label="Status (raw)" value={task.status_raw} />
        </dl>
        {assignees.length ? (
          <div className="mt-4 border-t border-border pt-4">
            <dt className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Responsáveis
            </dt>
            <div className="flex flex-wrap gap-2">
              {assignees.map((a) => (
                <span
                  key={a.id}
                  className="rounded-md bg-white/5 px-2 py-1 text-sm text-foreground"
                >
                  @{a.username}
                </span>
              ))}
            </div>
          </div>
        ) : null}
        {task.description ? (
          <div className="mt-4 border-t border-border pt-4">
            <p className="whitespace-pre-line text-sm leading-relaxed text-muted-foreground">
              {task.description}
            </p>
          </div>
        ) : null}
      </Card>

      {transitions.length ? (
        <Card>
          <SectionTitle>Transições de status</SectionTitle>
          <DataTable columns={['De', 'Para', 'Quando', 'Fonte']}>
            {transitions.map((t, i) => (
              <Row key={i}>
                <Cell>
                  <StatusBadge status={t.from_canonical} />
                </Cell>
                <Cell>
                  <StatusBadge status={t.to_canonical} />
                </Cell>
                <Cell className="text-muted-foreground">{fmtDateTime(t.at)}</Cell>
                <Cell className="text-muted-foreground">{t.source}</Cell>
              </Row>
            ))}
          </DataTable>
        </Card>
      ) : null}

      {recentComments.length ? (
        <Card>
          <SectionTitle hint="mais recentes">Comentários</SectionTitle>
          <ul className="grid gap-3">
            {recentComments.map((c) => (
              <li
                key={c.clickup_id}
                className="border-b border-border pb-3 last:border-0 last:pb-0"
              >
                <div className="mb-1 flex items-center justify-between gap-2 text-xs text-muted-foreground">
                  <span>@{c.author_id}</span>
                  <span>{fmtDateTime(c.date)}</span>
                </div>
                <p className="whitespace-pre-line text-sm leading-relaxed text-foreground">
                  {c.text}
                </p>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}
    </div>
  )
}

'use client'

import { useEffect, useState } from 'react'
import { api, num } from '@/lib/api'
import { HYGIENE_LABEL } from '@/lib/humanize'
import type {
  Aging,
  BlockChain,
  HygieneDuplicate,
  HygieneIssue,
  LeadCycle,
  Metrics,
  Page,
  Promised,
  TimeInStatus,
} from '@/lib/types'
import { Card, SectionTitle, StatusBadge, TaskLink } from './primitives'
import { DataTable, Row, Cell } from './data-table'
import { SimpleBar } from './charts'

const PAGE_SIZE = 5

function TablePager({
  page,
  limit,
  total,
  onPage,
}: {
  page: number
  limit: number
  total: number
  onPage: (page: number) => void
}) {
  if (total <= limit) return null
  const from = (page - 1) * limit + 1
  const to = Math.min(page * limit, total)
  const last = Math.max(1, Math.ceil(total / limit))
  return (
    <div className="mt-3 flex items-center justify-between gap-3 text-xs text-muted-foreground">
      <span>
        {from}–{to} de {total}
      </span>
      <div className="flex gap-2">
        <button
          type="button"
          disabled={page <= 1}
          onClick={() => onPage(page - 1)}
          className="rounded-md border border-border px-2 py-1 text-foreground disabled:opacity-40"
        >
          Anterior
        </button>
        <button
          type="button"
          disabled={page >= last}
          onClick={() => onPage(page + 1)}
          className="rounded-md border border-border px-2 py-1 text-foreground disabled:opacity-40"
        >
          Próxima
        </button>
      </div>
    </div>
  )
}

function usePagedMetric<T>(path: string, limit = PAGE_SIZE) {
  const [page, setPage] = useState(1)
  const [items, setItems] = useState<T[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    setLoading(true)
    api<Page<T>>(`${path}?page=${page}&limit=${limit}`, { silent: true })
      .then((d) => {
        if (!active) return
        setItems(d.items || [])
        setTotal(Number(d.total) || 0)
      })
      .catch(() => {
        if (!active) return
        setItems([])
        setTotal(0)
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [path, page, limit])

  return { page, setPage, items, total, loading, limit }
}

export function BottleneckBlock({ data }: { data: Metrics['bottleneck'] }) {
  if (!data.length) return null
  return (
    <Card>
      <SectionTitle hint="dias acumulados parados em cada etapa">Gargalos</SectionTitle>
      <DataTable columns={['Status', 'Lista', 'Dias acum.', 'Trechos', 'Média dias']}>
        {data.map((b, i) => (
          <Row key={i}>
            <Cell>
              <StatusBadge status={b.status_canonical} />
            </Cell>
            <Cell>{b.list_name}</Cell>
            <Cell className="tabular-nums">{num(b.dias_acumulados)}</Cell>
            <Cell className="tabular-nums">{b.trechos}</Cell>
            <Cell className="tabular-nums">{num(b.media_dias)}</Cell>
          </Row>
        ))}
      </DataTable>
    </Card>
  )
}

export function TimeInStatusBlock() {
  const { page, setPage, items, total, loading, limit } = usePagedMetric<TimeInStatus>(
    '/api/metrics/time-in-status',
  )
  if (!loading && total === 0) return null
  return (
    <Card>
      <SectionTitle hint="quanto tempo um card fica em cada etapa">Tempo em cada status</SectionTitle>
      <DataTable columns={['Status', 'Mediana (dias)', 'Casos mais lentos (dias)', 'Qtd']}>
        {items.map((t, i) => (
          <Row key={i}>
            <Cell>
              <StatusBadge status={t.status_canonical} />
            </Cell>
            <Cell className="tabular-nums">{num(t.mediana_dias)}</Cell>
            <Cell className="tabular-nums">{num(t.p85_dias)}</Cell>
            <Cell className="tabular-nums">{t.n}</Cell>
          </Row>
        ))}
      </DataTable>
      <TablePager page={page} limit={limit} total={total} onPage={setPage} />
    </Card>
  )
}

export function LeadCycleBlock() {
  const { page, setPage, items, total, loading, limit } = usePagedMetric<LeadCycle>(
    '/api/metrics/lead-cycle',
  )
  if (!loading && total === 0) return null
  return (
    <Card>
      <SectionTitle hint="criação até concluir · início do trabalho até concluir">
        Tempo de entrega
      </SectionTitle>
      <DataTable columns={['Lista', 'Área', 'Prioridade', 'Criação → fim (dias)', 'Início → fim (dias)', 'Qtd']}>
        {items.map((l, i) => (
          <Row key={i}>
            <Cell>{l.list_name}</Cell>
            <Cell className="text-muted-foreground">{l.area || '—'}</Cell>
            <Cell className="text-muted-foreground">{l.prioridade || '—'}</Cell>
            <Cell className="tabular-nums">{num(l.lead_mediana)}</Cell>
            <Cell className="tabular-nums">{num(l.cycle_mediana)}</Cell>
            <Cell className="tabular-nums">{l.n}</Cell>
          </Row>
        ))}
      </DataTable>
      <TablePager page={page} limit={limit} total={total} onPage={setPage} />
    </Card>
  )
}

export function WipBlock({ data }: { data: Metrics['wip'] }) {
  if (!data.length) return null
  const chart = [...data]
    .sort((a, b) => b.wip - a.wip)
    .slice(0, 10)
    .map((w) => ({ label: w.display_name, value: w.wip }))
  return (
    <Card>
      <SectionTitle hint="quantos cards cada pessoa tem em paralelo">Trabalho em paralelo</SectionTitle>
      <SimpleBar data={chart} horizontal color="#7b68ee" />
      <div className="mt-4">
        <DataTable columns={['Pessoa', 'Em paralelo', 'Em andamento', 'Em revisão', 'Contextos']}>
          {data.map((w) => (
            <Row key={w.person_id}>
              <Cell>{w.display_name}</Cell>
              <Cell className="tabular-nums">{w.wip}</Cell>
              <Cell className="tabular-nums">{w.em_andamento}</Cell>
              <Cell className="tabular-nums">{w.em_revisao}</Cell>
              <Cell className="tabular-nums">{w.contextos}</Cell>
            </Row>
          ))}
        </DataTable>
      </div>
    </Card>
  )
}

export function AgingBlock() {
  const { page, setPage, items, total, loading, limit } = usePagedMetric<Aging>('/api/metrics/aging')
  if (!loading && total === 0) return null
  return (
    <Card>
      <SectionTitle hint="há quanto tempo o card não muda de status">Cards parados</SectionTitle>
      <DataTable columns={['Tarefa', 'Status', 'Lista', 'Dias no status', 'Dias abertos']}>
        {items.map((a) => (
          <Row key={a.task_id}>
            <Cell>
              <TaskLink taskId={a.task_id} url={a.url} label={a.name} />
            </Cell>
            <Cell>
              <StatusBadge status={a.status_canonical} />
            </Cell>
            <Cell className="text-muted-foreground">{a.list_name}</Cell>
            <Cell className="tabular-nums">{num(a.days_in_status)}</Cell>
            <Cell className="tabular-nums">{num(a.days_open)}</Cell>
          </Row>
        ))}
      </DataTable>
      <TablePager page={page} limit={limit} total={total} onPage={setPage} />
    </Card>
  )
}

export function ReworkBlock({ data }: { data: Metrics['rework'] }) {
  if (!data.length) return null
  return (
    <Card>
      <SectionTitle hint="voltas da revisão para em andamento">Retrabalho</SectionTitle>
      <DataTable columns={['Tarefa', 'Retornos']}>
        {data.map((r) => (
          <Row key={r.task_id}>
            <Cell>
              <TaskLink taskId={r.task_id} url={r.url} label={r.name} />
            </Cell>
            <Cell className="tabular-nums">{r.returns_from_review}</Cell>
          </Row>
        ))}
      </DataTable>
    </Card>
  )
}

export function BlockChainBlock() {
  const { page, setPage, items, total, loading, limit } = usePagedMetric<BlockChain>(
    '/api/metrics/block-chain',
  )
  if (!loading && total === 0) return null
  return (
    <Card>
      <SectionTitle hint="dependências que travam outro card">Cadeia de bloqueios</SectionTitle>
      <DataTable columns={['De', 'Para', 'Pessoas', 'Descrição', 'Dias bloq.']}>
        {items.map((b) => (
          <Row key={b.id}>
            <Cell>
              {b.from_task_id ? (
                <TaskLink taskId={b.from_task_id} label={b.from_task_name || b.from_task_id} />
              ) : (
                <span className="text-muted-foreground">{b.from_task_name || '—'}</span>
              )}
            </Cell>
            <Cell>
              {b.to_task_id ? (
                <TaskLink taskId={b.to_task_id} label={b.to_task_name || b.to_task_id} />
              ) : (
                <span className="text-muted-foreground">{b.to_task_name || '—'}</span>
              )}
            </Cell>
            <Cell className="text-muted-foreground">
              {b.from_person} → {b.to_person}
            </Cell>
            <Cell className="text-muted-foreground">{b.description}</Cell>
            <Cell className="tabular-nums">{num(b.days_blocked)}</Cell>
          </Row>
        ))}
      </DataTable>
      <TablePager page={page} limit={limit} total={total} onPage={setPage} />
    </Card>
  )
}

export function PromisedBlock() {
  const { page, setPage, items, total, loading, limit } = usePagedMetric<Promised>(
    '/api/metrics/promised',
  )
  if (!loading && total === 0) return null
  return (
    <Card>
      <SectionTitle hint="prazo prometido vs data de conclusão">Prometido vs entregue</SectionTitle>
      <DataTable columns={['Tarefa', 'Fase', 'Status', 'Prazo', 'Fechado', 'Delta (d)']}>
        {items.map((p) => (
          <Row key={p.id}>
            <Cell>
              <TaskLink taskId={p.task_id} url={p.url} label={p.name} />
            </Cell>
            <Cell className="text-muted-foreground">{p.phase || '—'}</Cell>
            <Cell>
              <StatusBadge status={p.status_canonical} />
            </Cell>
            <Cell className="text-muted-foreground">{p.due_on || '—'}</Cell>
            <Cell className="text-muted-foreground">{p.closed_on || '—'}</Cell>
            <Cell
              className={
                p.days_delta != null && p.days_delta > 0
                  ? 'tabular-nums text-warn'
                  : 'tabular-nums text-success'
              }
            >
              {p.days_delta == null ? '—' : p.days_delta}
            </Cell>
          </Row>
        ))}
      </DataTable>
      <TablePager page={page} limit={limit} total={total} onPage={setPage} />
    </Card>
  )
}

export function HygieneBlock() {
  const { page, setPage, items, total, loading, limit } = usePagedMetric<HygieneIssue>(
    '/api/metrics/hygiene',
  )
  if (!loading && total === 0) return null
  return (
    <Card>
      <SectionTitle hint="cards sem dono, prioridade, contexto ou status padrão">
        Problemas de higiene
      </SectionTitle>
      <DataTable columns={['Tarefa', 'Status', 'Problemas']}>
        {items.map((h) => (
          <Row key={h.task_id}>
            <Cell>
              <TaskLink taskId={h.task_id} url={h.url} label={h.name} />
            </Cell>
            <Cell>
              <StatusBadge status={h.status_canonical} />
            </Cell>
            <Cell className="whitespace-normal">
              <span className="flex flex-wrap gap-1">
                {h.issues.map((iss) => (
                  <span
                    key={iss}
                    className="rounded bg-white/5 px-1.5 py-0.5 text-xs text-muted-foreground"
                  >
                    {HYGIENE_LABEL[iss] || iss}
                  </span>
                ))}
              </span>
            </Cell>
          </Row>
        ))}
      </DataTable>
      <TablePager page={page} limit={limit} total={total} onPage={setPage} />
    </Card>
  )
}

export function DuplicatesBlock() {
  const { page, setPage, items, total, loading, limit } = usePagedMetric<HygieneDuplicate>(
    '/api/metrics/duplicates',
  )
  if (!loading && total === 0) return null
  return (
    <Card>
      <SectionTitle>Possíveis duplicatas</SectionTitle>
      <DataTable columns={['Tarefa A', 'Tarefa B']}>
        {items.map((d, i) => (
          <Row key={i}>
            <Cell>
              <TaskLink taskId={d.task_a} url={d.url_a} label={d.name_a} />
            </Cell>
            <Cell>
              <TaskLink taskId={d.task_b} url={d.url_b} label={d.name_b} />
            </Cell>
          </Row>
        ))}
      </DataTable>
      <TablePager page={page} limit={limit} total={total} onPage={setPage} />
    </Card>
  )
}

export function MetricsSection({ metrics }: { metrics: Metrics }) {
  return (
    <div className="grid min-w-0 gap-4">
      <BottleneckBlock data={metrics.bottleneck} />
      <TimeInStatusBlock />
      <LeadCycleBlock />
      <WipBlock data={metrics.wip} />
      <AgingBlock />
      <ReworkBlock data={metrics.rework} />
      <BlockChainBlock />
      <PromisedBlock />
      <HygieneBlock />
      <DuplicatesBlock />
    </div>
  )
}

export { TablePager }

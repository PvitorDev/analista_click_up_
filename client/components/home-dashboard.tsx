'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { ArrowRight } from 'lucide-react'
import { api, fetchMetrics, STATUS_LABEL, toNum } from '@/lib/api'
import { deriveKpis } from '@/lib/kpi'
import { humanizeText } from '@/lib/humanize'
import { useMe } from '@/lib/me-context'
import { useTaskCatalog } from '@/lib/task-catalog'
import type { Metrics, Report } from '@/lib/types'
import { Card, EmptyState, PageLoader, SectionTitle } from './primitives'
import { KpiCard } from './kpi-card'
import { GenerateButton } from './generate-button'
import { BoardStatusCards } from './board-status-cards'
import { SyncButton } from './sync-button'
import { GroupedBar, SimpleBar, SimplePie } from './charts'

const AGING_ORDER: (0 | 7 | 14 | 30)[] = [0, 7, 14, 30]
const AGING_LABEL: Record<number, string> = {
  0: '< 7 dias',
  7: '7–13 dias',
  14: '14–29 dias',
  30: '30+ dias',
}

export function HomeDashboard() {
  const { me, people } = useMe()
  const { tasks } = useTaskCatalog()
  const isAdmin = me.role === 'admin'
  const [report, setReport] = useState<Report | null>(null)
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    ;(async () => {
      const [latest, m] = await Promise.all([
        api<Report | null>('/api/reports/latest').catch(() => null),
        fetchMetrics(),
      ])
      if (!active) return
      setReport(latest)
      setMetrics(m)
      setLoading(false)
    })()
    return () => {
      active = false
    }
  }, [])

  if (loading || !metrics) return <PageLoader />

  if (!report) {
    return (
      <div className="grid gap-6">
        <PageHeaderRow isAdmin={isAdmin} />
        {tasks.length ? <BoardStatusCards tasks={tasks} /> : null}
        <EmptyState
          title="É preciso gerar o primeiro relatório."
          description="Ainda não há diagnóstico disponível. Gere o primeiro relatório para ver o dashboard do board."
          action={
            <div className="flex flex-wrap justify-center gap-2">
              <GenerateButton />
              {isAdmin ? <SyncButton /> : null}
            </div>
          }
        />
      </div>
    )
  }

  const kpis = deriveKpis(report, metrics)

  const timeData = (metrics.timeInStatus.items || []).map((t) => ({
    label: STATUS_LABEL[t.status_canonical] || t.status_canonical,
    value: toNum(t.mediana_dias),
  }))

  const bottleneckData = [...metrics.bottleneck]
    .slice(0, 8)
    .map((b) => ({
      label: `${STATUS_LABEL[b.status_canonical] || b.status_canonical} · ${b.list_name}`,
      value: toNum(b.dias_acumulados),
    }))

  const leadCycleData = [...(metrics.leadCycle.items || [])]
    .slice(0, 8)
    .map((l) => ({
      label: l.list_name,
      lead: toNum(l.lead_mediana),
      cycle: toNum(l.cycle_mediana),
    }))

  const agingItems = metrics.aging.items || []
  const agingCounts = AGING_ORDER.map((bucket) => ({
    label: AGING_LABEL[bucket],
    value: agingItems.filter((a) => a.aging_bucket === bucket).length,
  })).filter((d) => d.value > 0)

  const wipData = [...metrics.wip]
    .sort((a, b) => b.wip - a.wip)
    .map((w) => ({ label: w.display_name, value: w.wip }))

  const teaser = humanizeText(report.narrative, tasks, people)
    .split(/\n\n+/)
    .map((p) => p.trim())
    .filter(Boolean)
    .slice(0, 3)
  const summary = humanizeText(report.history_summary, tasks, people)

  return (
    <div className="grid gap-8">
      <PageHeaderRow isAdmin={isAdmin} />

      {tasks.length ? <BoardStatusCards tasks={tasks} /> : null}

      <div className="grid min-w-0 grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-5">
        {kpis.map((k) => (
          <KpiCard key={k.label} {...k} />
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {timeData.length ? (
          <Card>
            <SectionTitle hint="mediana em dias">Tempo em cada status</SectionTitle>
            <SimpleBar data={timeData} color="#7b68ee" />
          </Card>
        ) : null}
        {bottleneckData.length ? (
          <Card>
            <SectionTitle hint="top 8 · dias acumulados">Gargalos</SectionTitle>
            <SimpleBar data={bottleneckData} color="#f97316" horizontal />
          </Card>
        ) : null}
        {leadCycleData.length ? (
          <Card>
            <SectionTitle hint="criação até concluir vs início do trabalho até concluir">
              Tempo de entrega
            </SectionTitle>
            <GroupedBar
              data={leadCycleData}
              keys={[
                { key: 'lead', name: 'Criação → fim', color: '#7b68ee' },
                { key: 'cycle', name: 'Início → fim', color: '#38bdf8' },
              ]}
            />
          </Card>
        ) : null}
        {agingCounts.length ? (
          <Card>
            <SectionTitle hint="há quanto tempo no mesmo status">Cards parados</SectionTitle>
            <SimplePie data={agingCounts} />
          </Card>
        ) : null}
        {wipData.length ? (
          <Card className="lg:col-span-2">
            <SectionTitle hint="quantos cards cada pessoa tem ao mesmo tempo">
              Trabalho em paralelo
            </SectionTitle>
            <SimpleBar data={wipData} color="#22c55e" horizontal />
          </Card>
        ) : null}
      </div>

      {teaser.length || report.history_summary ? (
        <Card>
          <div className="mb-3 flex items-center justify-between gap-3">
            <SectionTitle>Diagnóstico</SectionTitle>
            <Link
              href={`/relatorios/${report.id}`}
              className="flex shrink-0 items-center gap-1 text-sm font-medium text-primary hover:underline"
            >
              Ver relatório completo
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
          {report.history_summary ? (
            <p className="mb-4 break-words whitespace-pre-wrap rounded-lg bg-white/[0.03] p-3 text-sm leading-relaxed text-muted-foreground">
              {summary}
            </p>
          ) : null}
          <div className="grid min-w-0 gap-3">
            {teaser.map((p, i) => (
              <p key={i} className="break-words text-sm leading-relaxed text-foreground">
                {p}
              </p>
            ))}
          </div>
        </Card>
      ) : null}
    </div>
  )
}

function PageHeaderRow({ isAdmin }: { isAdmin: boolean }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Visão geral do board a partir do último diagnóstico.
        </p>
      </div>
      <div className="flex gap-2">
        {isAdmin ? <SyncButton /> : null}
        <GenerateButton />
      </div>
    </div>
  )
}

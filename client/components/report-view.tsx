'use client'

import { useState } from 'react'
import { fmtDateTime } from '@/lib/api'
import { humanizeText } from '@/lib/humanize'
import { useTaskCatalog } from '@/lib/task-catalog'
import { useMe } from '@/lib/me-context'
import type { Report, Metrics } from '@/lib/types'
import { Card, SectionTitle, TaskLink } from './primitives'
import { KpiCard } from './kpi-card'
import { MetricsSection, TablePager } from './metric-blocks'
import { deriveKpis } from '@/lib/kpi'

const EVIDENCE_PAGE = 5

function Anchor({ id }: { id: string }) {
  return <span id={id} className="block -translate-y-20" aria-hidden="true" />
}

export function ReportView({
  report,
  metrics,
}: {
  report: Report
  metrics: Metrics
}) {
  const { tasks } = useTaskCatalog()
  const { people } = useMe()
  const kpis = deriveKpis(report, metrics)
  const paragraphs = humanizeText(report.narrative, tasks, people)
    .split(/\n\n+/)
    .map((p) => p.trim())
    .filter(Boolean)
  const summary = humanizeText(report.history_summary, tasks, people)
  const [evPage, setEvPage] = useState(1)
  const evTotal = report.evidence?.length ?? 0
  const evSlice = (report.evidence || []).slice(
    (evPage - 1) * EVIDENCE_PAGE,
    evPage * EVIDENCE_PAGE,
  )

  return (
    <div className="grid min-w-0 gap-10">
      {/* 1. Resumo */}
      <section className="min-w-0">
        <Anchor id="resumo" />
        <div className="mb-4 min-w-0">
          <h1 className="text-balance break-words text-2xl font-semibold tracking-tight">
            {report.title}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Gerado em {fmtDateTime(report.created_at)}
            {report.generated_by ? ` · por ${report.generated_by}` : ''}
          </p>
        </div>

        {report.history_summary ? (
          <Card className="mb-4">
            <SectionTitle>Contexto do ciclo</SectionTitle>
            <p className="break-words whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">
              {summary}
            </p>
          </Card>
        ) : null}

        <div className="grid min-w-0 grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-5">
          {kpis.map((k) => (
            <KpiCard key={k.label} {...k} />
          ))}
        </div>
      </section>

      {/* 2. Diagnóstico */}
      {paragraphs.length ? (
        <section className="min-w-0">
          <Anchor id="diagnostico" />
          <SectionTitle>Diagnóstico</SectionTitle>
          <div className="grid min-w-0 gap-3">
            {paragraphs.map((p, i) => (
              <Card key={i}>
                <p className="break-words text-sm leading-relaxed text-foreground">{p}</p>
              </Card>
            ))}
          </div>
        </section>
      ) : null}

      {/* 3. Cinco mudanças */}
      {report.improvements?.length ? (
        <section className="min-w-0">
          <Anchor id="mudancas" />
          <SectionTitle hint="ordenadas por prioridade">Mudanças propostas</SectionTitle>
          <div className="grid gap-3">
            {report.improvements.map((imp, i) => (
              <Card key={i}>
                <div className="mb-3 flex items-start justify-between gap-3">
                  <h3 className="min-w-0 break-words text-base font-semibold text-foreground">
                    {i + 1}. {humanizeText(imp.problem, tasks, people)}
                  </h3>
                  <span className="shrink-0 rounded-md bg-[color:var(--accent-soft)] px-2 py-1 text-xs font-medium text-primary">
                    score {imp.score}
                  </span>
                </div>
                <dl className="grid gap-2 text-sm md:grid-cols-2">
                  <Field label="Impacto" value={humanizeText(imp.impact, tasks, people)} />
                  <Field label="Esforço" value={humanizeText(imp.effort, tasks, people)} />
                  <Field label="Quem decide" value={humanizeText(imp.decides, tasks, people)} />
                  <Field label="Ação" value={humanizeText(imp.action, tasks, people)} />
                </dl>
                {imp.task_ids?.length ? (
                  <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 border-t border-border pt-3">
                    {imp.task_ids.map((id) => (
                      <TaskLink key={id} taskId={id} />
                    ))}
                  </div>
                ) : null}
              </Card>
            ))}
          </div>
        </section>
      ) : null}

      {/* 4. Métricas */}
      <section className="min-w-0">
        <Anchor id="metricas" />
        <SectionTitle hint="números atuais do board">Métricas</SectionTitle>
        <MetricsSection metrics={metrics} />
      </section>

      {/* 5. Evidências */}
      {evTotal ? (
        <section className="min-w-0">
          <Anchor id="evidencias" />
          <SectionTitle>Evidências</SectionTitle>
          <Card>
            <ul className="grid gap-3">
              {evSlice.map((e, i) => (
                <li key={i} className="flex flex-col gap-1 border-b border-border pb-3 last:border-0 last:pb-0">
                  <span className="break-words text-sm text-foreground">
                    {humanizeText(e.claim, tasks, people)}
                  </span>
                  <TaskLink taskId={e.task_id} url={e.url} label={e.name} />
                </li>
              ))}
            </ul>
            <TablePager
              page={evPage}
              limit={EVIDENCE_PAGE}
              total={evTotal}
              onPage={setEvPage}
            />
          </Card>
        </section>
      ) : null}
    </div>
  )
}

function Field({ label, value }: { label: string; value: string }) {
  if (!value) return null
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd className="mt-0.5 break-words text-foreground">{value}</dd>
    </div>
  )
}

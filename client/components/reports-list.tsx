'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { ChevronRight } from 'lucide-react'
import { api, fmtDateTime } from '@/lib/api'
import type { ReportListItem } from '@/lib/types'
import { Card, EmptyState, PageLoader } from './primitives'
import { GenerateButton } from './generate-button'

export function ReportsList() {
  const [reports, setReports] = useState<ReportListItem[] | null>(null)

  useEffect(() => {
    let active = true
    api<ReportListItem[]>('/api/reports')
      .then((r) => active && setReports(r))
      .catch(() => active && setReports([]))
    return () => {
      active = false
    }
  }, [])

  if (reports === null) return <PageLoader />

  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Relatórios</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Histórico de diagnósticos, mais recente primeiro.
          </p>
        </div>
        <GenerateButton />
      </div>

      {reports.length === 0 ? (
        <EmptyState
          title="Nenhum relatório ainda."
          description="Gere o primeiro diagnóstico para começar."
          action={<GenerateButton />}
        />
      ) : (
        <Card className="p-0">
          <ul>
            {reports.map((r, i) => (
              <li key={r.id}>
                <Link
                  href={`/relatorios/${r.id}`}
                  className="flex items-center justify-between gap-3 border-b border-border px-5 py-4 transition-colors last:border-0 hover:bg-white/[0.02]"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="truncate font-medium text-foreground">
                        {r.title}
                      </span>
                      {i === 0 ? (
                        <span className="shrink-0 rounded bg-[color:var(--accent-soft)] px-1.5 py-0.5 text-xs font-medium text-primary">
                          atual
                        </span>
                      ) : null}
                    </div>
                    <span className="text-xs text-muted-foreground">
                      {fmtDateTime(r.created_at)}
                    </span>
                  </div>
                  <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  )
}

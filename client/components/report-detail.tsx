'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { api, fetchMetrics } from '@/lib/api'
import { useMe } from '@/lib/me-context'
import type { Metrics, Report } from '@/lib/types'
import { EmptyState, PageLoader } from './primitives'
import { ReportView } from './report-view'
import { SyncButton } from './sync-button'
import { GenerateButton } from './generate-button'

export function ReportDetail({ id }: { id: string }) {
  const { me } = useMe()
  const isAdmin = me.role === 'admin'
  const [report, setReport] = useState<Report | null>(null)
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [status, setStatus] = useState<'loading' | 'ready' | 'notfound'>('loading')

  useEffect(() => {
    let active = true
    ;(async () => {
      try {
        const [r, m] = await Promise.all([
          api<Report>(`/api/reports/${id}`),
          fetchMetrics(),
        ])
        if (!active) return
        setReport(r)
        setMetrics(m)
        setStatus('ready')
      } catch {
        if (active) setStatus('notfound')
      }
    })()
    return () => {
      active = false
    }
  }, [id])

  if (status === 'loading') return <PageLoader />

  if (status === 'notfound' || !report || !metrics) {
    return (
      <EmptyState
        title="Relatório não encontrado."
        description="O relatório solicitado não existe ou foi removido."
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

  return (
    <div className="grid min-w-0 gap-6">
      <div className="flex min-w-0 flex-wrap items-center justify-end gap-2">
        {isAdmin ? <SyncButton /> : null}
        <GenerateButton />
      </div>
      <ReportView key={report.id} report={report} metrics={metrics} />
    </div>
  )
}

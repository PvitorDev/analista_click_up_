import { num, STATUS_LABEL, toNum } from './api'
import type { Metrics, Report } from './types'

interface Kpi {
  label: string
  value: React.ReactNode
  sub?: string
  href?: string
  tone?: 'default' | 'accent' | 'success' | 'warn'
}

export function deriveKpis(report: Report | null, metrics: Metrics): Kpi[] {
  const top = metrics.bottleneck[0]
  const wipTotal = metrics.wip.reduce((acc, w) => acc + toNum(w.wip), 0)
  const aging30 = metrics.aging?.stale_30 ?? 0
  const hygieneCount = metrics.hygiene?.total ?? 0
  const improvements = report?.improvements.length ?? 0

  return [
    {
      label: 'Gargalo #1',
      value: top ? num(top.dias_acumulados) + ' d' : '—',
      sub: top ? `${STATUS_LABEL[top.status_canonical] || top.status_canonical} · ${top.list_name}` : 'sem dados',
      tone: 'warn',
    },
    {
      label: 'Em paralelo',
      value: wipTotal,
      sub: `${metrics.wip.length} pessoas`,
      tone: 'accent',
    },
    {
      label: 'Parados 30+ dias',
      value: aging30,
      sub: 'cards parados',
      tone: aging30 > 0 ? 'warn' : 'success',
    },
    {
      label: 'Higiene',
      value: hygieneCount,
      sub: 'itens com problema',
      tone: hygieneCount > 0 ? 'warn' : 'success',
    },
    {
      label: 'Mudanças',
      value: improvements,
      sub: 'propostas',
      href: report ? `/relatorios/${report.id}#mudancas` : undefined,
      tone: 'default',
    },
  ]
}

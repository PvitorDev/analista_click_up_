'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { toast } from 'react-toastify'
import { api, num } from '@/lib/api'
import { useMe } from '@/lib/me-context'
import type { Leaderboard } from '@/lib/types'
import { Card, EmptyState, PageLoader, SectionTitle } from './primitives'
import { DataTable, Row, Cell } from './data-table'
import { cn } from '@/lib/utils'

function Bar({ value, max, tone }: { value: number; max: number; tone: string }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0
  return (
    <span className="flex items-center gap-2">
      <span className="relative h-1.5 w-16 overflow-hidden rounded-full bg-white/8">
        <span
          className={cn('absolute inset-y-0 left-0 rounded-full', tone)}
          style={{ width: `${pct}%` }}
        />
      </span>
      <span className="tabular-nums">{value}</span>
    </span>
  )
}

export function LeaderboardView() {
  const { me } = useMe()
  const router = useRouter()
  const [tab, setTab] = useState<'fluxo' | 'entrega'>('fluxo')
  const [data, setData] = useState<Leaderboard | null>(null)
  const [status, setStatus] = useState<'loading' | 'ready' | 'unavailable'>('loading')

  useEffect(() => {
    if (me.role !== 'admin') {
      toast.info('Acesso restrito a administradores.')
      router.replace('/')
      return
    }
    let active = true
    api<Leaderboard>('/api/leaderboard')
      .then((d) => {
        if (active) {
          setData(d)
          setStatus('ready')
        }
      })
      .catch(() => {
        if (active) {
          setStatus('unavailable')
          toast.error('Leaderboard indisponível.')
        }
      })
    return () => {
      active = false
    }
  }, [me.role, router])

  if (me.role !== 'admin') return null
  if (status === 'loading') return <PageLoader />

  if (status === 'unavailable' || !data) {
    return (
      <div className="grid gap-6">
        <Header />
        <EmptyState
          title="Leaderboard indisponível"
          description="O ranking operacional ainda não está disponível no servidor."
        />
      </div>
    )
  }

  const fluxo = [...data.fluxo].sort((a, b) => b.wip - a.wip)
  const entrega = [...data.entrega].sort(
    (a, b) => b.cards_concluidos - a.cards_concluidos,
  )
  const maxWip = Math.max(1, ...fluxo.map((f) => f.wip))
  const maxCards = Math.max(1, ...entrega.map((e) => e.cards_concluidos))

  return (
    <div className="grid gap-6">
      <Header />

      <div className="flex gap-2">
        {(['fluxo', 'entrega'] as const).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={cn(
              'rounded-lg px-4 py-2 text-sm font-medium transition-colors',
              tab === t
                ? 'bg-[color:var(--accent-soft)] text-primary'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            {t === 'fluxo' ? 'Fluxo' : 'Entrega'}
          </button>
        ))}
      </div>

      {tab === 'fluxo' ? (
        <Card>
          <SectionTitle hint="ordenado por trabalho em paralelo">Fluxo</SectionTitle>
          {fluxo.length ? (
            <DataTable
              columns={['Pessoa', 'Em paralelo', 'Em andamento', 'Em revisão', 'Parados 7d', 'Parados 14d', 'Parados 30d']}
            >
              {fluxo.map((f) => (
                <Row key={f.person_id}>
                  <Cell>
                    <Link
                      href={`/perfil/${f.person_id}`}
                      className="text-foreground hover:text-primary hover:underline"
                    >
                      {f.display_name}
                    </Link>
                  </Cell>
                  <Cell>
                    <Bar value={f.wip} max={maxWip} tone="bg-primary" />
                  </Cell>
                  <Cell className="tabular-nums">{f.em_andamento}</Cell>
                  <Cell className="tabular-nums">{f.em_revisao}</Cell>
                  <Cell className="tabular-nums">{f.aging_7}</Cell>
                  <Cell className="tabular-nums">{f.aging_14}</Cell>
                  <Cell className="tabular-nums text-warn">{f.aging_30}</Cell>
                </Row>
              ))}
            </DataTable>
          ) : (
            <p className="text-sm text-muted-foreground">
              Sem dados de fluxo. O ranking aparece quando houver cards abertos com responsável.
            </p>
          )}
        </Card>
      ) : (
        <Card>
          <SectionTitle hint="ordenado por cards concluídos">Entrega</SectionTitle>
          {entrega.length ? (
            <DataTable
              columns={['Pessoa', 'Concluídos', 'Criação → fim (d)', 'Início → fim (d)', 'Marcos no prazo', 'Marcos atrasados', 'Atraso mediano (d)']}
            >
              {entrega.map((e) => (
                <Row key={e.person_id}>
                  <Cell>
                    <Link
                      href={`/perfil/${e.person_id}`}
                      className="text-foreground hover:text-primary hover:underline"
                    >
                      {e.display_name}
                    </Link>
                  </Cell>
                  <Cell>
                    <Bar value={e.cards_concluidos} max={maxCards} tone="bg-success" />
                  </Cell>
                  <Cell className="tabular-nums">{num(e.lead_mediana)}</Cell>
                  <Cell className="tabular-nums">{num(e.cycle_mediana)}</Cell>
                  <Cell className="tabular-nums text-success">{e.marcos_no_prazo}</Cell>
                  <Cell className="tabular-nums text-warn">{e.marcos_atrasados}</Cell>
                  <Cell className="tabular-nums">{num(e.atraso_mediano_dias)}</Cell>
                </Row>
              ))}
            </DataTable>
          ) : (
            <p className="text-sm text-muted-foreground">
              Sem dados de entrega. O ranking aparece quando houver cards concluídos com responsável.
            </p>
          )}
        </Card>
      )}
    </div>
  )
}

function Header() {
  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight">Ranking operacional</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Indicadores de fluxo e entrega por pessoa.
      </p>
    </div>
  )
}

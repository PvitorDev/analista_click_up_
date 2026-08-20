'use client'

import { useEffect, useState, type ReactNode } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { ShieldAlert } from 'lucide-react'
import { toast } from 'react-toastify'
import { api, num } from '@/lib/api'
import { useMe } from '@/lib/me-context'
import type { Profile } from '@/lib/types'
import { Card, EmptyState, PageLoader, SectionTitle, StatusBadge, TaskLink } from './primitives'
import { DataTable, Row, Cell } from './data-table'
import { GenerateButton } from './generate-button'

function TextSection({ title, value }: { title: string; value?: string | null }) {
  if (!value) return null
  return (
    <Card>
      <SectionTitle>{title}</SectionTitle>
      <p className="whitespace-pre-line text-sm leading-relaxed text-foreground">
        {value}
      </p>
    </Card>
  )
}

function hasContent(v: unknown): boolean {
  if (v == null) return false
  if (typeof v === 'string') return v.trim().length > 0
  if (Array.isArray(v)) return v.length > 0
  if (typeof v === 'object') return Object.keys(v as object).length > 0
  return true
}

export function ProfileView({ id }: { id: string }) {
  const { me } = useMe()
  const router = useRouter()
  const [data, setData] = useState<Profile | null>(null)
  const [status, setStatus] = useState<'loading' | 'ready' | 'notfound'>('loading')
  const ownProfile = String(me.clickup_user_id) === String(id)
  const allowed = me.role === 'admin' || ownProfile

  useEffect(() => {
    if (!allowed) {
      toast.info('Acesso restrito ao próprio perfil.')
      router.replace('/')
      return
    }
    let active = true
    api<Profile>(`/api/perfil/${id}`)
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
  }, [id, allowed, router])

  if (!allowed) return null
  if (status === 'loading') return <PageLoader />

  if (status === 'notfound' || !data) {
    return (
      <EmptyState
        title="Perfil não encontrado."
        description="A pessoa solicitada não existe ou você não tem acesso."
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

  const { member, profile, wip, aging, collaboration_out, collaboration_in, viewing_as_admin } = data

  return (
    <div className="grid gap-6">
      {viewing_as_admin ? (
        <div className="flex items-center gap-2 rounded-lg border border-[color:var(--accent)]/30 bg-[color:var(--accent-soft)] px-4 py-3 text-sm text-primary">
          <ShieldAlert className="h-4 w-4 shrink-0" />
          Você está vendo o perfil de {member.display_name} como administrador.
        </div>
      ) : null}

      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{member.display_name}</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          @{member.username}
          {member.email ? ` · ${member.email}` : ''}
        </p>
      </div>

      {wip ? (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Stat label="Em paralelo" value={wip.wip} />
          <Stat label="Em andamento" value={wip.em_andamento} />
          <Stat label="Em revisão" value={wip.em_revisao} />
          <Stat label="Contextos" value={wip.contextos} />
        </div>
      ) : null}

      {profile ? (
        <div className="grid gap-4">
          <TextSection title="Pontos fortes" value={profile.strengths} />
          <TextSection title="Alavancagem" value={profile.leverage} />
          <TextSection title="Próximo passo" value={profile.next_step} />
          <TextSection title="Consistência" value={profile.consistency} />
          <TextSection title="Autonomia" value={profile.autonomy} />
          <TextSection title="Carga" value={profile.load_note} />
          {hasContent(profile.domains) ? (
            <Card>
              <SectionTitle>Domínios</SectionTitle>
              <StructuredValue value={profile.domains} />
            </Card>
          ) : null}
          {hasContent(profile.knowledge_concentration) ? (
            <Card>
              <SectionTitle>Concentração de conhecimento</SectionTitle>
              <StructuredValue value={profile.knowledge_concentration} />
            </Card>
          ) : null}
          {hasContent(profile.communication) ? (
            <Card>
              <SectionTitle>Comunicação</SectionTitle>
              <StructuredValue value={profile.communication} />
            </Card>
          ) : null}
        </div>
      ) : (
        <EmptyState
          title="Perfil ainda não gerado."
          description="Gere um relatório para produzir o perfil desta pessoa."
          action={ownProfile ? <GenerateButton /> : undefined}
        />
      )}

      {collaboration_out?.length ? (
        <Card>
          <SectionTitle>Comenta no trabalho de</SectionTitle>
          <DataTable columns={['Pessoa', 'Comentários']}>
            {collaboration_out.map((c, i) => (
              <Row key={i}>
                <Cell>{c.owner_name || c.owner_username}</Cell>
                <Cell className="tabular-nums">{c.comments}</Cell>
              </Row>
            ))}
          </DataTable>
        </Card>
      ) : null}

      {collaboration_in?.length ? (
        <Card>
          <SectionTitle>Recebe comentários de</SectionTitle>
          <DataTable columns={['Pessoa', 'Comentários']}>
            {collaboration_in.map((c, i) => (
              <Row key={i}>
                <Cell>{c.commenter_name || c.commenter_username}</Cell>
                <Cell className="tabular-nums">{c.comments}</Cell>
              </Row>
            ))}
          </DataTable>
        </Card>
      ) : null}

      {aging?.length ? (
        <Card>
          <SectionTitle>Cards parados</SectionTitle>
          <DataTable columns={['Tarefa', 'Status', 'Dias no status']}>
            {aging.map((a) => (
              <Row key={a.task_id}>
                <Cell>
                  <TaskLink taskId={a.task_id} url={a.url} label={a.name} />
                </Cell>
                <Cell>
                  <StatusBadge status={a.status_canonical} />
                </Cell>
                <Cell className="tabular-nums">{num(a.days_in_status)}</Cell>
              </Row>
            ))}
          </DataTable>
        </Card>
      ) : null}
    </div>
  )
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </span>
      <p className="mt-1 text-2xl font-semibold tabular-nums text-foreground">{value}</p>
    </div>
  )
}

const FIELD_LABELS: Record<string, string> = {
  risco: 'Risco',
  bus_factor: 'Pessoas críticas',
  observacao: 'Observação',
  contextos_ativos: 'Contextos ativos',
  listas_exclusivas: 'Listas exclusivas',
  cobertura_percentual: 'Cobertura',
  nomeacao: 'Nomeação',
  status_confiavel: 'Status confiável',
  contexto_em_tarefas: 'Contexto nas tarefas',
  prioridade_declarada: 'Prioridade declarada',
  domains: 'Domínios',
  communication: 'Comunicação',
  collaboration: 'Colaboração',
}

const FIELD_HINTS: Record<string, string> = {
  bus_factor:
    'Quantas pessoas precisariam sair para o conhecimento se perder. 1 = só uma pessoa segura esse domínio.',
}

function humanizeKey(key: string): string {
  if (FIELD_LABELS[key]) return FIELD_LABELS[key]
  return key.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase())
}

function parseMaybeJson(value: unknown): unknown {
  if (typeof value !== 'string') return value
  const trimmed = value.trim()
  if (!trimmed.startsWith('{') && !trimmed.startsWith('[')) return value
  try {
    return JSON.parse(trimmed)
  } catch {
    return value
  }
}

function Chip({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-md border border-border bg-white/[0.04] px-2.5 py-1 text-xs font-medium text-foreground">
      {children}
    </span>
  )
}

function RiskBadge({ value }: { value: string }) {
  const v = value.toLowerCase()
  const tone =
    v.includes('alto') || v.includes('high')
      ? 'bg-[#f97316]/15 text-warn'
      : v.includes('médio') || v.includes('medio') || v.includes('medium')
        ? 'bg-[#f97316]/10 text-warn'
        : v.includes('baixo') || v.includes('low')
          ? 'bg-[#22c55e]/15 text-success'
          : 'bg-white/5 text-muted-foreground'
  return (
    <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium capitalize ${tone}`}>
      {value}
    </span>
  )
}

function formatScalar(key: string | undefined, value: unknown): ReactNode {
  if (typeof value === 'boolean') return value ? 'Sim' : 'Não'
  if (typeof value === 'number') {
    if (key?.includes('percent')) return `${value}%`
    return String(value)
  }
  if (typeof value === 'string') {
    if (key === 'risco') return <RiskBadge value={value} />
    return value
  }
  return String(value)
}

function StructuredValue({
  value,
  nested = false,
}: {
  value: unknown
  nested?: boolean
}) {
  const parsed = parseMaybeJson(value)

  if (parsed == null || parsed === '') return null

  if (typeof parsed === 'string' || typeof parsed === 'number' || typeof parsed === 'boolean') {
    return (
      <p className="text-sm leading-relaxed text-foreground">
        {formatScalar(undefined, parsed)}
      </p>
    )
  }

  if (Array.isArray(parsed)) {
    if (parsed.length === 0) return null
    const primitives = parsed.every(
      (item) => item == null || ['string', 'number', 'boolean'].includes(typeof item),
    )
    if (primitives) {
      return (
        <div className="flex flex-wrap gap-2">
          {parsed.map((item, i) => (
            <Chip key={i}>{String(item)}</Chip>
          ))}
        </div>
      )
    }
    return (
      <div className="grid gap-3">
        {parsed.map((item, i) => (
          <div key={i} className="rounded-lg border border-border bg-white/[0.03] p-3">
            <StructuredValue value={item} nested />
          </div>
        ))}
      </div>
    )
  }

  if (typeof parsed === 'object') {
    const entries = Object.entries(parsed as Record<string, unknown>).filter(([, v]) =>
      hasContent(v),
    )
    if (!entries.length) return null
    return (
      <dl className={nested ? 'grid gap-3' : 'grid gap-4'}>
        {entries.map(([key, val]) => {
          const inner = parseMaybeJson(val)
          const isLongText = typeof inner === 'string' && inner.length > 80
          return (
            <div key={key} className="grid gap-1.5">
              <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {humanizeKey(key)}
              </dt>
              {FIELD_HINTS[key] ? (
                <p className="text-xs leading-relaxed text-muted-foreground/80">
                  {FIELD_HINTS[key]}
                </p>
              ) : null}
              <dd>
                {typeof inner === 'string' || typeof inner === 'number' || typeof inner === 'boolean' ? (
                  <p
                    className={
                      isLongText
                        ? 'text-sm leading-relaxed text-foreground'
                        : 'text-sm text-foreground'
                    }
                  >
                    {formatScalar(key, inner)}
                  </p>
                ) : (
                  <StructuredValue value={inner} nested />
                )}
              </dd>
            </div>
          )
        })}
      </dl>
    )
  }

  return null
}

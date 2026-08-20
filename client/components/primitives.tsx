import Link from 'next/link'
import { ExternalLink } from 'lucide-react'
import { cn } from '@/lib/utils'
import { STATUS_LABEL } from '@/lib/api'
import type { StatusCanonical } from '@/lib/types'
import { useTaskCatalog, useTaskName } from '@/lib/task-catalog'

export function Card({
  className,
  children,
}: {
  className?: string
  children: React.ReactNode
}) {
  return (
    <div
      className={cn(
        'min-w-0 overflow-hidden rounded-xl border border-border bg-card p-5',
        className,
      )}
    >
      {children}
    </div>
  )
}

export function SectionTitle({
  children,
  hint,
}: {
  children: React.ReactNode
  hint?: string
}) {
  return (
    <div className="mb-3 flex min-w-0 items-baseline justify-between gap-3">
      <h2 className="min-w-0 text-lg font-semibold tracking-tight text-foreground">
        {children}
      </h2>
      {hint ? (
        <span className="shrink-0 text-right text-xs text-muted-foreground">{hint}</span>
      ) : null}
    </div>
  )
}

export function Spinner({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        'inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent',
        className,
      )}
      aria-hidden="true"
    />
  )
}

export function PageLoader({ label = 'Carregando…' }: { label?: string }) {
  return (
    <div className="flex min-h-[40vh] flex-col items-center justify-center gap-3 text-muted-foreground">
      <Spinner className="h-6 w-6 text-primary" />
      <span className="text-sm">{label}</span>
    </div>
  )
}

const STATUS_STYLES: Record<string, string> = {
  A_FAZER: 'bg-white/5 text-muted-foreground',
  EM_ANDAMENTO: 'bg-[color:var(--accent-soft)] text-primary',
  EM_REVISAO: 'bg-[#f97316]/15 text-warn',
  CONCLUIDO: 'bg-[#22c55e]/15 text-success',
  BLOQUEADO: 'bg-[#f97316]/20 text-warn',
  OUTRO: 'bg-white/5 text-muted-foreground',
}

export function StatusBadge({ status }: { status: StatusCanonical | string }) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium',
        STATUS_STYLES[status] || STATUS_STYLES.OUTRO,
      )}
    >
      {STATUS_LABEL[status] || status}
    </span>
  )
}

export function TaskLink({
  taskId,
  url,
  label,
  className,
}: {
  taskId: string
  url?: string | null
  label?: string
  className?: string
}) {
  const { byId } = useTaskCatalog()
  const name = useTaskName(taskId, label)
  const hrefUrl = url || byId.get(taskId)?.url
  const isIdOnly = name === taskId
  return (
    <span className={cn('flex min-w-0 max-w-full flex-wrap items-start gap-x-2 gap-y-1', className)}>
      <Link
        href={`/tasks/${taskId}`}
        className={cn(
          'min-w-0 break-all text-sm text-primary underline-offset-2 hover:underline',
          isIdOnly && 'font-mono',
        )}
      >
        {name}
      </Link>
      {hrefUrl ? (
        <a
          href={hrefUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-0.5 text-xs text-muted-foreground hover:text-foreground"
        >
          ClickUp
          <ExternalLink className="h-3 w-3" />
        </a>
      ) : null}
    </span>
  )
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string
  description?: string
  action?: React.ReactNode
}) {
  return (
    <Card className="flex flex-col items-center justify-center gap-3 py-14 text-center">
      <h3 className="text-base font-medium text-foreground">{title}</h3>
      {description ? (
        <p className="max-w-md text-sm text-muted-foreground">{description}</p>
      ) : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </Card>
  )
}

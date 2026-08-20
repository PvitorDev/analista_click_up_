import type { ReactNode } from 'react'
import Link from 'next/link'
import { cn } from '@/lib/utils'

export function KpiCard({
  label,
  value,
  sub,
  href,
  onClick,
  tone = 'default',
}: {
  label: string
  value: ReactNode
  sub?: string
  href?: string
  onClick?: () => void
  tone?: 'default' | 'accent' | 'success' | 'warn'
}) {
  const toneClass = {
    default: 'text-foreground',
    accent: 'text-primary',
    success: 'text-success',
    warn: 'text-warn',
  }[tone]

  const clickable = Boolean(href || onClick)

  const body = (
    <div
      className={cn(
        'flex h-full min-w-0 flex-col gap-1 overflow-hidden rounded-xl border border-border bg-card p-4 transition-colors',
        clickable && 'hover:border-[color:var(--accent)]/40 hover:bg-white/[0.02]',
      )}
    >
      <span className="text-xs font-medium uppercase leading-tight tracking-wide text-muted-foreground">
        {label}
      </span>
      <span className={cn('break-words text-xl font-semibold tabular-nums sm:text-2xl', toneClass)}>
        {value}
      </span>
      {sub ? (
        <span className="mt-auto break-words text-xs text-muted-foreground">{sub}</span>
      ) : null}
    </div>
  )

  if (onClick) {
    return (
      <button type="button" onClick={onClick} className="block h-full min-w-0 w-full cursor-pointer text-left">
        {body}
      </button>
    )
  }

  if (href) {
    return (
      <Link href={href} className="block h-full min-w-0">
        {body}
      </Link>
    )
  }
  return body
}

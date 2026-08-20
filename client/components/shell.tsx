'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { LogOut, Home, FileText, Trophy, User } from 'lucide-react'
import { toast } from 'react-toastify'
import { API_URL } from '@/lib/api'
import { useMe } from '@/lib/me-context'
import { ClickUpMark } from './clickup-logo'
import { SyncButton } from './sync-button'
import { GenerateButton } from './generate-button'
import { WorkspaceSwitcher } from './workspace-switcher'
import { cn } from '@/lib/utils'

function NavItem({
  href,
  label,
  icon: Icon,
  active,
}: {
  href: string
  label: string
  icon: React.ComponentType<{ className?: string }>
  active: boolean
}) {
  return (
    <Link
      href={href}
      className={cn(
        'flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
        active
          ? 'bg-[color:var(--accent-soft)] text-primary'
          : 'text-muted-foreground hover:bg-[color:var(--accent-soft)] hover:text-foreground',
      )}
    >
      <Icon className="h-4 w-4" />
      {label}
    </Link>
  )
}

export function Shell({ children }: { children: React.ReactNode }) {
  const { me } = useMe()
  const pathname = usePathname()
  const router = useRouter()
  const isAdmin = me.role === 'admin'

  async function logout() {
    try {
      await fetch(`${API_URL}/auth/logout`, {
        method: 'POST',
        credentials: 'include',
      })
      toast.success('Sessão encerrada.')
    } catch {
      toast.error('Falha ao encerrar sessão.')
    } finally {
      router.push('/login')
    }
  }

  const nav = [
    { href: '/', label: 'Home', icon: Home, active: pathname === '/' },
    {
      href: '/relatorios',
      label: 'Relatórios',
      icon: FileText,
      active: pathname.startsWith('/relatorios'),
    },
    ...(isAdmin
      ? [
          {
            href: '/leaderboard',
            label: 'Leaderboard',
            icon: Trophy,
            active: pathname.startsWith('/leaderboard'),
          },
        ]
      : []),
    {
      href: `/perfil/${me.clickup_user_id}`,
      label: 'Meu perfil',
      icon: User,
      active: pathname === `/perfil/${me.clickup_user_id}`,
    },
  ]

  return (
    <div className="flex min-h-0 min-w-0 flex-1 overflow-hidden bg-background">
      {/* Sidebar */}
      <aside className="hidden h-full w-64 shrink-0 flex-col overflow-y-auto border-r border-border bg-chrome px-4 py-6 md:flex">
        <Link href="/" className="mb-8 flex items-center gap-2 px-1">
          <ClickUpMark className="h-7 w-7" />
          <span className="text-base font-semibold tracking-tight">Analista</span>
        </Link>

        <div className="mb-6 rounded-lg border border-border bg-card px-3 py-3">
          <p className="truncate text-sm font-medium text-foreground">
            {me.username || me.email || me.clickup_user_id}
          </p>
          <p className="mt-0.5 text-xs capitalize text-muted-foreground">
            {me.role === 'admin' ? 'Administrador' : 'Membro'}
          </p>
        </div>

        {isAdmin ? (
          <div className="mb-6 flex flex-col gap-2">
            <SyncButton />
            <GenerateButton variant="ghost" />
          </div>
        ) : (
          <div className="mb-6">
            <GenerateButton variant="ghost" />
          </div>
        )}

        <div className="mt-auto">
          <button
            type="button"
            onClick={logout}
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-[color:var(--accent-soft)] hover:text-foreground"
          >
            <LogOut className="h-4 w-4" />
            Sair
          </button>
        </div>
      </aside>

      {/* Main column */}
      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <header className="z-50 flex shrink-0 items-center gap-3 border-b border-border bg-chrome px-4 py-3">
          <div className="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto">
            {nav.map((n) => (
              <NavItem key={n.href} {...n} />
            ))}
          </div>
          <WorkspaceSwitcher />
        </header>
        <main className="min-h-0 min-w-0 flex-1 overflow-x-hidden overflow-y-auto px-4 py-6 pb-24 md:px-8">
          <div className="mx-auto w-full min-w-0 max-w-[1200px]">{children}</div>
        </main>
      </div>
    </div>
  )
}

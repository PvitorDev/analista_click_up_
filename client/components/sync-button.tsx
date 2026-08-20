'use client'

import { useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { toast } from 'react-toastify'
import { api } from '@/lib/api'
import { Spinner } from './primitives'
import { cn } from '@/lib/utils'

interface SyncResult {
  sync: {
    spaces: number
    lists: number
    tasks: number
    team_id: string
    team_name: string
  }
}

export function SyncButton({
  variant = 'ghost',
  onDone,
}: {
  variant?: 'ghost' | 'solid'
  onDone?: () => void
}) {
  const [loading, setLoading] = useState(false)

  async function run() {
    setLoading(true)
    try {
      const res = await api<SyncResult>('/api/sync', { method: 'POST' })
      toast.success(
        `Sincronizado: ${res.sync.tasks} tarefas · ${res.sync.team_name}`,
      )
      onDone?.()
    } catch {
      /* toast handled in api() */
    } finally {
      setLoading(false)
    }
  }

  return (
    <button
      type="button"
      onClick={run}
      disabled={loading}
      className={cn(
        'flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors disabled:opacity-60',
        variant === 'solid'
          ? 'bg-primary text-primary-foreground hover:opacity-90'
          : 'border border-border text-foreground hover:bg-[color:var(--accent-soft)]',
      )}
    >
      {loading ? <Spinner /> : <RefreshCw className="h-4 w-4" />}
      Sincronizar ClickUp
    </button>
  )
}

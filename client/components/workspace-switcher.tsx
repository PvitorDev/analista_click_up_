'use client'

import { useEffect, useRef, useState } from 'react'
import { Check, ChevronDown } from 'lucide-react'
import { toast } from 'react-toastify'
import { api } from '@/lib/api'
import { writeStoredWorkspaceId } from '@/lib/workspace'
import { Spinner } from './primitives'
import { cn } from '@/lib/utils'

interface Workspace {
  id: string
  name: string
}

interface WorkspacesResponse {
  workspaces: Workspace[]
  selected: Workspace | null
}

export function WorkspaceSwitcher() {
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState<Workspace[]>([])
  const [selected, setSelected] = useState<Workspace | null>(null)
  const [loading, setLoading] = useState(true)
  const [switching, setSwitching] = useState(false)
  const rootRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    let active = true
    api<WorkspacesResponse>('/api/workspaces', { silent: true })
      .then((res) => {
        if (!active) return
        const list = res.workspaces || []
        setItems(list)
        const current = res.selected || list[0] || null
        setSelected(current)
        if (current?.id) writeStoredWorkspaceId(current.id)
      })
      .catch(() => {
        if (active) setItems([])
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false)
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDoc)
      document.removeEventListener('keydown', onKey)
    }
  }, [])

  async function choose(ws: Workspace) {
    if (switching || ws.id === selected?.id) {
      setOpen(false)
      return
    }
    setSwitching(true)
    setOpen(false)
    writeStoredWorkspaceId(ws.id)
    const toastId = toast.loading(`Trocando para ${ws.name}…`)
    const ctrl = new AbortController()
    const timer = window.setTimeout(() => ctrl.abort(), 90000)
    try {
      await api('/api/workspaces/select', {
        method: 'POST',
        body: JSON.stringify({ team_id: ws.id }),
        signal: ctrl.signal,
        silent: true,
      })
      clearTimeout(timer)
      toast.update(toastId, {
        render: `Workspace: ${ws.name}`,
        type: 'success',
        isLoading: false,
        autoClose: 2500,
      })
      window.location.reload()
    } catch {
      clearTimeout(timer)
      toast.update(toastId, {
        render: 'Não foi possível trocar de workspace. Tente de novo.',
        type: 'error',
        isLoading: false,
        autoClose: 4000,
      })
      setSwitching(false)
    }
  }

  const label = selected?.name || (loading ? 'Workspace' : 'Sem workspace')

  return (
    <div ref={rootRef} className="relative ml-auto shrink-0">
      <button
        type="button"
        disabled={loading || switching || items.length === 0}
        onClick={() => setOpen((v) => !v)}
        className={cn(
          'flex max-w-[16rem] items-center gap-2 rounded-lg border border-border bg-card px-3 py-1.5 text-sm font-medium text-foreground transition-colors',
          'hover:bg-white/[0.04] disabled:opacity-60',
        )}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        {switching ? <Spinner /> : null}
        <span className="truncate">{label}</span>
        <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
      </button>
      {open ? (
        <ul
          role="listbox"
          className="absolute right-0 z-[100] mt-2 max-h-72 min-w-[16rem] overflow-auto rounded-xl border border-border bg-chrome py-1 shadow-2xl"
        >
          {items.map((ws) => {
            const active = ws.id === selected?.id
            return (
              <li key={ws.id}>
                <button
                  type="button"
                  role="option"
                  aria-selected={active}
                  onClick={() => choose(ws)}
                  className={cn(
                    'flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm hover:bg-white/[0.04]',
                    active ? 'text-primary' : 'text-foreground',
                  )}
                >
                  <span className="truncate">{ws.name}</span>
                  {active ? <Check className="h-4 w-4 shrink-0" /> : null}
                </button>
              </li>
            )
          })}
        </ul>
      ) : null}
    </div>
  )
}

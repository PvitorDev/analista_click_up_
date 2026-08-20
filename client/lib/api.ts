import { toast } from 'react-toastify'
import type { Metrics } from './types'

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

/** Base WS URL derived from API_URL (http->ws, https->wss). */
export function wsUrl(path: string): string {
  const base = API_URL.replace(/^http/, 'ws')
  return `${base}${path}`
}

/** Full-page navigation to start the OAuth flow. NEVER call via fetch. */
export function goToLogin() {
  window.location.href = `${API_URL}/auth/login`
}

class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

/**
 * Fetch helper for the FastAPI backend.
 * - Always sends the session cookie (credentials: include).
 * - 401 -> go to the Next /login route (never trigger OAuth here).
 * - 403 -> toast "Acesso negado" and throw.
 * - Other errors -> toast the body text and throw.
 */
export async function api<T = unknown>(
  path: string,
  init: RequestInit & { silent?: boolean } = {},
): Promise<T> {
  const { silent, ...fetchInit } = init
  let res: Response
  try {
    res = await fetch(`${API_URL}${path}`, {
      credentials: 'include',
      ...fetchInit,
      headers: {
        'Content-Type': 'application/json',
        ...(fetchInit.headers || {}),
      },
    })
  } catch {
    if (!silent) toast.error('Falha de rede ao contatar o servidor.')
    throw new ApiError(0, 'network')
  }

  if (res.status === 401) {
    if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
      window.location.href = '/login'
    }
    throw new ApiError(401, 'não autenticado')
  }

  if (res.status === 403) {
    if (!silent) toast.error('Acesso negado.')
    throw new ApiError(403, 'acesso negado')
  }

  if (res.status === 204) {
    return null as T
  }

  if (!res.ok) {
    let detail = `Erro ${res.status}`
    try {
      const text = await res.text()
      if (text) {
        try {
          const j = JSON.parse(text)
          detail = j.detail || text
        } catch {
          detail = text
        }
      }
    } catch {
      /* ignore */
    }
    if (!silent) toast.error(detail)
    throw new ApiError(res.status, detail)
  }

  return (await res.json()) as T
}

export { ApiError }

/** Format decimals that may arrive as string (Postgres numeric). */
export function num(v: number | string | null | undefined, digits = 1): string {
  if (v === null || v === undefined || v === '') return '—'
  const n = Number(v)
  if (Number.isNaN(n)) return '—'
  return n.toLocaleString('pt-BR', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

export function toNum(v: number | string | null | undefined): number {
  const n = Number(v)
  return Number.isNaN(n) ? 0 : n
}

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleDateString('pt-BR')
}

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString('pt-BR')
}

const emptyPage = { items: [], total: 0 }
const emptyAging = { items: [], total: 0, stale_30: 0 }

/** Fetch board metrics in parallel. Paged endpoints use page=1&limit=8 for charts/KPIs. */
export async function fetchMetrics(): Promise<Metrics> {
  const safe = async <T>(p: string, fallback: T): Promise<T> => {
    try {
      return await api<T>(p, { silent: true })
    } catch {
      return fallback
    }
  }
  const [
    bottleneck,
    timeInStatus,
    wip,
    aging,
    leadCycle,
    rework,
    hygiene,
    duplicates,
  ] = await Promise.all([
    safe('/api/metrics/bottleneck', []),
    safe('/api/metrics/time-in-status?page=1&limit=8', emptyPage),
    safe('/api/metrics/wip', []),
    safe('/api/metrics/aging?page=1&limit=8', emptyAging),
    safe('/api/metrics/lead-cycle?page=1&limit=8', emptyPage),
    safe('/api/metrics/rework', []),
    safe('/api/metrics/hygiene?page=1&limit=8', emptyPage),
    safe('/api/metrics/duplicates?page=1&limit=8', emptyPage),
  ])
  return {
    bottleneck,
    timeInStatus,
    wip,
    aging,
    leadCycle,
    rework,
    hygiene,
    duplicates,
    blockChain: emptyPage,
    promised: emptyPage,
  } as Metrics
}

export const STATUS_LABEL: Record<string, string> = {
  A_FAZER: 'A fazer',
  EM_ANDAMENTO: 'Em andamento',
  EM_REVISAO: 'Em revisão',
  CONCLUIDO: 'Concluído',
  BLOQUEADO: 'Bloqueado',
  OUTRO: 'Outro',
}

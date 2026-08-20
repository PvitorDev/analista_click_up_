import { STATUS_LABEL } from './api'
import type { Person } from './types'

export const HYGIENE_LABEL: Record<string, string> = {
  sem_assignee: 'sem responsável',
  sem_prioridade: 'sem prioridade',
  sem_contexto: 'sem contexto',
  status_divergente: 'status fora do padrão',
  sem_semantica: 'título genérico',
  multi_assignee: 'vários responsáveis',
  subtask_orfa: 'subtarefa órfã',
}

const TERM_REPLACEMENTS: Array<[RegExp, string]> = [
  [/\blead_cycle\b/gi, 'tempo de entrega'],
  [/\blead_mediana\b/gi, 'tempo mediano da criação até concluir'],
  [/\bcycle_mediana\b/gi, 'tempo mediano desde que o trabalho começou até concluir'],
  [/\btime_in_status\b/gi, 'tempo em cada status'],
  [/\bdays_in_status\b/gi, 'dias no status atual'],
  [/\bstatus_canonical\b/gi, 'status padronizado'],
  [/\bstatus_raw\b/gi, 'status original no ClickUp'],
  [/\bbus[_\s-]?factor\b/gi, 'pessoas críticas'],
  [/\bcobertura_percentual\b/gi, 'cobertura'],
  [/\bcontextos_ativos\b/gi, 'contextos ativos'],
  [/\blistas_exclusivas\b/gi, 'listas exclusivas'],
  [/\bsem_assignee\b/gi, 'sem responsável'],
  [/\bsem_prioridade\b/gi, 'sem prioridade'],
  [/\bsem_contexto\b/gi, 'sem contexto'],
  [/\bstatus_divergente\b/gi, 'status fora do padrão'],
  [/\bsem_semantica\b/gi, 'título genérico'],
  [/\bmulti_assignee\b/gi, 'vários responsáveis'],
  [/\bclickup_id\b/gi, 'id'],
  [/\bcustom_id\b/gi, 'id'],
  [/\bWIP\b/g, 'trabalho em paralelo'],
  [/\bp85\b/gi, 'casos mais lentos'],
  [/\brework\b/gi, 'retrabalho'],
  [/\baging\b/gi, 'cards parados'],
]

export type TaskRef = {
  clickup_id: string
  custom_id?: string | null
  name: string
  url?: string | null
  status_canonical?: string
  status_raw?: string | null
}

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/** Turns agent jargon / ids in stored reports into readable Portuguese. */
export function humanizeText(
  text: string | null | undefined,
  tasks: TaskRef[] = [],
  people: Person[] = [],
): string {
  if (!text) return ''
  let out = text

  const ids: Array<{ id: string; name: string }> = []
  for (const t of tasks) {
    if (t.clickup_id) ids.push({ id: t.clickup_id, name: t.name })
    if (t.custom_id) ids.push({ id: t.custom_id, name: t.name })
  }
  for (const p of people) {
    const name = p.display_name || p.username || p.clickup_id
    if (p.clickup_id) ids.push({ id: p.clickup_id, name })
  }
  ids.sort((a, b) => b.id.length - a.id.length)

  for (const { id, name } of ids) {
    if (!id || id.length < 5) continue
    const esc = escapeRegExp(id)
    out = out.replace(new RegExp(`\\s*\\(\\s*${esc}\\s*\\)`, 'g'), '')
    out = out.replace(new RegExp(`\\b${esc}\\b`, 'g'), name)
  }

  for (const [code, label] of Object.entries(STATUS_LABEL)) {
    out = out.replace(new RegExp(`\\b${code}\\b`, 'g'), label)
  }

  for (const [re, label] of TERM_REPLACEMENTS) {
    out = out.replace(re, label)
  }

  return out.replace(/[ \t]{2,}/g, ' ').replace(/ \)/g, ')').trim()
}

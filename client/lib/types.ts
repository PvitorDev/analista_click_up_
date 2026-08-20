export type Role = 'admin' | 'member'

export type StatusCanonical =
  | 'A_FAZER'
  | 'EM_ANDAMENTO'
  | 'EM_REVISAO'
  | 'CONCLUIDO'
  | 'BLOQUEADO'
  | 'OUTRO'

export interface Me {
  clickup_user_id: string
  role: Role
  username?: string | null
  email?: string | null
}

export interface Person {
  clickup_id: string
  username: string
  display_name: string
  email: string
}

export interface Improvement {
  problem: string
  impact: string
  effort: string
  action: string
  decides: string
  score: number
  task_ids: string[]
}

export interface Evidence {
  claim: string
  task_id: string
  name?: string
  url: string
}

export interface Report {
  id: number
  title: string
  created_at: string
  narrative: string
  history_summary: string
  improvements: Improvement[]
  evidence: Evidence[]
  generated_by: string | null
}

export interface ReportListItem {
  id: number
  title: string
  created_at: string
}

export interface Bottleneck {
  status_canonical: StatusCanonical
  list_id: string
  list_name: string
  dias_acumulados: number | string
  trechos: number
  media_dias: number | string
}

export interface TimeInStatus {
  status_canonical: StatusCanonical
  mediana_dias: number | string
  p85_dias: number | string
  n: number
}

export interface Wip {
  person_id: string
  display_name: string
  username: string
  wip: number
  em_andamento: number
  em_revisao: number
  contextos: number
}

export interface Aging {
  task_id: string
  name: string
  url: string
  status_canonical: StatusCanonical
  primary_assignee_id: string
  list_name: string
  days_in_status: number | string
  days_open: number | string
  aging_bucket: 0 | 7 | 14 | 30
}

export interface LeadCycle {
  list_name: string
  area: string
  prioridade: string
  lead_mediana: number | string
  cycle_mediana: number | string
  n: number
}

export interface Rework {
  task_id: string
  name: string
  url: string
  primary_assignee_id: string
  returns_from_review: number
}

export interface HygieneIssue {
  task_id: string
  name: string
  url: string
  status_canonical: StatusCanonical
  status_raw: string
  issues: string[]
}

export interface HygieneDuplicate {
  task_a: string
  task_b: string
  name_a: string
  name_b: string
  url_a: string
  url_b: string
}

export interface Page<T> {
  items: T[]
  total: number
}

export interface AgingPage extends Page<Aging> {
  stale_30: number
}

export interface Hygiene {
  issues: HygieneIssue[]
  duplicates: HygieneDuplicate[]
}

export interface BlockChain {
  id: number
  from_task_id: string | null
  from_task_name: string | null
  to_task_id: string | null
  to_task_name: string | null
  from_person: string
  to_person: string
  description: string
  evidence_task_id: string | null
  days_blocked: number | string
}

export interface Promised {
  id: number
  task_id: string
  name: string
  url: string
  phase: string
  due_on: string | null
  closed_on: string | null
  status_canonical: StatusCanonical
  days_delta: number | null
}

export interface Metrics {
  bottleneck: Bottleneck[]
  timeInStatus: Page<TimeInStatus>
  wip: Wip[]
  aging: AgingPage
  leadCycle: Page<LeadCycle>
  rework: Rework[]
  hygiene: Page<HygieneIssue> | null
  duplicates: Page<HygieneDuplicate>
  blockChain: Page<BlockChain>
  promised: Page<Promised>
}

export interface TaskDetail {
  task: {
    clickup_id: string
    custom_id: string | null
    name: string
    description: string
    url: string | null
    list_id: string
    parent_id: string | null
    status_raw: string
    status_canonical: StatusCanonical
    date_created: string
    date_updated: string
    date_closed: string | null
    due_date: string | null
    start_date: string | null
    archived: boolean
    assignees: { id: string; username: string }[]
    primary_assignee_id: string | null
    prioridade: string | null
    contexto: string | null
    area: string | null
    tipo: string | null
    last_status_seen: string | null
    last_status_seen_at: string | null
    synced_at: string
    deleted_at: string | null
  }
  comments: { clickup_id: string; author_id: string; text: string; date: string }[]
  transitions: {
    from_status: string
    to_status: string
    from_canonical: StatusCanonical
    to_canonical: StatusCanonical
    at: string
    source: string
  }[]
}

export interface Profile {
  member: Person
  profile: {
    person_id: string
    report_id: number
    strengths: string
    leverage: string
    next_step: string
    domains: unknown
    consistency: string
    autonomy: string
    load_note: string
    knowledge_concentration: unknown
    collaboration: unknown
    communication: unknown
    updated_at: string
  } | null
  wip: Wip | null
  aging: {
    task_id: string
    name: string
    url: string
    status_canonical: StatusCanonical
    days_in_status: number | string
  }[]
  collaboration_out: {
    commenter_id: string
    owner_id: string
    comments: number
    owner_name: string
    owner_username: string
  }[]
  collaboration_in: {
    commenter_id: string
    owner_id: string
    comments: number
    commenter_name: string
    commenter_username: string
  }[]
  viewing_as_admin: boolean
}

export interface LeaderboardFlow {
  person_id: string
  display_name: string
  username: string
  wip: number
  em_andamento: number
  em_revisao: number
  aging_7: number
  aging_14: number
  aging_30: number
}

export interface LeaderboardDelivery {
  person_id: string
  display_name: string
  username: string
  cards_concluidos: number
  lead_mediana: number | string
  cycle_mediana: number | string
  marcos_no_prazo: number
  marcos_atrasados: number
  atraso_mediano_dias: number | string
}

export interface Leaderboard {
  fluxo: LeaderboardFlow[]
  entrega: LeaderboardDelivery[]
}

export interface Health {
  ok: boolean
  last_sync: { value: unknown; updated_at: string } | null
}

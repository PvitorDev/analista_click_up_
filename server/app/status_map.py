import re
import unicodedata

CANONICAL = {
    "doing": "EM_ANDAMENTO",
    "fazendo": "EM_ANDAMENTO",
    "in progress": "EM_ANDAMENTO",
    "em andamento": "EM_ANDAMENTO",
    "em progresso": "EM_ANDAMENTO",
    "progresso": "EM_ANDAMENTO",
    "andamento": "EM_ANDAMENTO",
    "review": "EM_REVISAO",
    "em revisão": "EM_REVISAO",
    "em revisao": "EM_REVISAO",
    "in review": "EM_REVISAO",
    "a fazer": "A_FAZER",
    "open": "A_FAZER",
    "to do": "A_FAZER",
    "todo": "A_FAZER",
    "backlog": "A_FAZER",
    "pendente": "A_FAZER",
    "pending": "A_FAZER",
    "aguardando": "A_FAZER",
    "unstarted": "A_FAZER",
    "feito": "CONCLUIDO",
    "closed": "CONCLUIDO",
    "fechado": "CONCLUIDO",
    "fechada": "CONCLUIDO",
    "pronto": "CONCLUIDO",
    "pronta": "CONCLUIDO",
    "resolvido": "CONCLUIDO",
    "resolvida": "CONCLUIDO",
    "finished": "CONCLUIDO",
    "resolved": "CONCLUIDO",
    "encerrado": "CONCLUIDO",
    "encerrada": "CONCLUIDO",
    "complete": "CONCLUIDO",
    "completed": "CONCLUIDO",
    "completo": "CONCLUIDO",
    "completa": "CONCLUIDO",
    "completado": "CONCLUIDO",
    "completada": "CONCLUIDO",
    "concluido": "CONCLUIDO",
    "concluida": "CONCLUIDO",
    "finalizado": "CONCLUIDO",
    "finalizada": "CONCLUIDO",
    "done": "CONCLUIDO",
    "blocked": "BLOQUEADO",
    "bloqueado": "BLOQUEADO",
}

STATUS_LABEL_PT = {
    "A_FAZER": "A fazer",
    "EM_ANDAMENTO": "Em andamento",
    "EM_REVISAO": "Em revisão",
    "CONCLUIDO": "Concluído",
    "BLOQUEADO": "Bloqueado",
    "OUTRO": "Outro (status do ClickUp fora do padrão)",
}


def _norm(value: str) -> str:
    nfkd = unicodedata.normalize("NFKD", value or "")
    stripped = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", stripped).strip().lower()


def canonical_status(raw: str | None, status_type: str | None = None) -> str:
    if not raw and not status_type:
        return "OUTRO"
    t = _norm(status_type)
    # ClickUp type is the source of truth for closed/done columns.
    if t in ("closed", "done"):
        return "CONCLUIDO"
    key = _norm(raw)
    if key in CANONICAL:
        return CANONICAL[key]
    # Prefer longer needles so "em progresso" wins over fragments.
    for needle, canon in sorted(CANONICAL.items(), key=lambda kv: len(kv[0]), reverse=True):
        if len(needle) >= 4 and needle in key:
            return canon
    if t in ("unstarted",):
        return "A_FAZER"
    if t == "open" and not key:
        return "A_FAZER"
    return "OUTRO"


def remap_stored_statuses() -> int:
    from app.db import execute, fetch_all

    changed = 0
    rows = fetch_all(
        "SELECT clickup_id, status_raw, status_canonical, date_closed FROM tasks"
    )
    for row in rows:
        new = canonical_status(row.get("status_raw"))
        if new == "OUTRO" and row.get("date_closed"):
            new = "CONCLUIDO"
        if new != row.get("status_canonical"):
            execute(
                "UPDATE tasks SET status_canonical = %s WHERE clickup_id = %s",
                (new, row["clickup_id"]),
            )
            changed += 1

    transitions = fetch_all(
        """
        SELECT id, from_status, to_status, from_canonical, to_canonical
        FROM status_transitions
        """
    )
    for row in transitions:
        new_from = canonical_status(row.get("from_status")) if row.get("from_status") else None
        new_to = canonical_status(row.get("to_status"))
        if new_from != row.get("from_canonical") or new_to != row.get("to_canonical"):
            execute(
                """
                UPDATE status_transitions
                   SET from_canonical = %s, to_canonical = %s
                 WHERE id = %s
                """,
                (new_from, new_to, row["id"]),
            )
            changed += 1
    return changed


AREA_PREFIXES = {
    "ui/ux": "UI/UX",
    "ui": "UI/UX",
    "ux": "UI/UX",
    "backend": "Backend",
    "infra": "Infra",
    "spbk": "SPBK",
}


def taxonomy_from_title(name: str) -> tuple[str | None, str | None]:
    m = re.match(r"^\[([^\]]+)\]", name or "", re.I)
    if not m:
        return None, None
    token = _norm(m.group(1))
    area = AREA_PREFIXES.get(token)
    return area, m.group(1).strip()

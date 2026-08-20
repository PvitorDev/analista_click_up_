from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.config import settings
from app.db import execute, fetch_all, fetch_one
from app.status_map import STATUS_LABEL_PT

logger = logging.getLogger(__name__)


FORBIDDEN_SQL = re.compile(r"\b(insert|update|delete|drop|alter|truncate|create|grant|revoke)\b", re.I)


def metrics_bundle() -> dict[str, Any]:
    catalog = fetch_all(
        """
        SELECT clickup_id, custom_id, name, url
        FROM tasks
        WHERE deleted_at IS NULL AND parent_id IS NULL
        LIMIT 80
        """
    )
    return {
        "como_ler_os_dados": {
            "status": STATUS_LABEL_PT,
            "lead_mediana": "tempo mediano da criação do card até ele ser concluído (calendário, não esforço)",
            "cycle_mediana": "tempo mediano desde que o trabalho começou de verdade até concluir; nulo = o card nunca saiu da fila",
            "p85": "os casos mais lentos (15% piores); se igual à mediana, não há variação — típico de estoque parado",
            "WIP": "quantos cards a pessoa tem em paralelo agora (fila de trabalho, não avaliação)",
            "aging": "há quantos dias o card está no mesmo status",
            "bus_factor": "quantas pessoas sustentam esse conhecimento; 1 = uma só cabeça",
            "higiene": {
                "sem_assignee": "sem responsável",
                "sem_prioridade": "sem prioridade",
                "sem_contexto": "sem contexto",
                "status_divergente": "status do ClickUp fora do padrão da empresa",
                "sem_semantica": "título genérico, sem significado",
                "multi_assignee": "vários responsáveis",
            },
        },
        "task_catalog": catalog,
        "bottleneck": fetch_all("SELECT * FROM v_bottleneck LIMIT 15"),
        "time_in_status": fetch_all(
            """
            SELECT DISTINCT ON (status_canonical)
                   status_canonical, mediana_dias, p85_dias, n
            FROM v_time_in_status_stats
            WHERE list_id IS NULL AND area IS NULL AND person_id IS NULL
            ORDER BY status_canonical, n DESC
            """
        ),
        "wip": fetch_all("SELECT * FROM v_wip ORDER BY wip DESC LIMIT 15"),
        "aging": fetch_all("SELECT * FROM v_aging ORDER BY days_in_status DESC LIMIT 15"),
        "rework": fetch_all("SELECT * FROM v_rework ORDER BY returns_from_review DESC LIMIT 15"),
        "hygiene": fetch_all(
            "SELECT * FROM v_hygiene WHERE cardinality(issues) > 0 LIMIT 20"
        ),
        "block_chain": fetch_all("SELECT * FROM v_block_chain LIMIT 15"),
        "promised": fetch_all("SELECT * FROM v_promised_vs_delivered LIMIT 15"),
        "lead_cycle": fetch_all(
            """
            SELECT list_name, area, prioridade,
                   percentile_cont(0.5) WITHIN GROUP (ORDER BY lead_days) AS lead_mediana,
                   percentile_cont(0.5) WITHIN GROUP (ORDER BY cycle_days) AS cycle_mediana,
                   count(*) AS n
            FROM v_lead_cycle
            GROUP BY list_name, area, prioridade
            LIMIT 15
            """
        ),
        "members": fetch_all(
            """
            SELECT clickup_id, username, display_name
            FROM members
            ORDER BY display_name NULLS LAST
            LIMIT 80
            """
        ),
    }


def sql_readonly(sql: str) -> list[dict]:
    stripped = sql.strip().rstrip(";")
    if FORBIDDEN_SQL.search(stripped) or not stripped.lower().startswith("select"):
        raise ValueError("Apenas SELECT é permitido")
    return fetch_all(stripped)


TZ_SP = ZoneInfo("America/Sao_Paulo")


def report_title(when: datetime | None = None) -> str:
    stamp = (when or datetime.now(TZ_SP)).astimezone(TZ_SP)
    return f"Relatório {stamp.strftime('%d/%m/%Y %H:%M')}"


def last_history_summary() -> str:
    from app.workspace import current_team_id

    team_id = current_team_id()
    if not team_id:
        return ""
    row = fetch_one(
        """
        SELECT history_summary FROM reports
        WHERE COALESCE(history_summary, '') <> ''
          AND team_id = %s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (team_id,),
    )
    return (row or {}).get("history_summary") or ""


def _enrich_evidence(evidence: list) -> list:
    out: list = []
    for ev in evidence or []:
        if not isinstance(ev, dict):
            continue
        item = dict(ev)
        tid = str(item.get("task_id") or "")
        if tid:
            task = fetch_one(
                "SELECT name, url FROM tasks WHERE clickup_id = %s OR custom_id = %s",
                (tid, tid),
            )
            if task:
                item.setdefault("name", task.get("name"))
                if not item.get("url"):
                    item["url"] = task.get("url")
        out.append(item)
    return out


def _resolve_member_id(raw: str | None) -> str | None:
    key = (raw or "").strip()
    if not key or key.lower() in {"none", "null"}:
        return None
    row = fetch_one(
        """
        SELECT clickup_id FROM members
        WHERE clickup_id = %s
           OR lower(coalesce(username, '')) = lower(%s)
           OR lower(coalesce(display_name, '')) = lower(%s)
        LIMIT 1
        """,
        (key, key, key),
    )
    return str(row["clickup_id"]) if row else None


def _fallback_profile(member: dict) -> dict:
    name = member.get("display_name") or member.get("username") or "esta pessoa"
    pid = str(member["clickup_id"])
    wip = fetch_one("SELECT * FROM v_wip WHERE person_id = %s", (pid,))
    aging_n = fetch_one(
        "SELECT count(*) AS n FROM v_aging WHERE primary_assignee_id = %s",
        (pid,),
    )
    wip_n = int((wip or {}).get("wip") or 0)
    aging_count = int((aging_n or {}).get("n") or 0)
    if wip_n or aging_count:
        strengths = (
            f"{name} aparece no board com {wip_n} card(s) em execução/revisão "
            f"e {aging_count} card(s) ainda abertos."
        )
        leverage = "Concentrar o trabalho em paralelo e destravar os cards parados."
        next_step = "Revisar os cards abertos e fechar ou avançar o que estiver parado."
        load = f"Trabalho em paralelo: {wip_n}. Cards abertos: {aging_count}."
    else:
        strengths = (
            f"Ainda há pouca evidência de cards com {name} como responsável neste workspace."
        )
        leverage = (
            "Atribuir e avançar cards no ClickUp para o perfil ficar mais preciso no próximo ciclo."
        )
        next_step = "Garantir que o trabalho ativo esteja com responsável claro."
        load = "Sem cards abertos atribuídos neste recorte."
    return {
        "person_id": pid,
        "strengths": strengths,
        "leverage": leverage,
        "next_step": next_step,
        "domains": [],
        "consistency": "Ainda sem histórico suficiente para falar de consistência.",
        "autonomy": "Ainda sem evidência textual suficiente.",
        "load_note": load,
        "knowledge_concentration": {},
        "collaboration": {},
        "communication": {},
    }


def _normalize_profiles(profiles: list, session_user_id: str | None) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for profile in profiles or []:
        if not isinstance(profile, dict):
            continue
        pid = _resolve_member_id(str(profile.get("person_id") or ""))
        if not pid:
            pid = _resolve_member_id(
                str(profile.get("display_name") or profile.get("name") or "")
            )
        if not pid or pid in seen:
            continue
        item = dict(profile)
        item["person_id"] = pid
        out.append(item)
        seen.add(pid)

    members = fetch_all(
        "SELECT clickup_id, username, display_name FROM members ORDER BY display_name NULLS LAST"
    )
    wip_ids = {str(r["person_id"]) for r in fetch_all("SELECT person_id FROM v_wip")}
    session_id = str(session_user_id or "")
    for member in members:
        cid = str(member["clickup_id"])
        if cid in seen:
            continue
        if cid == session_id or cid in wip_ids or len(members) <= 15:
            out.append(_fallback_profile(member))
            seen.add(cid)
    return out


def save_report(
    narrative: str,
    improvements: list,
    evidence: list,
    profiles: list[dict],
    history_summary: str,
    session_user_id: str | None = None,
) -> tuple[int, str]:
    title = report_title()
    evidence = _enrich_evidence(evidence)
    from app.workspace import current_team_id

    team_id = current_team_id()
    row = fetch_one(
        """
        INSERT INTO reports (title, narrative, improvements, evidence, generated_by, history_summary, team_id)
        VALUES (%s, %s, %s::jsonb, %s::jsonb, 'claude', %s, %s)
        RETURNING id, title, created_at
        """,
        (
            title,
            narrative,
            json.dumps(improvements, default=str),
            json.dumps(evidence, default=str),
            history_summary or "",
            team_id or None,
        ),
    )
    report_id = row["id"]
    for profile in _normalize_profiles(profiles, session_user_id):
        pid = str(profile.get("person_id"))
        member = fetch_one("SELECT clickup_id FROM members WHERE clickup_id = %s", (pid,))
        if not member:
            logger.warning("Perfil ignorado: person_id %s não está em members", pid)
            continue
        execute(
            """
            INSERT INTO person_profiles (
                person_id, report_id, strengths, leverage, next_step, domains,
                consistency, autonomy, load_note, knowledge_concentration, collaboration, communication
            ) VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb)
            ON CONFLICT (person_id) DO UPDATE SET
                report_id = EXCLUDED.report_id,
                strengths = EXCLUDED.strengths,
                leverage = EXCLUDED.leverage,
                next_step = EXCLUDED.next_step,
                domains = EXCLUDED.domains,
                consistency = EXCLUDED.consistency,
                autonomy = EXCLUDED.autonomy,
                load_note = EXCLUDED.load_note,
                knowledge_concentration = EXCLUDED.knowledge_concentration,
                collaboration = EXCLUDED.collaboration,
                communication = EXCLUDED.communication,
                updated_at = now()
            """,
            (
                pid,
                report_id,
                profile.get("strengths"),
                profile.get("leverage"),
                profile.get("next_step"),
                json.dumps(profile.get("domains") or {}, default=str),
                profile.get("consistency"),
                profile.get("autonomy"),
                profile.get("load_note"),
                json.dumps(profile.get("knowledge_concentration") or {}, default=str),
                json.dumps(profile.get("collaboration") or {}, default=str),
                json.dumps(profile.get("communication") or {}, default=str),
            ),
        )
    try:
        from app.rag import index_report

        index_report(
            {
                "id": report_id,
                "title": title,
                "created_at": row.get("created_at"),
                "narrative": narrative,
                "history_summary": history_summary or "",
                "improvements": improvements,
                "team_id": team_id,
            }
        )
    except Exception:
        logger.exception("Falha ao indexar relatório %s no Redis", report_id)
    return report_id, title


SYSTEM = """Você é um analista sênior de gestão de tarefas, não um dashboard e não um robô de automação.
Responda como um gestor depois de uma semana investigando o ClickUp desta empresa.
Tom: prosa corrida, causa provável + evidência. Não use bullet points soltos no diagnóstico.
Métricas de processo podem citar gargalos e trabalho em paralelo. NÃO ranqueie pessoas por desempenho.
Perfis individuais: pontos fortes, alavancagem, próximo passo concreto — nunca ranking.
profiles DEVE ter um objeto para CADA pessoa em members (e obrigatoriamente usuario_da_sessao, se existir).
person_id DEVE ser o clickup_id da lista members — nunca o nome nem o username.

LINGUAGEM (obrigatório — o leitor é gestor, não engenheiro):
- Português claro. Nunca escreva nomes de campo, view ou coluna (lead_cycle, lead_mediana, cycle_mediana, time_in_status, days_in_status, status_canonical, status_raw, bus_factor, WIP, p85, aging, rework, hygiene).
- Traduza: lead = "tempo da criação até concluir"; cycle = "tempo desde que o trabalho começou até concluir" (se nulo, diga que o card nunca saiu da fila); p85 = "os casos mais lentos"; WIP = "trabalho em paralelo"; bus factor = "quantas pessoas sustentam esse conhecimento"; aging = "dias parado no mesmo status".
- Status: use o rótulo em português de como_ler_os_dados.status (A_FAZER → "A fazer", EM_ANDAMENTO → "Em andamento", OUTRO → "status fora do padrão"). Nunca escreva A_FAZER, EM_ANDAMENTO, EM_REVISAO, CONCLUIDO, BLOQUEADO, OUTRO no texto.
- Cards: cite SEMPRE o nome do card (task_catalog.name). Nunca cole id ClickUp (86e2ugrch, clickup_id, custom_id) na narrativa, no resumo ou nas melhorias. O id vai só no JSON de evidence.task_id e improvements.task_ids.
- Pessoas: use display_name. Nunca o número clickup_id entre parênteses.
- Higiene: "sem responsável", "sem prioridade", "sem contexto", "status fora do padrão" — não sem_assignee / sem_prioridade.

Se o payload trouxer previous_history_summary, use-o como único contexto comparativo do ciclo anterior.
Na narrativa, compare o agora com esse resumo: o que mudou e o que ainda falta. Não cole o resumo antigo no texto.

FORMATO DA RESPOSTA (obrigatório, nesta ordem):
1) Escreva PRIMEIRO o diagnóstico em Markdown (## e ### para títulos, **negrito**, listas com "- "). Prosa de gestor. Sem JSON nessa parte. Sem ids ClickUp.
2) Em seguida, sozinho, UM objeto JSON (pode vir após uma linha em branco). Chaves:
{
  "narrative": "o mesmo diagnóstico em texto (pode repetir a prosa)",
  "improvements": [{"problem": "", "impact": "", "effort": "", "action": "", "decides": "", "score": 0, "task_ids": []}],
  "evidence": [{"claim": "", "task_id": "", "name": "", "url": ""}],
  "profiles": [{"person_id": "", "strengths": "", "leverage": "", "next_step": "", "domains": [], "consistency": "", "autonomy": "", "load_note": "", "knowledge_concentration": {}, "collaboration": {}, "communication": {}}],
  "history_summary": "5 a 6 linhas"
}
Não escreva nada depois do JSON.

Improvements: exatamente 5, ordenadas por impacto/esforço (score alto primeiro). problem/action em português claro, sem jargão técnico.
O diagnóstico deve responder: onde o trabalho para e quanto custa; como cada pessoa trabalha (em prosa, sem ranking); as 5 mudanças de maior impacto.

RESUMO PARA HISTÓRICO (history_summary):
Ao final, gere um resumo curto (máximo 5-6 linhas) deste relatório, escrito para ser usado como contexto comparativo nos PRÓXIMOS relatórios. Esse resumo deve:
- Conter apenas os fatos e números essenciais para comparação futura (não detalhes)
- Focar em tendência, não em explicação
- Ser objetivo, sem repetir texto do relatório completo
- Ser escrito na terceira pessoa, em português claro, com as mesmas regras de linguagem acima (nomes de card, status em português, sem ids, sem nomes de campo)
- Formato factual (ex: "Período: 45 tarefas concluídas, 12 atrasadas, aumento de 10% em relação ao período anterior")
Se houver previous_history_summary, o novo resumo sobrescreve o anterior: descreva a mudança e o que ainda falta. Não concatene o texto velho.
"""

REFINE_SYSTEM = """Você refina extrações heurísticas do Bloco B (milestones, dependencies, risks, decisions).
Recebe candidatos já extraídos + trechos de descrição/comentários + catálogo de tasks/members.

Regras:
- Devolva APENAS JSON válido com as chaves milestones, dependencies, risks, decisions (arrays).
- Enriqueça somente quando houver evidência textual clara no payload.
- Ambíguo ou incerto → omita o item ou deixe campos null; NUNCA invente task_id, comment_id ou pessoas.
- to_task_id / from_person / to_person só se mencionados ou dedutíveis de forma única no texto.
- Não reescreva description/text de forma que perca a evidência original.

Formato:
{
  "milestones": [{"task_id","phase","due_on","evidence"}],
  "dependencies": [{"evidence_task_id","description","from_task_id","to_task_id","from_person","to_person"}],
  "risks": [{"task_id","kind","text"}],
  "decisions": [{"task_id","comment_id","author_id","text","decided_at"}]
}
"""


def _parse_json_payload(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text.rstrip("`").strip(), count=1, flags=re.I).rstrip("`").strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    return json.loads(text)


def _extract_report_json_blob(text: str) -> str | None:
    """Pega o objeto JSON do relatório (não o primeiro `{` da prosa)."""
    raw = (text or "").strip()
    if not raw:
        return None
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw, flags=re.I | re.S)
    if fence:
        candidate = fence.group(1)
        if _json_loads_relaxed(candidate) is not None:
            return candidate
    keys = ('"improvements"', '"profiles"', '"history_summary"', '"evidence"')
    for needle in keys:
        idx = raw.rfind(needle)
        while idx >= 0:
            start = raw.rfind("{", 0, idx)
            while start >= 0:
                blob = _slice_balanced_object(raw, start)
                if blob and any(k in blob for k in keys):
                    if _json_loads_relaxed(blob) is not None:
                        return blob
                    repaired = _repair_json(blob)
                    if repaired is not None:
                        return repaired
                start = raw.rfind("{", 0, start)
            idx = raw.rfind(needle, 0, idx)
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        blob = raw[start : end + 1]
        repaired = _repair_json(blob)
        if repaired is not None:
            return repaired
        return blob
    return None


def _slice_balanced_object(text: str, start: int) -> str | None:
    if start < 0 or start >= len(text) or text[start] != "{":
        return None
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return text[start:]


def _json_loads_relaxed(blob: str) -> dict | None:
    try:
        data = json.loads(blob)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        repaired = _repair_json(blob)
        if repaired is None:
            return None
        try:
            data = json.loads(repaired)
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None


def _repair_json(blob: str) -> str | None:
    cleaned = re.sub(r",\s*([}\]])", r"\1", blob)
    try:
        json.loads(cleaned)
        return cleaned
    except json.JSONDecodeError:
        pass
    # Truncado (bateu no max_tokens): fecha strings/chaves/listas abertas.
    fixed = cleaned
    in_str = False
    escape = False
    braces = 0
    brackets = 0
    for ch in fixed:
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            braces += 1
        elif ch == "}":
            braces -= 1
        elif ch == "[":
            brackets += 1
        elif ch == "]":
            brackets -= 1
    if in_str:
        fixed += '"'
    fixed = re.sub(r",\s*$", "", fixed)
    fixed += "]" * max(brackets, 0) + "}" * max(braces, 0)
    try:
        json.loads(fixed)
        return fixed
    except json.JSONDecodeError:
        return None


def parse_report_output(text: str) -> dict:
    prose = visible_narrative(text).strip()
    parsed: dict | None = None
    blob = _extract_report_json_blob(text)
    if blob:
        parsed = _json_loads_relaxed(blob)
    if parsed is None:
        try:
            parsed = _parse_json_payload(text)
        except (json.JSONDecodeError, TypeError, ValueError):
            logger.warning("JSON do relatório inválido; salvando só o diagnóstico em prosa")
            parsed = None
    if not parsed:
        parsed = {
            "narrative": prose,
            "improvements": [],
            "evidence": [],
            "profiles": [],
            "history_summary": "",
        }
    if prose and not (parsed.get("narrative") or "").strip():
        parsed["narrative"] = prose
    return parsed


def visible_narrative(full: str) -> str:
    """Prosa visível no stream: esconde o JSON (e fence) no final."""
    if not full:
        return ""
    stripped = full.lstrip()
    if stripped.startswith("{") or stripped.lower().startswith("```json"):
        return ""
    cut = len(full)
    fence = re.search(r"\n```(?:json)?\s*\n?\s*\{", full, flags=re.I)
    if fence:
        cut = min(cut, fence.start())
    brace = full.find("\n{")
    if brace >= 0:
        tail = full[brace:]
        if any(
            k in tail
            for k in ('"improvements"', '"evidence"', '"profiles"', '"history_summary"', '"narrative"')
        ):
            cut = min(cut, brace)
    return full[:cut].rstrip()


def parse_report_output(text: str) -> dict:
    parsed = _parse_json_payload(text)
    prose = visible_narrative(text).strip()
    if prose and not (parsed.get("narrative") or "").strip():
        parsed["narrative"] = prose
    return parsed


def _prepare_bundle(session_user_id: str | None) -> dict:
    bundle = metrics_bundle()
    previous = last_history_summary()
    if previous:
        bundle["previous_history_summary"] = previous
    if session_user_id:
        me = fetch_one(
            "SELECT clickup_id, username, display_name FROM members WHERE clickup_id = %s",
            (session_user_id,),
        )
        bundle["usuario_da_sessao"] = me or {
            "clickup_id": session_user_id,
            "aviso": "não está na tabela members",
        }
    return bundle


def persist_generated(parsed: dict, session_user_id: str | None = None) -> dict:
    improvements = parsed.get("improvements") or []
    improvements = sorted(improvements, key=lambda i: float(i.get("score") or 0), reverse=True)[:5]
    history_summary = (parsed.get("history_summary") or "").strip()
    narrative = (parsed.get("narrative") or "").strip()
    report_id, title = save_report(
        narrative,
        improvements,
        parsed.get("evidence") or [],
        parsed.get("profiles") or [],
        history_summary,
        session_user_id=session_user_id,
    )
    return {
        "id": report_id,
        "title": title,
        "history_summary": history_summary,
        **parsed,
        "narrative": narrative,
        "improvements": improvements,
    }


async def generate_with_agent_sdk(bundle: dict) -> dict:
    from claude_agent_sdk import ClaudeAgentOptions, query

    prompt = SYSTEM + "\n\nDADOS:\n" + json.dumps(bundle, default=str, ensure_ascii=False)[:120000]
    options = ClaudeAgentOptions(
        system_prompt="Analista de gestão de tarefas. Só leia os dados fornecidos. Não use Bash nem escreva arquivos.",
        allowed_tools=[],
        disallowed_tools=["Bash", "Write", "Edit", "Read", "Glob", "Grep", "WebSearch", "WebFetch"],
        permission_mode="dontAsk",
    )
    chunks: list[str] = []
    async for message in query(prompt=prompt, options=options):
        content = getattr(message, "content", None)
        if isinstance(content, list):
            for block in content:
                if hasattr(block, "text"):
                    chunks.append(block.text)
                elif isinstance(block, dict) and block.get("text"):
                    chunks.append(block["text"])
        elif isinstance(content, str):
            chunks.append(content)
    return parse_report_output("".join(chunks))


def generate_with_anthropic(bundle: dict) -> dict:
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    msg = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=16000,
        system=SYSTEM,
        messages=[
            {
                "role": "user",
                "content": json.dumps(bundle, default=str, ensure_ascii=False)[:120000],
            }
        ],
    )
    text = "".join(getattr(b, "text", "") for b in msg.content)
    return parse_report_output(text)


async def refine_with_agent_sdk(candidates: dict) -> dict:
    from claude_agent_sdk import ClaudeAgentOptions, query

    prompt = REFINE_SYSTEM + "\n\nDADOS:\n" + json.dumps(candidates, default=str, ensure_ascii=False)[:80000]
    options = ClaudeAgentOptions(
        system_prompt="Refino de extração Bloco B. Só leia os dados fornecidos.",
        allowed_tools=[],
        disallowed_tools=["Bash", "Write", "Edit", "Read", "Glob", "Grep", "WebSearch", "WebFetch"],
        permission_mode="dontAsk",
    )
    chunks: list[str] = []
    async for message in query(prompt=prompt, options=options):
        content = getattr(message, "content", None)
        if isinstance(content, list):
            for block in content:
                if hasattr(block, "text"):
                    chunks.append(block.text)
                elif isinstance(block, dict) and block.get("text"):
                    chunks.append(block["text"])
        elif isinstance(content, str):
            chunks.append(content)
    return _parse_json_payload("".join(chunks))


def refine_with_anthropic(candidates: dict) -> dict:
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    msg = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=4000,
        system=REFINE_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": json.dumps(candidates, default=str, ensure_ascii=False)[:80000],
            }
        ],
    )
    text = "".join(getattr(b, "text", "") for b in msg.content)
    return _parse_json_payload(text)


async def refine_extraction_llm(candidates: dict) -> dict | None:
    if not settings.anthropic_api_key:
        return None
    try:
        return await refine_with_agent_sdk(candidates)
    except Exception:
        return refine_with_anthropic(candidates)


async def generate_report(session_user_id: str | None = None) -> dict:
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY ausente")
    bundle = _prepare_bundle(session_user_id)
    try:
        parsed = await generate_with_agent_sdk(bundle)
    except Exception:
        parsed = generate_with_anthropic(bundle)
    return persist_generated(parsed, session_user_id)


async def stream_report_llm(bundle: dict, on_visible_delta) -> str:
    """Gera o relatório via Anthropic stream. on_visible_delta(str) recebe só a prosa."""
    import anthropic

    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY ausente")
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    user_content = json.dumps(bundle, default=str, ensure_ascii=False)[:120000]
    chunks: list[str] = []
    prev_visible = ""

    async def _emit(full: str) -> None:
        nonlocal prev_visible
        vis = visible_narrative(full)
        if vis.startswith(prev_visible) and vis != prev_visible:
            extra = vis[len(prev_visible) :]
            if extra:
                await on_visible_delta(extra)
            prev_visible = vis
        elif vis != prev_visible and vis:
            await on_visible_delta(vis[len(prev_visible) :] if vis.startswith(prev_visible) else vis)
            prev_visible = vis

    try:
        async with client.messages.stream(
            model=settings.anthropic_model,
            max_tokens=16000,
            system=SYSTEM,
            messages=[{"role": "user", "content": user_content}],
        ) as stream:
            async for text in stream.text_stream:
                if text:
                    chunks.append(text)
                    await _emit("".join(chunks))
    except Exception:
        logger.exception("Stream do relatório falhou")
        if not chunks:
            msg = await client.messages.create(
                model=settings.anthropic_model,
                max_tokens=16000,
                system=SYSTEM,
                messages=[{"role": "user", "content": user_content}],
            )
            text = "".join(getattr(b, "text", "") or "" for b in msg.content)
            chunks.append(text)
            await _emit(text)
    return "".join(chunks)

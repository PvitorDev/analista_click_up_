-- Durações por trecho de status (transições + estado atual)
CREATE OR REPLACE VIEW v_status_segments AS
WITH ordered AS (
    SELECT
        t.clickup_id AS task_id,
        t.list_id,
        t.primary_assignee_id,
        t.status_canonical AS current_canonical,
        t.date_created,
        COALESCE(t.area, tx.area) AS area,
        tr.from_canonical,
        tr.to_canonical,
        tr.at,
        lead(tr.at) OVER (PARTITION BY t.clickup_id ORDER BY tr.at) AS next_at,
        row_number() OVER (PARTITION BY t.clickup_id ORDER BY tr.at) AS rn
    FROM tasks t
    LEFT JOIN task_taxonomy tx ON tx.task_id = t.clickup_id
    LEFT JOIN status_transitions tr ON tr.task_id = t.clickup_id
    WHERE t.deleted_at IS NULL
),
from_transitions AS (
    SELECT
        task_id,
        list_id,
        primary_assignee_id,
        area,
        to_canonical AS status_canonical,
        at AS started_at,
        COALESCE(next_at, CASE WHEN to_canonical = current_canonical THEN now() END) AS ended_at
    FROM ordered
    WHERE to_canonical IS NOT NULL
),
never_transitioned AS (
    SELECT
        t.clickup_id AS task_id,
        t.list_id,
        t.primary_assignee_id,
        COALESCE(t.area, tx.area) AS area,
        t.status_canonical,
        COALESCE(t.date_created, t.synced_at) AS started_at,
        now() AS ended_at
    FROM tasks t
    LEFT JOIN task_taxonomy tx ON tx.task_id = t.clickup_id
    WHERE t.deleted_at IS NULL
      AND NOT EXISTS (
        SELECT 1 FROM status_transitions st WHERE st.task_id = t.clickup_id
    )
)
SELECT * FROM from_transitions WHERE ended_at IS NOT NULL
UNION ALL
SELECT * FROM never_transitioned;

CREATE OR REPLACE VIEW v_time_in_status AS
SELECT
    status_canonical,
    list_id,
    area,
    primary_assignee_id AS person_id,
    extract(epoch FROM (ended_at - started_at)) / 86400.0 AS days
FROM v_status_segments
WHERE ended_at > started_at;

CREATE OR REPLACE VIEW v_time_in_status_stats AS
SELECT
    status_canonical,
    list_id,
    area,
    person_id,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY days) AS mediana_dias,
    percentile_cont(0.85) WITHIN GROUP (ORDER BY days) AS p85_dias,
    count(*) AS n
FROM v_time_in_status
GROUP BY GROUPING SETS (
    (status_canonical),
    (status_canonical, list_id),
    (status_canonical, area),
    (status_canonical, person_id)
);

CREATE OR REPLACE VIEW v_bottleneck AS
SELECT
    status_canonical,
    list_id,
    l.name AS list_name,
    sum(days) AS dias_acumulados,
    count(*) AS trechos,
    avg(days) AS media_dias
FROM v_time_in_status tis
LEFT JOIN lists l ON l.clickup_id = tis.list_id
WHERE status_canonical IN ('EM_REVISAO', 'BLOQUEADO', 'A_FAZER', 'EM_ANDAMENTO')
GROUP BY status_canonical, list_id, l.name
ORDER BY dias_acumulados DESC;

CREATE OR REPLACE VIEW v_lead_cycle AS
SELECT
    t.clickup_id AS task_id,
    t.name,
    t.list_id,
    l.name AS list_name,
    COALESCE(t.area, tx.area) AS area,
    t.prioridade,
    t.date_created,
    t.date_closed,
    extract(epoch FROM (COALESCE(t.date_closed, now()) - t.date_created)) / 86400.0 AS lead_days,
    (
        SELECT extract(epoch FROM (COALESCE(t.date_closed, now()) - min(st.at))) / 86400.0
        FROM status_transitions st
        WHERE st.task_id = t.clickup_id AND st.to_canonical = 'EM_ANDAMENTO'
    ) AS cycle_days
FROM tasks t
LEFT JOIN lists l ON l.clickup_id = t.list_id
LEFT JOIN task_taxonomy tx ON tx.task_id = t.clickup_id
WHERE t.parent_id IS NULL;

CREATE OR REPLACE VIEW v_wip AS
SELECT
    m.clickup_id AS person_id,
    m.display_name,
    m.username,
    count(*) FILTER (WHERE t.status_canonical IN ('EM_ANDAMENTO', 'EM_REVISAO', 'BLOQUEADO')) AS wip,
    count(*) FILTER (WHERE t.status_canonical = 'EM_ANDAMENTO') AS em_andamento,
    count(*) FILTER (WHERE t.status_canonical = 'EM_REVISAO') AS em_revisao,
    count(DISTINCT COALESCE(t.contexto, t.area, tx.area)) AS contextos
FROM members m
JOIN tasks t ON t.primary_assignee_id = m.clickup_id AND t.parent_id IS NULL
LEFT JOIN task_taxonomy tx ON tx.task_id = t.clickup_id
WHERE t.status_canonical NOT IN ('CONCLUIDO')
  AND t.deleted_at IS NULL
GROUP BY m.clickup_id, m.display_name, m.username;

CREATE OR REPLACE VIEW v_aging AS
SELECT
    t.clickup_id AS task_id,
    t.name,
    t.url,
    t.status_canonical,
    t.primary_assignee_id,
    l.name AS list_name,
    extract(epoch FROM (now() - COALESCE(t.last_status_seen_at, t.date_updated, t.date_created))) / 86400.0 AS days_in_status,
    extract(epoch FROM (now() - t.date_created)) / 86400.0 AS days_open,
    CASE
        WHEN extract(epoch FROM (now() - COALESCE(t.last_status_seen_at, t.date_updated, t.date_created))) / 86400.0 >= 30 THEN 30
        WHEN extract(epoch FROM (now() - COALESCE(t.last_status_seen_at, t.date_updated, t.date_created))) / 86400.0 >= 14 THEN 14
        WHEN extract(epoch FROM (now() - COALESCE(t.last_status_seen_at, t.date_updated, t.date_created))) / 86400.0 >= 7 THEN 7
        ELSE 0
    END AS aging_bucket
FROM tasks t
LEFT JOIN lists l ON l.clickup_id = t.list_id
WHERE t.status_canonical <> 'CONCLUIDO'
  AND t.parent_id IS NULL
  AND t.deleted_at IS NULL;

CREATE OR REPLACE VIEW v_rework AS
SELECT
    t.clickup_id AS task_id,
    t.name,
    t.url,
    t.primary_assignee_id,
    count(*) FILTER (
        WHERE st.to_canonical = 'EM_ANDAMENTO'
          AND st.from_canonical = 'EM_REVISAO'
    ) AS returns_from_review
FROM tasks t
JOIN status_transitions st ON st.task_id = t.clickup_id
GROUP BY t.clickup_id, t.name, t.url, t.primary_assignee_id
HAVING count(*) FILTER (
    WHERE st.to_canonical = 'EM_ANDAMENTO' AND st.from_canonical = 'EM_REVISAO'
) > 0;

CREATE OR REPLACE VIEW v_block_chain AS
SELECT
    d.id,
    d.from_task_id,
    ft.name AS from_task_name,
    d.to_task_id,
    tt.name AS to_task_name,
    COALESCE(fm.display_name, fm.username, d.from_person) AS from_person,
    COALESCE(tm.display_name, tm.username, d.to_person) AS to_person,
    d.description,
    d.evidence_task_id,
    CASE
        WHEN tt.status_canonical IS DISTINCT FROM 'CONCLUIDO' THEN
            extract(epoch FROM (now() - COALESCE(tt.last_status_seen_at, tt.date_created))) / 86400.0
        ELSE 0
    END AS days_blocked
FROM dependencies d
LEFT JOIN tasks ft ON ft.clickup_id = d.from_task_id
LEFT JOIN tasks tt ON tt.clickup_id = d.to_task_id
LEFT JOIN members fm ON fm.clickup_id = d.from_person
LEFT JOIN members tm ON tm.clickup_id = d.to_person;

CREATE OR REPLACE VIEW v_promised_vs_delivered AS
SELECT
    m.id,
    m.task_id,
    t.name,
    t.url,
    m.phase,
    m.due_on,
    t.date_closed::date AS closed_on,
    t.status_canonical,
    CASE
        WHEN t.date_closed IS NOT NULL AND m.due_on IS NOT NULL THEN (t.date_closed::date - m.due_on)
        WHEN t.date_closed IS NULL AND m.due_on IS NOT NULL THEN (CURRENT_DATE - m.due_on)
        ELSE NULL
    END AS days_delta
FROM milestones m
JOIN tasks t ON t.clickup_id = m.task_id;

CREATE OR REPLACE VIEW v_hygiene AS
SELECT
    t.clickup_id AS task_id,
    t.name,
    t.url,
    t.status_canonical,
    t.status_raw,
    ARRAY_remove(ARRAY[
        CASE WHEN t.name ~* '^(janeiro|fevereiro|março|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro|[0-9]{4})$'
             THEN 'sem_semantica' END,
        CASE WHEN jsonb_array_length(t.assignees) = 0 THEN 'sem_assignee' END,
        CASE WHEN jsonb_array_length(t.assignees) >= 3 THEN 'multi_assignee' END,
        CASE WHEN t.parent_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM tasks p WHERE p.clickup_id = t.parent_id
        ) THEN 'subtask_orfa' END,
        CASE WHEN t.status_canonical = 'OUTRO' THEN 'status_divergente' END,
        CASE WHEN t.prioridade IS NULL THEN 'sem_prioridade' END,
        CASE WHEN t.contexto IS NULL THEN 'sem_contexto' END
    ], NULL) AS issues
FROM tasks t;

CREATE OR REPLACE VIEW v_possible_duplicates AS
SELECT
    a.clickup_id AS task_a,
    b.clickup_id AS task_b,
    a.name AS name_a,
    b.name AS name_b,
    a.url AS url_a,
    b.url AS url_b
FROM tasks a
JOIN tasks b ON a.clickup_id < b.clickup_id
    AND lower(trim(a.name)) = lower(trim(b.name))
    AND a.parent_id IS NULL AND b.parent_id IS NULL;

CREATE OR REPLACE VIEW v_collaboration AS
SELECT
    c.author_id AS commenter_id,
    t.primary_assignee_id AS owner_id,
    count(*) AS comments
FROM comments c
JOIN tasks t ON t.clickup_id = c.task_id
WHERE c.author_id IS NOT NULL
  AND t.primary_assignee_id IS NOT NULL
  AND c.author_id <> t.primary_assignee_id
GROUP BY c.author_id, t.primary_assignee_id;

CREATE OR REPLACE VIEW v_leaderboard_fluxo AS
SELECT
    m.clickup_id AS person_id,
    COALESCE(m.display_name, m.username, m.clickup_id) AS display_name,
    m.username,
    COALESCE(w.wip, 0)::int AS wip,
    COALESCE(w.em_andamento, 0)::int AS em_andamento,
    COALESCE(w.em_revisao, 0)::int AS em_revisao,
    COALESCE(a.aging_7, 0)::int AS aging_7,
    COALESCE(a.aging_14, 0)::int AS aging_14,
    COALESCE(a.aging_30, 0)::int AS aging_30
FROM members m
LEFT JOIN v_wip w ON w.person_id = m.clickup_id
LEFT JOIN (
    SELECT
        primary_assignee_id AS person_id,
        count(*) FILTER (WHERE aging_bucket = 7) AS aging_7,
        count(*) FILTER (WHERE aging_bucket = 14) AS aging_14,
        count(*) FILTER (WHERE aging_bucket = 30) AS aging_30
    FROM v_aging
    WHERE primary_assignee_id IS NOT NULL
    GROUP BY primary_assignee_id
) a ON a.person_id = m.clickup_id
WHERE w.person_id IS NOT NULL
   OR COALESCE(a.aging_7, 0) + COALESCE(a.aging_14, 0) + COALESCE(a.aging_30, 0) > 0
ORDER BY COALESCE(w.wip, 0) DESC;

CREATE OR REPLACE VIEW v_leaderboard_entrega AS
SELECT
    m.clickup_id AS person_id,
    COALESCE(m.display_name, m.username, m.clickup_id) AS display_name,
    m.username,
    COALESCE(done.cards_concluidos, 0)::int AS cards_concluidos,
    lc.lead_mediana,
    lc.cycle_mediana,
    COALESCE(pv.marcos_no_prazo, 0)::int AS marcos_no_prazo,
    COALESCE(pv.marcos_atrasados, 0)::int AS marcos_atrasados,
    atrasos.atraso_mediano_dias
FROM members m
LEFT JOIN (
    SELECT primary_assignee_id AS person_id, count(*) AS cards_concluidos
    FROM tasks
    WHERE status_canonical = 'CONCLUIDO'
      AND parent_id IS NULL
      AND deleted_at IS NULL
      AND primary_assignee_id IS NOT NULL
    GROUP BY primary_assignee_id
) done ON done.person_id = m.clickup_id
LEFT JOIN (
    SELECT
        t.primary_assignee_id AS person_id,
        percentile_cont(0.5) WITHIN GROUP (ORDER BY v.lead_days) AS lead_mediana,
        percentile_cont(0.5) WITHIN GROUP (ORDER BY v.cycle_days) AS cycle_mediana
    FROM v_lead_cycle v
    JOIN tasks t ON t.clickup_id = v.task_id
    WHERE t.primary_assignee_id IS NOT NULL
    GROUP BY t.primary_assignee_id
) lc ON lc.person_id = m.clickup_id
LEFT JOIN (
    SELECT
        t.primary_assignee_id AS person_id,
        count(*) FILTER (WHERE p.days_delta IS NOT NULL AND p.days_delta <= 0) AS marcos_no_prazo,
        count(*) FILTER (WHERE p.days_delta > 0) AS marcos_atrasados
    FROM v_promised_vs_delivered p
    JOIN tasks t ON t.clickup_id = p.task_id
    WHERE t.primary_assignee_id IS NOT NULL
    GROUP BY t.primary_assignee_id
) pv ON pv.person_id = m.clickup_id
LEFT JOIN (
    SELECT
        t.primary_assignee_id AS person_id,
        percentile_cont(0.5) WITHIN GROUP (ORDER BY p.days_delta) AS atraso_mediano_dias
    FROM v_promised_vs_delivered p
    JOIN tasks t ON t.clickup_id = p.task_id
    WHERE t.primary_assignee_id IS NOT NULL
      AND p.days_delta > 0
    GROUP BY t.primary_assignee_id
) atrasos ON atrasos.person_id = m.clickup_id
WHERE COALESCE(done.cards_concluidos, 0) > 0
   OR lc.lead_mediana IS NOT NULL
   OR COALESCE(pv.marcos_no_prazo, 0) + COALESCE(pv.marcos_atrasados, 0) > 0
ORDER BY COALESCE(done.cards_concluidos, 0) DESC;

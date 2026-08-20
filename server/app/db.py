from pathlib import Path

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import settings

pool: ConnectionPool | None = None
SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def get_pool() -> ConnectionPool:
    global pool
    if pool is None:
        pool = ConnectionPool(conninfo=settings.database_url, min_size=1, max_size=8, kwargs={"row_factory": dict_row})
    return pool


def exec_sql_script(conn, text: str) -> None:
    buf: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("--") and not buf:
            continue
        buf.append(line)
        if stripped.endswith(";"):
            stmt = "\n".join(buf).strip()
            buf = []
            if stmt:
                conn.execute(stmt)


def init_schema() -> None:
    schema = (SQL_DIR / "schema.sql").read_text(encoding="utf-8")
    views = (SQL_DIR / "views.sql").read_text(encoding="utf-8")
    with get_pool().connection() as conn:
        exec_sql_script(conn, schema)
        exec_sql_script(conn, views)
        conn.commit()


def fetch_all(sql: str, params: tuple | dict | None = None) -> list[dict]:
    with get_pool().connection() as conn:
        cur = conn.execute(sql, params)
        return list(cur.fetchall())


def fetch_one(sql: str, params: tuple | dict | None = None) -> dict | None:
    with get_pool().connection() as conn:
        cur = conn.execute(sql, params)
        return cur.fetchone()


def execute(sql: str, params: tuple | dict | None = None) -> None:
    with get_pool().connection() as conn:
        conn.execute(sql, params)
        conn.commit()

import time

from app.config import settings
from app.db import init_schema
from app.extract import extract_from_tasks
from app.sync.engine import run_sync


def main() -> None:
    settings.validate_boot()
    init_schema()
    print("Worker de sync iniciado. A2 (histórico de status) está ativo.")
    while True:
        try:
            stats = run_sync()
            extract = extract_from_tasks()
            print(f"Sync ok: {stats} extract: {extract}")
        except Exception as exc:
            print(f"Sync falhou: {exc}")
        time.sleep(max(30, settings.sync_interval_seconds))


if __name__ == "__main__":
    main()

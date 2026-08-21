#!/bin/sh
# Sobe worker + API no mesmo container (só se quiser UM serviço no Railway).
# Prefira dois serviços: railway.toml + railway.worker.toml
set -e
python -m app.worker &
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"

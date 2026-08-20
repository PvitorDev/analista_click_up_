from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth import router as auth_router
from app.api import router as api_router
from app.chat import router as chat_router
from app.report_ws import router as report_ws_router
from app.config import settings
from app.db import init_schema
from app.status_map import remap_stored_statuses

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate_boot()
    init_schema()
    try:
        remap_stored_statuses()
    except Exception:
        pass
    try:
        from app.workspace import backfill_report_team_ids

        backfill_report_team_ids()
    except Exception:
        logger.exception("Backfill team_id dos relatórios falhou")
    try:
        from app.rag import boot as rag_boot

        rag_boot()
    except Exception:
        logger.exception("RAG Redis não iniciou")
    yield


app = FastAPI(title="Analista ClickUp", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)
app.include_router(api_router)
app.include_router(chat_router)
app.include_router(report_ws_router)


@app.get("/")
def root():
    return {"service": "clickup-analyst", "read_only": True}

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from datum.api.admin import router as admin_router
from datum.api.citations import router as citations_router
from datum.api.context import router as context_router
from datum.api.documents import router as documents_router
from datum.api.evaluation import router as evaluation_router
from datum.api.inbox import router as inbox_router
from datum.api.projects import router as projects_router
from datum.api.projects import ws_router as projects_ws_router
from datum.api.search import router as search_router
from datum.api.sessions import router as sessions_router
from datum.api.versions import router as versions_router
from datum.config import settings
from datum.mcp_server import create_mcp_server


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Datum", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[f"http://localhost:{settings.frontend_port}"],
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(projects_router)
app.include_router(projects_ws_router)
app.include_router(versions_router)
app.include_router(documents_router)
app.include_router(inbox_router)
app.include_router(search_router)
app.include_router(evaluation_router)
app.include_router(sessions_router)
app.include_router(context_router)
app.include_router(citations_router)
app.include_router(admin_router)

mcp = create_mcp_server(settings.projects_root)
mcp.settings.mount_path = "/mcp"
app.mount("/mcp", mcp.sse_app())


@app.get("/api/v1/health")
async def health():
    return {"status": "ok"}

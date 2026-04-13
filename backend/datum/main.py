from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from datum.api.documents import router as documents_router
from datum.api.evaluation import router as evaluation_router
from datum.api.projects import router as projects_router
from datum.api.projects import ws_router as projects_ws_router
from datum.api.search import router as search_router
from datum.api.versions import router as versions_router
from datum.config import settings


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
app.include_router(search_router)
app.include_router(evaluation_router)


@app.get("/api/v1/health")
async def health():
    return {"status": "ok"}

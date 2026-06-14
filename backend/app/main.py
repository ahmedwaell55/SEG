from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import router
from app.config import get_settings
from app.database import init_db

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = PROJECT_ROOT / "frontend"
PAGES_DIR = FRONTEND_DIR / "pages"


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    init_db()
    yield


settings = get_settings()
app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

if FRONTEND_DIR.exists():
    app.mount("/css", StaticFiles(directory=FRONTEND_DIR / "css"), name="css")
    app.mount("/js", StaticFiles(directory=FRONTEND_DIR / "js"), name="js")
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")


@app.get("/", include_in_schema=False)
def home_page() -> FileResponse:
    return FileResponse(PAGES_DIR / "index.html")


@app.get("/login", include_in_schema=False)
def login_page() -> FileResponse:
    return FileResponse(PAGES_DIR / "login.html")


@app.get("/add-client", include_in_schema=False)
def add_client_page() -> FileResponse:
    return FileResponse(PAGES_DIR / "add-client.html")


@app.get("/client/{client_id}", include_in_schema=False)
def client_profile_page(client_id: int) -> FileResponse:  # noqa: ARG001
    return FileResponse(PAGES_DIR / "profile.html")


@app.get("/follow-ups", include_in_schema=False)
def followups_page() -> FileResponse:
    return FileResponse(PAGES_DIR / "follow-ups.html")


@app.get("/follow-ups/{followup_id}", include_in_schema=False)
def followup_detail_page(followup_id: int) -> FileResponse:  # noqa: ARG001
    return FileResponse(PAGES_DIR / "follow-up-details.html")

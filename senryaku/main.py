from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

from senryaku.config import get_settings
from senryaku.database import init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create data directory if needed
    Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
    init_db()
    yield


app = FastAPI(
    title="Senryaku",
    description="\u6226\u7565 \u2014 Personal operations server",
    version="0.1.0",
    lifespan=lifespan,
)

# Static files
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Templates
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


# API Key middleware - only for /api/ routes
class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/api/"):
            api_key = request.headers.get("X-API-Key")
            if api_key != settings.api_key:
                return JSONResponse(
                    status_code=401, content={"detail": "Invalid API key"}
                )
        response = await call_next(request)
        return response


app.add_middleware(APIKeyMiddleware)

# Import and include routers
from senryaku.routers.campaigns import router as campaigns_router  # noqa: E402
from senryaku.routers.missions import router as missions_router  # noqa: E402
from senryaku.routers.sorties import router as sorties_router  # noqa: E402
from senryaku.routers.operations import router as operations_router  # noqa: E402

app.include_router(campaigns_router, prefix="/api/v1")
app.include_router(missions_router, prefix="/api/v1")
app.include_router(sorties_router, prefix="/api/v1")
app.include_router(operations_router, prefix="/api/v1")

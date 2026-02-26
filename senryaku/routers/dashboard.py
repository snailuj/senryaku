from datetime import date
from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlmodel import Session
from pathlib import Path

from senryaku.database import get_session

templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

router = APIRouter()

@router.get("/")
def index(request: Request):
    """Redirect to dashboard."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/dashboard")

@router.get("/dashboard")
def dashboard(request: Request, session: Session = Depends(get_session)):
    """Main dashboard page."""
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "current_date": date.today().strftime("%A, %B %d"),
    })

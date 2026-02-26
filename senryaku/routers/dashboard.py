"""Dashboard and form-handling routes for the Senryaku UI."""

from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlmodel import Session, select

from senryaku.database import get_session
from senryaku.models import (
    Campaign,
    CampaignStatus,
    CognitiveLoad,
    Mission,
    MissionStatus,
    Sortie,
    SortieStatus,
)
from senryaku.services.health import compute_campaign_health, get_dashboard_data

templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

router = APIRouter()


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------


@router.get("/")
def index(request: Request):
    """Redirect to dashboard."""
    return RedirectResponse(url="/dashboard")


@router.get("/dashboard")
def dashboard(request: Request, session: Session = Depends(get_session)):
    """Main dashboard page."""
    campaigns = get_dashboard_data(session)
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "current_date": date.today().strftime("%A, %B %d"),
        "campaigns": campaigns,
    })


@router.get("/campaigns/{campaign_id}")
def campaign_detail(request: Request, campaign_id: str, session: Session = Depends(get_session)):
    """Campaign detail page showing missions and sorties."""
    campaign = session.get(Campaign, UUID(campaign_id))
    if not campaign:
        raise HTTPException(status_code=404)

    # Get missions with their sorties
    missions = session.exec(
        select(Mission)
        .where(Mission.campaign_id == campaign.id)
        .order_by(Mission.sort_order)
    ).all()

    # Load sorties for each mission
    for mission in missions:
        mission.sorties = session.exec(
            select(Sortie)
            .where(Sortie.mission_id == mission.id)
            .order_by(Sortie.sort_order)
        ).all()

    health = compute_campaign_health(session, campaign)

    return templates.TemplateResponse("campaign_detail.html", {
        "request": request,
        "current_date": date.today().strftime("%A, %B %d"),
        "campaign": campaign,
        "missions": missions,
        "health": health,
    })


# ---------------------------------------------------------------------------
# Partial routes (return HTMX fragments for modals)
# ---------------------------------------------------------------------------


@router.get("/partials/campaign-form")
def campaign_form_partial(
    request: Request,
    id: Optional[str] = Query(default=None),
    session: Session = Depends(get_session),
):
    """Return the campaign form partial. If ?id= is provided, pre-fill for editing."""
    campaign = None
    if id:
        campaign = session.get(Campaign, UUID(id))
        if not campaign:
            raise HTTPException(status_code=404)

    return templates.TemplateResponse("partials/campaign_form.html", {
        "request": request,
        "campaign": campaign,
    })


@router.get("/partials/mission-form")
def mission_form_partial(
    request: Request,
    campaign_id: str = Query(...),
    id: Optional[str] = Query(default=None),
    session: Session = Depends(get_session),
):
    """Return the mission form partial. Pre-fills campaign_id; if ?id= provided, edit mode."""
    mission = None
    if id:
        mission = session.get(Mission, UUID(id))
        if not mission:
            raise HTTPException(status_code=404)

    return templates.TemplateResponse("partials/mission_form.html", {
        "request": request,
        "mission": mission,
        "campaign_id": campaign_id,
    })


@router.get("/partials/sortie-form")
def sortie_form_partial(
    request: Request,
    mission_id: str = Query(...),
    id: Optional[str] = Query(default=None),
    session: Session = Depends(get_session),
):
    """Return the sortie form partial. Pre-fills mission_id; if ?id= provided, edit mode."""
    sortie = None
    if id:
        sortie = session.get(Sortie, UUID(id))
        if not sortie:
            raise HTTPException(status_code=404)

    return templates.TemplateResponse("partials/sortie_form.html", {
        "request": request,
        "sortie": sortie,
        "mission_id": mission_id,
    })


# ---------------------------------------------------------------------------
# Form handlers (HTML form submission -> create/update -> redirect)
# ---------------------------------------------------------------------------


@router.post("/forms/campaigns")
def create_campaign_form(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    priority_rank: int = Form(...),
    weekly_block_target: int = Form(...),
    colour: str = Form("#6366f1"),
    tags: str = Form(""),
    target_date: str = Form(""),
    session: Session = Depends(get_session),
):
    """Handle campaign creation from HTML form."""
    campaign = Campaign(
        name=name,
        description=description,
        status=CampaignStatus.active,
        priority_rank=priority_rank,
        weekly_block_target=weekly_block_target,
        colour=colour,
        tags=tags,
        target_date=date.fromisoformat(target_date) if target_date else None,
    )
    session.add(campaign)
    session.commit()

    response = HTMLResponse(content="", status_code=200)
    response.headers["HX-Redirect"] = "/dashboard"
    return response


@router.post("/forms/campaigns/{campaign_id}")
def update_campaign_form(
    request: Request,
    campaign_id: str,
    name: str = Form(...),
    description: str = Form(""),
    priority_rank: int = Form(...),
    weekly_block_target: int = Form(...),
    colour: str = Form("#6366f1"),
    tags: str = Form(""),
    target_date: str = Form(""),
    session: Session = Depends(get_session),
):
    """Handle campaign update from HTML form."""
    campaign = session.get(Campaign, UUID(campaign_id))
    if not campaign:
        raise HTTPException(status_code=404)

    campaign.name = name
    campaign.description = description
    campaign.priority_rank = priority_rank
    campaign.weekly_block_target = weekly_block_target
    campaign.colour = colour
    campaign.tags = tags
    campaign.target_date = date.fromisoformat(target_date) if target_date else None

    session.add(campaign)
    session.commit()

    response = HTMLResponse(content="", status_code=200)
    response.headers["HX-Redirect"] = "/campaigns/" + campaign_id
    return response


@router.post("/forms/missions")
def create_mission_form(
    request: Request,
    campaign_id: str = Form(...),
    name: str = Form(...),
    description: str = Form(""),
    target_date: str = Form(""),
    sort_order: int = Form(0),
    session: Session = Depends(get_session),
):
    """Handle mission creation from HTML form."""
    # Verify campaign exists
    campaign = session.get(Campaign, UUID(campaign_id))
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    mission = Mission(
        campaign_id=UUID(campaign_id),
        name=name,
        description=description,
        status=MissionStatus.not_started,
        target_date=date.fromisoformat(target_date) if target_date else None,
        sort_order=sort_order,
    )
    session.add(mission)
    session.commit()

    response = HTMLResponse(content="", status_code=200)
    response.headers["HX-Redirect"] = "/campaigns/" + campaign_id
    return response


@router.post("/forms/missions/{mission_id}")
def update_mission_form(
    request: Request,
    mission_id: str,
    campaign_id: str = Form(...),
    name: str = Form(...),
    description: str = Form(""),
    target_date: str = Form(""),
    sort_order: int = Form(0),
    session: Session = Depends(get_session),
):
    """Handle mission update from HTML form."""
    mission = session.get(Mission, UUID(mission_id))
    if not mission:
        raise HTTPException(status_code=404)

    mission.name = name
    mission.description = description
    mission.target_date = date.fromisoformat(target_date) if target_date else None
    mission.sort_order = sort_order

    session.add(mission)
    session.commit()

    response = HTMLResponse(content="", status_code=200)
    response.headers["HX-Redirect"] = "/campaigns/" + campaign_id
    return response


@router.post("/forms/sorties")
def create_sortie_form(
    request: Request,
    mission_id: str = Form(...),
    title: str = Form(...),
    cognitive_load: str = Form(...),
    description: str = Form(""),
    estimated_blocks: int = Form(1),
    sort_order: int = Form(0),
    session: Session = Depends(get_session),
):
    """Handle sortie creation from HTML form."""
    # Verify mission exists and get campaign_id for redirect
    mission = session.get(Mission, UUID(mission_id))
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")

    sortie = Sortie(
        mission_id=UUID(mission_id),
        title=title,
        cognitive_load=CognitiveLoad(cognitive_load),
        description=description if description else None,
        estimated_blocks=estimated_blocks,
        status=SortieStatus.queued,
        sort_order=sort_order,
    )
    session.add(sortie)
    session.commit()

    response = HTMLResponse(content="", status_code=200)
    response.headers["HX-Redirect"] = "/campaigns/" + str(mission.campaign_id)
    return response


@router.post("/forms/sorties/{sortie_id}")
def update_sortie_form(
    request: Request,
    sortie_id: str,
    mission_id: str = Form(...),
    title: str = Form(...),
    cognitive_load: str = Form(...),
    description: str = Form(""),
    estimated_blocks: int = Form(1),
    sort_order: int = Form(0),
    session: Session = Depends(get_session),
):
    """Handle sortie update from HTML form."""
    sortie = session.get(Sortie, UUID(sortie_id))
    if not sortie:
        raise HTTPException(status_code=404)

    # Get campaign_id for redirect
    mission = session.get(Mission, UUID(mission_id))
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")

    sortie.title = title
    sortie.cognitive_load = CognitiveLoad(cognitive_load)
    sortie.description = description if description else None
    sortie.estimated_blocks = estimated_blocks
    sortie.sort_order = sort_order

    session.add(sortie)
    session.commit()

    response = HTMLResponse(content="", status_code=200)
    response.headers["HX-Redirect"] = "/campaigns/" + str(mission.campaign_id)
    return response

"""Operations API router — daily check-in and operational endpoints."""

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from senryaku.database import get_session
from senryaku.models import DailyCheckIn
from senryaku.schemas import DailyCheckInCreate, DailyCheckInRead

router = APIRouter()


@router.post("/checkin", response_model=DailyCheckInRead, status_code=201)
def create_checkin(
    checkin: DailyCheckInCreate,
    session: Session = Depends(get_session),
):
    """Create or update a daily check-in (upsert by date)."""
    # Check if checkin already exists for this date (upsert)
    existing = session.exec(
        select(DailyCheckIn).where(DailyCheckIn.date == checkin.date)
    ).first()

    if existing:
        # Update existing
        for key, value in checkin.model_dump().items():
            setattr(existing, key, value)
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    # Create new
    db_checkin = DailyCheckIn(**checkin.model_dump())
    session.add(db_checkin)
    session.commit()
    session.refresh(db_checkin)
    return db_checkin

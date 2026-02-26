"""Drift detection service — surfaces gap between stated priorities and actual time.

Implements the drift algorithm from PRD section 8.3:

    For each active campaign:
      expected_share = weekly_block_target / sum(all_weekly_block_targets)
      actual_share   = blocks_this_week / total_blocks_this_week
      drift          = actual_share - expected_share

    Sort campaigns by abs(drift) descending.
    Flag campaigns where abs(drift) > 0.15 as misaligned.

Also computes 4-week trend (PRD section 4.5): compares this week's drift
to the average of past 3 weeks to determine if misalignments are improving,
worsening, or stable.
"""

from datetime import date, datetime, timedelta

from sqlmodel import Session, select, func, col

from senryaku.models import AAR, Campaign, CampaignStatus, Mission, Sortie
from senryaku.schemas import CampaignDrift, DriftReport

# Drift threshold: campaigns with abs(drift) > this are flagged misaligned
MISALIGNMENT_THRESHOLD = 0.15

# Trend threshold: drift change below this is considered "stable"
TREND_THRESHOLD = 0.05


def _blocks_for_campaign_in_window(
    session: Session,
    campaign_id,
    window_start: datetime,
    window_end: datetime,
) -> int:
    """Sum actual_blocks from AARs within [window_start, window_end) for a campaign."""
    result = session.exec(
        select(func.coalesce(func.sum(AAR.actual_blocks), 0))
        .join(Sortie, col(AAR.sortie_id) == col(Sortie.id))
        .join(Mission, col(Sortie.mission_id) == col(Mission.id))
        .where(Mission.campaign_id == campaign_id)
        .where(AAR.created_at >= window_start)
        .where(AAR.created_at < window_end)
    ).one()
    return int(result)


def compute_trend(
    session: Session,
    campaign: Campaign,
    current_expected_share: float,
    now: datetime | None = None,
) -> str:
    """Compare current week's drift to average of past 3 weeks.

    Returns:
        "improving" — abs(drift) is decreasing (getting closer to expected)
        "worsening" — abs(drift) is increasing (getting further from expected)
        "stable"    — abs(drift) change is within TREND_THRESHOLD
        "new"       — no past data to compare against
    """
    if now is None:
        now = datetime.utcnow()

    past_drifts = []

    for weeks_ago in range(1, 4):  # 1, 2, 3 weeks ago
        window_end = now - timedelta(days=7 * weeks_ago)
        window_start = window_end - timedelta(days=7)

        # Get blocks for this campaign in that week
        campaign_blocks = _blocks_for_campaign_in_window(
            session, campaign.id, window_start, window_end
        )

        # Get total blocks across ALL active campaigns in that week
        # (we use the same set of currently-active campaigns for consistency)
        all_campaigns = session.exec(
            select(Campaign).where(Campaign.status == CampaignStatus.active)
        ).all()

        total_blocks = 0
        for c in all_campaigns:
            total_blocks += _blocks_for_campaign_in_window(
                session, c.id, window_start, window_end
            )

        if total_blocks > 0:
            actual_share = campaign_blocks / total_blocks
        else:
            actual_share = 0.0

        past_drift = actual_share - current_expected_share
        past_drifts.append(past_drift)

    # If no past weeks had any data, this is "new"
    if not past_drifts:
        return "new"

    # Check if all past weeks had zero total blocks — treat as "new"
    # (past_drifts will all be -expected_share in that case, but we need
    #  at least one week with actual activity to make a trend judgment)
    avg_past_abs_drift = sum(abs(d) for d in past_drifts) / len(past_drifts)

    # Get current week's drift
    current_window_start = now - timedelta(days=7)
    current_blocks = _blocks_for_campaign_in_window(
        session, campaign.id, current_window_start, now
    )

    all_campaigns = session.exec(
        select(Campaign).where(Campaign.status == CampaignStatus.active)
    ).all()
    current_total = 0
    for c in all_campaigns:
        current_total += _blocks_for_campaign_in_window(
            session, c.id, current_window_start, now
        )

    if current_total > 0:
        current_actual_share = current_blocks / current_total
    else:
        current_actual_share = 0.0

    current_drift = current_actual_share - current_expected_share
    current_abs_drift = abs(current_drift)

    drift_change = current_abs_drift - avg_past_abs_drift

    if abs(drift_change) < TREND_THRESHOLD:
        return "stable"
    elif drift_change < 0:
        return "improving"
    else:
        return "worsening"


def compute_drift(session: Session, now: datetime | None = None) -> DriftReport:
    """Compute drift report for all active campaigns.

    Args:
        session: Database session.
        now: Override "current time" for testing. Defaults to datetime.utcnow().

    Returns:
        DriftReport with per-campaign drift data and misalignment statements.
    """
    if now is None:
        now = datetime.utcnow()

    campaigns = session.exec(
        select(Campaign)
        .where(Campaign.status == CampaignStatus.active)
        .order_by(Campaign.priority_rank)
    ).all()

    if not campaigns:
        return DriftReport(
            date=date.today(),
            total_blocks_this_week=0,
            campaigns=[],
            misalignment_statements=[],
        )

    # Calculate blocks this week per campaign
    week_ago = now - timedelta(days=7)

    campaign_blocks: dict = {}
    for campaign in campaigns:
        campaign_blocks[campaign.id] = _blocks_for_campaign_in_window(
            session, campaign.id, week_ago, now
        )

    total_blocks = sum(campaign_blocks.values())
    total_target = sum(c.weekly_block_target for c in campaigns)

    # Compute drift per campaign
    drifts: list[CampaignDrift] = []
    for campaign in campaigns:
        expected_share = (
            campaign.weekly_block_target / total_target if total_target > 0 else 0.0
        )
        actual_share = (
            campaign_blocks[campaign.id] / total_blocks if total_blocks > 0 else 0.0
        )
        drift = actual_share - expected_share
        is_misaligned = abs(drift) > MISALIGNMENT_THRESHOLD

        trend = compute_trend(session, campaign, expected_share, now=now)

        drifts.append(
            CampaignDrift(
                campaign_id=campaign.id,
                name=campaign.name,
                colour=campaign.colour,
                priority_rank=campaign.priority_rank,
                weekly_block_target=campaign.weekly_block_target,
                blocks_this_week=campaign_blocks[campaign.id],
                expected_share=round(expected_share, 3),
                actual_share=round(actual_share, 3),
                drift=round(drift, 3),
                is_misaligned=is_misaligned,
                trend=trend,
            )
        )

    # Sort by abs(drift) descending
    drifts.sort(key=lambda d: abs(d.drift), reverse=True)

    # Generate plain-language misalignment statements
    statements: list[str] = []
    for d in drifts:
        if d.is_misaligned:
            expected_pct = round(d.expected_share * 100)
            actual_pct = round(d.actual_share * 100)
            if d.drift > 0:
                statements.append(
                    f"{d.name} is ranked #{d.priority_rank} and received "
                    f"{actual_pct}% of blocks (target: {expected_pct}%). "
                    f"Over-allocated by {round(abs(d.drift) * 100)}%."
                )
            else:
                statements.append(
                    f"{d.name} is ranked #{d.priority_rank} but received only "
                    f"{actual_pct}% of blocks (target: {expected_pct}%). "
                    f"Under-allocated by {round(abs(d.drift) * 100)}%."
                )

    return DriftReport(
        date=date.today(),
        total_blocks_this_week=total_blocks,
        campaigns=drifts,
        misalignment_statements=statements,
    )

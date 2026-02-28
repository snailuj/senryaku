#!/usr/bin/env python3
"""Seed the database with realistic sample data.

Usage:
    python -m scripts.seed          # from project root
    python scripts/seed.py          # direct invocation
"""

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import Session, select
from senryaku.database import engine, init_db
from senryaku.models import (
    AAR, AAROutcome, Campaign, CampaignStatus, CognitiveLoad,
    DailyCheckIn, EnergyLevel, Mission, MissionStatus,
    Sortie, SortieStatus,
)


def seed():
    init_db()

    with Session(engine) as session:
        # Check if data already exists
        existing = session.exec(select(Campaign)).first()
        if existing:
            print("Database already has data. Skipping seed.")
            return

        now = datetime.utcnow()
        today = date.today()

        # -----------------------------------------------------------------
        # Campaign 1: Metaforge (software product)
        # -----------------------------------------------------------------
        metaforge = Campaign(
            name="Metaforge",
            description="Cross-domain metaphor engine for creative augmentation",
            status=CampaignStatus.active,
            priority_rank=1,
            weekly_block_target=8,
            colour="#6366f1",
            tags="software,AI,creative",
        )
        session.add(metaforge)
        session.flush()

        mf_m1 = Mission(
            campaign_id=metaforge.id,
            name="Salience Pipeline",
            description="P1 feature: salience-ranked metaphor retrieval",
            status=MissionStatus.completed,
            sort_order=1,
            completed_at=now - timedelta(days=5),
        )
        mf_m2 = Mission(
            campaign_id=metaforge.id,
            name="Concreteness Gate",
            description="P2 feature: filter metaphors by concreteness score",
            status=MissionStatus.in_progress,
            sort_order=2,
        )
        mf_m3 = Mission(
            campaign_id=metaforge.id,
            name="Live Demo",
            description="End-to-end demo with real corpus",
            status=MissionStatus.not_started,
            sort_order=3,
        )
        session.add_all([mf_m1, mf_m2, mf_m3])
        session.flush()

        # Completed sorties for M1
        mf_s1 = Sortie(
            mission_id=mf_m1.id, title="Implement MRR scoring",
            cognitive_load=CognitiveLoad.deep, estimated_blocks=2,
            status=SortieStatus.completed, sort_order=1,
            started_at=now - timedelta(days=6), completed_at=now - timedelta(days=6),
        )
        mf_s2 = Sortie(
            mission_id=mf_m1.id, title="Write salience unit tests",
            cognitive_load=CognitiveLoad.medium, estimated_blocks=1,
            status=SortieStatus.completed, sort_order=2,
            started_at=now - timedelta(days=5), completed_at=now - timedelta(days=5),
        )
        session.add_all([mf_s1, mf_s2])
        session.flush()

        # AARs for completed sorties
        session.add(AAR(
            sortie_id=mf_s1.id, energy_before=EnergyLevel.green,
            energy_after=EnergyLevel.yellow, outcome=AAROutcome.completed, actual_blocks=2,
        ))
        session.add(AAR(
            sortie_id=mf_s2.id, energy_before=EnergyLevel.yellow,
            energy_after=EnergyLevel.yellow, outcome=AAROutcome.completed, actual_blocks=1,
        ))

        # Queued sorties for M2
        mf_s3 = Sortie(
            mission_id=mf_m2.id, title="Add FastText regression model",
            cognitive_load=CognitiveLoad.deep, estimated_blocks=2,
            status=SortieStatus.queued, sort_order=1,
        )
        mf_s4 = Sortie(
            mission_id=mf_m2.id, title="Threshold tuning for concreteness",
            cognitive_load=CognitiveLoad.medium, estimated_blocks=1,
            status=SortieStatus.queued, sort_order=2,
        )
        session.add_all([mf_s3, mf_s4])

        # Queued sorties for M3
        mf_s5 = Sortie(
            mission_id=mf_m3.id, title="Prepare demo corpus",
            cognitive_load=CognitiveLoad.light, estimated_blocks=1,
            status=SortieStatus.queued, sort_order=1,
        )
        session.add(mf_s5)

        # -----------------------------------------------------------------
        # Campaign 2: Digital Garden (writing)
        # -----------------------------------------------------------------
        garden = Campaign(
            name="Digital Garden",
            description="Essay collection exploring power, gender, and systems thinking",
            status=CampaignStatus.active,
            priority_rank=2,
            weekly_block_target=5,
            colour="#10b981",
            tags="writing,essays",
        )
        session.add(garden)
        session.flush()

        dg_m1 = Mission(
            campaign_id=garden.id,
            name="Gender, Sex and Power",
            description="Draft essay on power dynamics and gender constructs",
            status=MissionStatus.in_progress,
            sort_order=1,
        )
        dg_m2 = Mission(
            campaign_id=garden.id,
            name="Systems Thinking Primer",
            description="Introductory essay on feedback loops and emergence",
            status=MissionStatus.not_started,
            sort_order=2,
        )
        session.add_all([dg_m1, dg_m2])
        session.flush()

        dg_s1 = Sortie(
            mission_id=dg_m1.id, title="Outline argument structure",
            cognitive_load=CognitiveLoad.deep, estimated_blocks=1,
            status=SortieStatus.completed, sort_order=1,
            started_at=now - timedelta(days=3), completed_at=now - timedelta(days=3),
        )
        dg_s2 = Sortie(
            mission_id=dg_m1.id, title="Draft sections 1-3",
            cognitive_load=CognitiveLoad.deep, estimated_blocks=2,
            status=SortieStatus.queued, sort_order=2,
        )
        dg_s3 = Sortie(
            mission_id=dg_m1.id, title="Research historical examples",
            cognitive_load=CognitiveLoad.medium, estimated_blocks=1,
            status=SortieStatus.queued, sort_order=3,
        )
        session.add_all([dg_s1, dg_s2, dg_s3])
        session.flush()

        session.add(AAR(
            sortie_id=dg_s1.id, energy_before=EnergyLevel.green,
            energy_after=EnergyLevel.green, outcome=AAROutcome.completed, actual_blocks=1,
        ))

        dg_s4 = Sortie(
            mission_id=dg_m2.id, title="Collect examples of feedback loops",
            cognitive_load=CognitiveLoad.light, estimated_blocks=1,
            status=SortieStatus.queued, sort_order=1,
        )
        session.add(dg_s4)

        # -----------------------------------------------------------------
        # Campaign 3: Estate Administration (family/admin)
        # -----------------------------------------------------------------
        estate = Campaign(
            name="Estate Admin",
            description="Finalise estate distribution and legal close-out",
            status=CampaignStatus.active,
            priority_rank=3,
            weekly_block_target=3,
            colour="#f59e0b",
            tags="family,legal,admin",
        )
        session.add(estate)
        session.flush()

        ea_m1 = Mission(
            campaign_id=estate.id,
            name="Tax Filing",
            description="Complete final estate tax return",
            status=MissionStatus.in_progress,
            sort_order=1,
        )
        session.add(ea_m1)
        session.flush()

        ea_s1 = Sortie(
            mission_id=ea_m1.id, title="Gather bank statements",
            cognitive_load=CognitiveLoad.light, estimated_blocks=1,
            status=SortieStatus.completed, sort_order=1,
            started_at=now - timedelta(days=2), completed_at=now - timedelta(days=2),
        )
        ea_s2 = Sortie(
            mission_id=ea_m1.id, title="Email accountant re: asset schedule",
            cognitive_load=CognitiveLoad.light, estimated_blocks=1,
            status=SortieStatus.queued, sort_order=2,
        )
        ea_s3 = Sortie(
            mission_id=ea_m1.id, title="Review draft return",
            cognitive_load=CognitiveLoad.medium, estimated_blocks=1,
            status=SortieStatus.queued, sort_order=3,
        )
        session.add_all([ea_s1, ea_s2, ea_s3])
        session.flush()

        session.add(AAR(
            sortie_id=ea_s1.id, energy_before=EnergyLevel.yellow,
            energy_after=EnergyLevel.yellow, outcome=AAROutcome.completed, actual_blocks=1,
        ))

        # -----------------------------------------------------------------
        # Campaign 4: Kagami (paused project)
        # -----------------------------------------------------------------
        kagami = Campaign(
            name="Kagami",
            description="Cognitive state tracker with dashboard and metrics engine",
            status=CampaignStatus.paused,
            priority_rank=4,
            weekly_block_target=0,
            colour="#8b5cf6",
            tags="software,cognitive",
        )
        session.add(kagami)
        session.flush()

        kg_m1 = Mission(
            campaign_id=kagami.id,
            name="V1 Build",
            description="Full v1 with 102 tests",
            status=MissionStatus.completed,
            sort_order=1,
            completed_at=now - timedelta(days=14),
        )
        session.add(kg_m1)
        session.flush()

        kg_s1 = Sortie(
            mission_id=kg_m1.id, title="Final test suite cleanup",
            cognitive_load=CognitiveLoad.medium, estimated_blocks=1,
            status=SortieStatus.completed, sort_order=1,
            started_at=now - timedelta(days=14), completed_at=now - timedelta(days=14),
        )
        session.add(kg_s1)
        session.flush()

        session.add(AAR(
            sortie_id=kg_s1.id, energy_before=EnergyLevel.green,
            energy_after=EnergyLevel.green, outcome=AAROutcome.completed, actual_blocks=1,
        ))

        # -----------------------------------------------------------------
        # Today's check-in
        # -----------------------------------------------------------------
        checkin = DailyCheckIn(
            date=today,
            energy_level=EnergyLevel.green,
            available_blocks=4,
            focus_note="Deep work morning, admin in afternoon",
        )
        session.add(checkin)

        # Yesterday's check-in
        session.add(DailyCheckIn(
            date=today - timedelta(days=1),
            energy_level=EnergyLevel.yellow,
            available_blocks=3,
        ))

        session.commit()
        print("Seeded: 4 campaigns, 7 missions, 14 sorties, 5 AARs, 2 check-ins")


if __name__ == "__main__":
    seed()

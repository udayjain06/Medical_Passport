"""archive dependent profiles and preserve timeline source references

Revision ID: 9a7c2d41b6e0
Revises: 6fafbd8b528d
Create Date: 2026-11-05
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9a7c2d41b6e0"
down_revision: str | None = "6fafbd8b528d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("patient_profiles", sa.Column("archived_at", sa.DateTime(timezone=True)))
    with op.batch_alter_table("timeline_events", recreate="always") as batch:
        batch.add_column(sa.Column("source_extraction_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("source_candidate_id", sa.String(length=64), nullable=True))
        batch.add_column(
            sa.Column("source_document_filename", sa.String(length=255), nullable=True)
        )
        batch.add_column(sa.Column("source_document_checksum", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("conflict_group", sa.String(length=80), nullable=True))
        batch.add_column(sa.Column("uncertainty_note", sa.String(length=1000), nullable=True))
        batch.create_foreign_key(
            "fk_timeline_events_source_extraction_id_document_extractions",
            "document_extractions",
            ["source_extraction_id"],
            ["id"],
            ondelete="SET NULL",
        )

    bind = op.get_bind()
    events = sa.table(
        "timeline_events",
        sa.column("id", sa.Uuid()),
        sa.column("source_document_id", sa.Uuid()),
        sa.column("source_page", sa.Integer()),
        sa.column("title", sa.String()),
        sa.column("source_extraction_id", sa.Uuid()),
        sa.column("source_candidate_id", sa.String()),
        sa.column("source_document_filename", sa.String()),
        sa.column("source_document_checksum", sa.String()),
    )
    documents = sa.table(
        "medical_documents",
        sa.column("id", sa.Uuid()),
        sa.column("original_filename", sa.String()),
        sa.column("sha256_checksum", sa.String()),
    )
    extractions = sa.table(
        "document_extractions",
        sa.column("id", sa.Uuid()),
        sa.column("document_id", sa.Uuid()),
        sa.column("candidates", sa.JSON()),
    )
    source_events = bind.execute(
        sa.select(
            events.c.id,
            events.c.source_document_id,
            events.c.source_page,
            events.c.title,
            documents.c.original_filename,
            documents.c.sha256_checksum,
        ).join(documents, events.c.source_document_id == documents.c.id)
    ).mappings()
    for event in source_events:
        bind.execute(
            sa.update(events)
            .where(events.c.id == event["id"])
            .values(
                source_document_filename=event["original_filename"],
                source_document_checksum=event["sha256_checksum"],
            )
        )

    for extraction_id, document_id, candidates in bind.execute(
        sa.select(extractions.c.id, extractions.c.document_id, extractions.c.candidates)
    ):
        candidates = candidates or []
        for candidate in candidates:
            candidate.setdefault("candidate_id", str(uuid.uuid4()))
        bind.execute(
            sa.update(extractions)
            .where(extractions.c.id == extraction_id)
            .values(candidates=candidates)
        )
        matching_events = bind.execute(
            sa.select(events.c.id, events.c.source_page, events.c.title).where(
                events.c.source_document_id == document_id
            )
        ).mappings()
        for event in matching_events:
            for candidate in candidates:
                candidate_title = (
                    f"{str(candidate.get('field', '')).replace('_', ' ').title()}: "
                    f"{candidate.get('value', '')}"
                )[:200]
                if candidate_title == event["title"] and (
                    candidate.get("source_page") is None
                    or candidate.get("source_page") == event["source_page"]
                ):
                    bind.execute(
                        sa.update(events)
                        .where(events.c.id == event["id"])
                        .values(
                            source_extraction_id=extraction_id,
                            source_candidate_id=candidate["candidate_id"],
                        )
                    )
                    break


def downgrade() -> None:
    with op.batch_alter_table("timeline_events", recreate="always") as batch:
        batch.drop_constraint(
            "fk_timeline_events_source_extraction_id_document_extractions", type_="foreignkey"
        )
        for name in (
            "uncertainty_note",
            "conflict_group",
            "source_document_checksum",
            "source_document_filename",
            "source_candidate_id",
            "source_extraction_id",
        ):
            batch.drop_column(name)
    op.drop_column("patient_profiles", "archived_at")

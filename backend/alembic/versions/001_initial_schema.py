"""initial schema

Revision ID: 001
Revises:
Create Date: 2025-01-01

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "trends",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("keyword", sa.String(500), nullable=False),
        sa.Column("niche", sa.String(100), nullable=False),
        sa.Column("score", sa.Float(), server_default="0.0"),
        sa.Column("raw_data", postgresql.JSONB(), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("discovered_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_trends_niche", "trends", ["niche"])
    op.create_index("ix_trends_source", "trends", ["source"])

    op.create_table(
        "topics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("niche", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(50), server_default="pending"),
        sa.Column("priority", sa.Integer(), server_default="5"),
        sa.Column("trend_id", sa.Integer(), sa.ForeignKey("trends.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_topics_status", "topics", ["status"])
    op.create_index("ix_topics_niche", "topics", ["niche"])

    op.create_table(
        "scripts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("topic_id", sa.Integer(), sa.ForeignKey("topics.id"), nullable=False),
        sa.Column("hook", sa.Text(), nullable=False),
        sa.Column("main_content", sa.Text(), nullable=False),
        sa.Column("cta", sa.Text(), nullable=False),
        sa.Column("scenes", postgresql.JSONB(), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("hashtags", postgresql.JSONB(), nullable=True),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("quality_feedback", postgresql.JSONB(), nullable=True),
        sa.Column("model_used", sa.String(200), nullable=True),
        sa.Column("voice_style", sa.String(100), nullable=True),
        sa.Column("estimated_duration_seconds", sa.Integer(), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1"),
        sa.Column("status", sa.String(50), server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_scripts_topic_id", "scripts", ["topic_id"])
    op.create_index("ix_scripts_status", "scripts", ["status"])

    op.create_table(
        "videos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("topic_id", sa.Integer(), sa.ForeignKey("topics.id"), nullable=False),
        sa.Column("script_id", sa.Integer(), sa.ForeignKey("scripts.id"), nullable=False),
        sa.Column("status", sa.String(50), server_default="queued"),
        sa.Column("audio_path", sa.Text(), nullable=True),
        sa.Column("image_paths", postgresql.JSONB(), nullable=True),
        sa.Column("video_path", sa.Text(), nullable=True),
        sa.Column("thumbnail_path", sa.Text(), nullable=True),
        sa.Column("render_time_seconds", sa.Float(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("file_size_mb", sa.Float(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("render_metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_videos_status", "videos", ["status"])

    op.create_table(
        "publishing_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("video_id", sa.Integer(), sa.ForeignKey("videos.id"), nullable=False),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("platform_video_id", sa.String(200), nullable=True),
        sa.Column("status", sa.String(50), server_default="pending"),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "analytics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "publishing_record_id",
            sa.Integer(),
            sa.ForeignKey("publishing_records.id"),
            nullable=False,
        ),
        sa.Column("views", sa.Integer(), server_default="0"),
        sa.Column("likes", sa.Integer(), server_default="0"),
        sa.Column("comments", sa.Integer(), server_default="0"),
        sa.Column("shares", sa.Integer(), server_default="0"),
        sa.Column("watch_time_avg_seconds", sa.Float(), nullable=True),
        sa.Column("retention_rate", sa.Float(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("analytics")
    op.drop_table("publishing_records")
    op.drop_table("videos")
    op.drop_table("scripts")
    op.drop_table("topics")
    op.drop_table("trends")

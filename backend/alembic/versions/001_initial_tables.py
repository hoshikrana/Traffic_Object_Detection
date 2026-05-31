"""Initial tables: jobs, traffic_snapshots, incidents

Revision ID: 001
Revises: None
Create Date: 2024-01-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Jobs table
    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("status", sa.String(20), default="queued", index=True),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("input_path", sa.String(500), nullable=False),
        sa.Column("output_path", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_frames", sa.Integer, nullable=True),
        sa.Column("processed_frames", sa.Integer, nullable=True),
        sa.Column("progress_pct", sa.Float, default=0.0),
        sa.Column("error_message", sa.Text, nullable=True),
    )

    # Traffic snapshots table
    op.create_table(
        "traffic_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            index=True,
        ),
        sa.Column("frame_number", sa.Integer, nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("total_vehicles", sa.Integer, default=0),
        sa.Column("cars", sa.Integer, default=0),
        sa.Column("vans", sa.Integer, default=0),
        sa.Column("trucks", sa.Integer, default=0),
        sa.Column("buses", sa.Integer, default=0),
        sa.Column("others", sa.Integer, default=0),
        sa.Column("avg_speed_kmh", sa.Float, default=0.0),
        sa.Column("max_speed_kmh", sa.Float, default=0.0),
        sa.Column("congestion_level", sa.String(20), default="LOW"),
        sa.Column("crossing_total", sa.Integer, default=0),
        sa.Column("active_incidents_count", sa.Integer, default=0),
    )

    # Try to create TimescaleDB hypertable (graceful fallback)
    try:
        op.execute(
            "SELECT create_hypertable('traffic_snapshots', 'timestamp', "
            "if_not_exists => TRUE);"
        )
    except Exception:
        pass  # TimescaleDB not available — standard table works fine

    # Incidents table
    op.create_table(
        "incidents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            index=True,
        ),
        sa.Column("track_id", sa.Integer, nullable=False),
        sa.Column("incident_type", sa.String(50), default="stopped_vehicle"),
        sa.Column("frame_number", sa.Integer, nullable=False),
        sa.Column("x", sa.Float, nullable=False),
        sa.Column("y", sa.Float, nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("resolved", sa.Boolean, default=False),
    )


def downgrade() -> None:
    op.drop_table("incidents")
    op.drop_table("traffic_snapshots")
    op.drop_table("jobs")

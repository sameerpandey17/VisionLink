"""
Alembic migration: add frame_id_seq PostgreSQL sequence.

IDENTIFIED ISSUE — In-Memory Frame Counter
-------------------------------------------
The original ingest.py used:

    _frame_counter = itertools.count(1)
    frame_id = next(_frame_counter)

This is a Python-level counter, stored only in process memory. Two problems:

  1. On server restart: the counter resets to 1.
     Any new frames inserted after restart share frame_ids with frames
     inserted before the restart. The DB has no uniqueness constraint on
     frame_id, so there is no error — just silent data corruption.

  2. With multiple workers: Worker 1 counts 1,2,3... and Worker 2 ALSO
     counts 1,2,3... independently. Both workers insert frame_id=1 into
     the same session, making the frame_id field meaningless.

FIX — PostgreSQL SEQUENCE
--------------------------
A SEQUENCE is a database-level monotonic counter. It is:
  - Crash-safe: Postgres writes sequence state to WAL before returning.
  - Multi-process safe: SELECT nextval('frame_id_seq') is an atomic
    operation — no two callers get the same value, ever.
  - Fast: sequences use no row locks and no MVCC overhead.

Used via: SELECT nextval('frame_id_seq') in crud.get_next_frame_id().

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-08
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE IF NOT EXISTS frame_id_seq START 1 INCREMENT 1 NO CYCLE")


def downgrade() -> None:
    op.execute("DROP SEQUENCE IF EXISTS frame_id_seq")

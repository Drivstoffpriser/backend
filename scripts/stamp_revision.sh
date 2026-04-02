#!/usr/bin/env bash
# Usage: ./scripts/stamp_revision.sh <revision>
# Stamps the database at a specific migration revision without running migrations.
# Useful when the DB schema already exists and you want to mark it as at a certain point.
#
# Examples:
#   ./scripts/stamp_revision.sh head       # stamp as fully up-to-date
#   ./scripts/stamp_revision.sh base       # stamp as having no migrations applied
#   ./scripts/stamp_revision.sh abc123ef   # stamp at a specific revision ID

set -e

REVISION=${1:-head}

uv run alembic stamp "$REVISION"
echo "Stamped database at revision: $REVISION"

"""Post-write hook: update alembic/versions/head with the new revision ID."""

import sys
from pathlib import Path

script_path = Path(sys.argv[1])
revision = script_path.stem.split("_")[0]
head_file = script_path.parent / "head"
head_file.write_text(revision + "\n")

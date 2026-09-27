#!/usr/bin/env bash
# Sentinel verification — run from backend/ with the venv present.
#
#   bash scripts/verify.sh
#
# Three stages, cheapest first, stopping at the first failure. Stage 1 catches
# schema and import errors in a few seconds; stage 3 is the full suite.
#
# The stages are ordered deliberately: when something is broken, the useful
# output is the *first* failure, and a 400-line pytest tail buries it.

set -uo pipefail

cd "$(dirname "$0")/.." || exit 1

PY="${PY:-venv/bin/python}"
if [ ! -x "$PY" ]; then
    echo "No interpreter at $PY — activate the venv or set PY=path/to/python" >&2
    exit 1
fi

echo "=== 1/3  Models: can the schema be built? ==="
"$PY" - <<'EOF' || exit 1
from sqlalchemy import create_engine
from app.core.database import Base
import app.models  # noqa: F401  — importing the package registers every model
engine = create_engine("sqlite:///./_modelcheck.db")
Base.metadata.create_all(engine)
print(f"OK: {len(Base.metadata.tables)} tables built")
EOF

echo
echo "=== 2/3  App: does it import? ==="
"$PY" -c "
import app.main
print(f'OK: app imports, {len(app.main.app.routes)} routes registered')
" || exit 1

echo
echo "=== 3/3  Tests ==="
"$PY" -m pytest tests/ -q
status=$?

echo
if [ $status -eq 0 ]; then
    echo "All stages passed."
else
    echo "Tests failed (exit $status). Stages 1 and 2 passed, so this is a"
    echo "behavioural failure rather than a broken import or schema."
fi
exit $status

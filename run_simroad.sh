#!/usr/bin/env bash
# Run from anywhere; all generated files stay beside this script under runs/.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
for candidate in "$ROOT/.venv/bin/python" "$ROOT/.venv/Scripts/python.exe" "$ROOT/.venv-runner/bin/python" "$ROOT/.venv-runner/Scripts/python.exe"; do
  if [[ -x "$candidate" ]] && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 11))' >/dev/null 2>&1; then
    exec "$candidate" "$ROOT/scripts/run_all.py" "$@"
  fi
done
for candidate in python3.12 python3 python; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 11))' >/dev/null 2>&1; then
    exec "$candidate" "$ROOT/scripts/run_all.py" "$@"
  fi
done
printf '%s\n' 'Python 3.11+ is required (3.12 recommended). Install Python, then rerun this script.' >&2
exit 1

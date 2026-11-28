#!/usr/bin/env bash
set -euo pipefail

SOURCE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME="${1:-"$HOME/JGA/OASIS-Research-Runtime"}"
RUNTIME="$(python3 -c 'import os,sys; print(os.path.abspath(os.path.expanduser(sys.argv[1])))' "$RUNTIME")"

[[ -f "$SOURCE/pyproject.toml" ]] || { echo "Not an AVA Python project: $SOURCE" >&2; exit 2; }
command -v python3 >/dev/null 2>&1 || { echo "Python 3.11+ is required." >&2; exit 2; }
python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 2)' || { echo "Python 3.11+ is required." >&2; exit 2; }

if [[ -e "$RUNTIME" ]]; then
  [[ -d "$RUNTIME" ]] || { echo "Runtime path exists and is not a directory: $RUNTIME" >&2; exit 2; }
  [[ -z "$(find "$RUNTIME" -mindepth 1 -maxdepth 1 -print -quit)" ]] || {
    echo "Refusing to overwrite non-empty runtime directory: $RUNTIME" >&2; exit 2;
  }
else
  mkdir -p "$RUNTIME"
fi

python3 -m venv "$RUNTIME/.venv"
"$RUNTIME/.venv/bin/python" -m pip install --no-deps -e "$SOURCE"
"$RUNTIME/.venv/bin/python" -m ava_military.doctor --source "$SOURCE" --runtime "$RUNTIME" > "$RUNTIME/foundation-doctor.json"
echo "AVA research foundation installed. This is NOT the integrated AVA/OASIS runtime."
echo "Runtime: $RUNTIME"
echo "Doctor report: $RUNTIME/foundation-doctor.json"
echo "No service, listener, firewall rule, model, or privileged component was installed."

#!/usr/bin/env bash
# Build a portable runtime lock without packages from the shared development pod.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
python3 -m venv "$WORK/venv"
PYTHON="$WORK/venv/bin/python"
# Only the public package index: private/internal packages must never leak in.
export PIP_CONFIG_FILE=/dev/null
export PIP_INDEX_URL=https://pypi.org/simple
export PIP_EXTRA_INDEX_URL=
"$PYTHON" -m pip install --disable-pip-version-check -r "$ROOT/backend/requirements.in"
"$PYTHON" -m pip check
"$PYTHON" -m pip freeze > "$ROOT/backend/requirements.txt"
printf '\nRuntime dependencies generated from a clean environment.\n'
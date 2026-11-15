#!/bin/zsh
set -e

SCRIPT_DIR="${0:A:h}"
ISDT_PYTHON="$HOME/isdt-env/bin/python"

if [[ ! -x "$ISDT_PYTHON" ]]; then
  ISDT_PYTHON="$(command -v python3)"
fi

cd "$SCRIPT_DIR"
exec "$ISDT_PYTHON" main.py

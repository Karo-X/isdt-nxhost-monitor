#!/bin/zsh
set -euo pipefail

PROJECT_DIR=${0:A:h}
"$HOME/isdt-env/bin/python" "$PROJECT_DIR/usb_autostart.py" --uninstall
echo
echo "Der automatische USB-Start wurde entfernt."
read -k 1 "?Taste drücken …"

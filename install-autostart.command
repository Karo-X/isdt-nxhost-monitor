#!/bin/zsh
set -euo pipefail

PROJECT_DIR=${0:A:h}
"$HOME/isdt-env/bin/python" "$PROJECT_DIR/usb_autostart.py" --install
echo
echo "Fertig. Dieses Fenster kann geschlossen werden."
read -k 1 "?Taste drücken …"

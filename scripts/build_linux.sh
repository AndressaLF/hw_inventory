#!/usr/bin/env bash
# Gera dist/hw-inventory a partir deste Linux. Não altera o hw-inventory.exe do Windows.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! python3 -c "import tkinter" >/dev/null 2>&1; then
  echo "Instale o Tk do Python antes de continuar. Veja docs/DEPENDENCIAS_SO.md" >&2
  exit 1
fi

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
.venv/bin/pip install -r requirements.txt pyinstaller

.venv/bin/pyinstaller \
  --noconfirm \
  --onefile \
  --windowed \
  --name hw-inventory \
  --distpath "$ROOT/dist" \
  --workpath "$ROOT/build/pyinstaller" \
  --specpath "$ROOT/build" \
  --paths "$ROOT" \
  --add-data "$ROOT/hw_inventory/fonts:hw_inventory/fonts" \
  "$ROOT/hw_inventory/__main__.py"

chmod +x "$ROOT/dist/hw-inventory"
echo "Binário gerado: $ROOT/dist/hw-inventory"
echo "Uso: sudo -E $ROOT/dist/hw-inventory"

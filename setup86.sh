#!/bin/sh
# SPDX-License-Identifier: MIT  (Copyright (c) 2026 Ariel Juszczyk, see LICENSE)
# Start the Disc Builder app on Linux, from any folder.
#   ./setup86.sh             start the app
#   ./setup86.sh --desktop   add Setup86, with its icon, to the desktop's app menu and dock
# Uses the venv ~/.venvs/setup86 (see README, Installation), or python3 if there is none.
DIR=$(cd "$(dirname "$0")" && pwd)
if [ "$1" = --desktop ]; then
    APPS=${XDG_DATA_HOME:-$HOME/.local/share}/applications
    mkdir -p "$APPS"
    cat > "$APPS/setup86.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Setup86
Comment=Build DOS game CDs from eXoDOS
Exec="$DIR/setup86.sh"
Icon=$DIR/art/setup86-icon-256.png
StartupWMClass=setup86
Categories=Game;
Terminal=false
EOF
    echo "added $APPS/setup86.desktop"
    exit 0
fi
PY=$HOME/.venvs/setup86/bin/python
[ -x "$PY" ] || PY=python3
exec "$PY" "$DIR/setup86_gui.py" "$@"

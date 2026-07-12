#!/usr/bin/env bash
# Launch Bonzi natively. Forces XWayland (xcb) so window positioning, dragging
# and always-on-top behave on KDE/GNOME Wayland sessions.
set -euo pipefail
cd "$(dirname "$0")"
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"
export PYTHONPATH="src:${PYTHONPATH:-}"
exec python3 -m bonzi.app "$@"

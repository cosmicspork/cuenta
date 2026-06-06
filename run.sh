#!/usr/bin/env sh
cd "$(dirname "$0")"
uv run cuenta
echo
read -r -p "Press Enter to close..." _

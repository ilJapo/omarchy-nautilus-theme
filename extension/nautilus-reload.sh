#!/bin/bash
# Omarchy Theme Hook: Trigger in-process GTK4 CSS reload in GNOME Nautilus
# Triggers the omarchy_live_theme.py nautilus-python extension without quitting or restarting Nautilus.

TRIGGER_FILE="$HOME/.local/state/omarchy/nautilus-reload"

mkdir -p "$(dirname "$TRIGGER_FILE")"
touch "$TRIGGER_FILE" 2>/dev/null

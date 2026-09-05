#!/usr/bin/env bash
#
# nautilus-gtk-refresh.sh
#
# Shared logic called by both the theme-set and font-set Omarchy hooks.
# It takes the gtk.css already rendered by Omarchy's template engine into
# the current theme's staging directory, stamps in the live system font,
# deploys it to the paths GTK actually reads, and restarts Nautilus so the
# new stylesheet is picked up.
#
# Why the restart is required:
# libadwaita reads the user stylesheet (~/.config/gtk-4.0/gtk.css) only
# once, at process startup. Closing an open Files window is not enough --
# Nautilus runs as a D-Bus-activatable --gapplication-service daemon that
# survives in the background and keeps painting the stale theme. `nautilus
# -q` terminates that daemon; it respawns on demand the next time Files (or
# a D-Bus caller) needs it, and re-reads gtk.css at that point.
#
# Why the file is always rewritten from scratch (never sed -i in place):
# ~/.config/gtk-4.0/gtk.css may be a symlink in some setups. `sed -i`
# replaces the target path outright, silently turning a symlink into a
# disconnected regular file. Rendering to a temp file and `install`-ing it
# over the destination avoids that failure mode entirely, whatever the
# destination currently is (symlink, regular file, or missing).

set -uo pipefail

THEME_CSS="$HOME/.local/state/omarchy/current/theme/gtk.css"
DEST_GTK4="$HOME/.config/gtk-4.0/gtk.css"

# Always try to restart Nautilus on exit, even if something above fails --
# a half-applied font update should never leave the daemon un-refreshed.
trap 'nautilus -q 2>/dev/null || true' EXIT

mkdir -p "$(dirname "$DEST_GTK4")" "$(dirname "$DEST_GTK3")"

# Nothing to do if the active theme hasn't rendered gtk.css yet (e.g. the
# template was just installed and no theme switch has happened since).
if [ ! -f "$THEME_CSS" ]; then
    echo "nautilus-gtk-refresh: $THEME_CSS not found yet -- switch theme once to generate it." >&2
    exit 0
fi

CURRENT_FONT="$(gsettings get org.gnome.desktop.interface font-name 2>/dev/null \
    | sed -e "s/'//g" -e 's/ [0-9.]*$//')"
CURRENT_FONT="${CURRENT_FONT:-Sans}"

TMP_CSS="$(mktemp)"
sed -E "s/font-family:[^;]+;/font-family: '${CURRENT_FONT}', monospace;/g" \
    "$THEME_CSS" > "$TMP_CSS"

install -m 644 "$TMP_CSS" "$DEST_GTK4"
rm -f "$TMP_CSS"

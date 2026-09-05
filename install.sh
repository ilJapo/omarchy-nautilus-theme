#!/usr/bin/env bash
# Installs the dynamic Nautilus theme: GTK4 template + auto-refresh hooks.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Installing GTK4 template"
mkdir -p "$HOME/.config/omarchy/themed"
cp "$REPO_DIR/gtk.css.tpl" "$HOME/.config/omarchy/themed/gtk.css.tpl"

echo "==> Installing refresh script"
mkdir -p "$HOME/.local/bin"
cp "$REPO_DIR/bin/nautilus-gtk-refresh.sh" "$HOME/.local/bin/nautilus-gtk-refresh.sh"
chmod +x "$HOME/.local/bin/nautilus-gtk-refresh.sh"

echo "==> Installing hooks"
mkdir -p "$HOME/.config/omarchy/hooks/theme-set.d" "$HOME/.config/omarchy/hooks/font-set.d"
cp "$REPO_DIR/hooks/theme-set.d/nautilus-theme-set.sh" \
   "$HOME/.config/omarchy/hooks/theme-set.d/nautilus-theme-set.sh"
cp "$REPO_DIR/hooks/font-set.d/nautilus-font-set.sh" \
   "$HOME/.config/omarchy/hooks/font-set.d/nautilus-font-set.sh"
chmod +x "$HOME/.config/omarchy/hooks/theme-set.d/nautilus-theme-set.sh" \
         "$HOME/.config/omarchy/hooks/font-set.d/nautilus-font-set.sh"

echo
echo "Installed."
echo "The template only gets rendered on the NEXT theme switch. Trigger one now"
echo "by re-applying the current theme (this is enough to generate gtk.css):"
echo
echo "    omarchy theme set \"\$(cat \"\$HOME/.local/state/omarchy/current/theme.name\")\""
echo
echo "From then on, both theme switches and font changes refresh Nautilus automatically."

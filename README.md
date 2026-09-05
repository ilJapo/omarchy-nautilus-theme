# Omarchy Quattro Dynamic Nautilus Theme

<img width="2560" height="1600" alt="screenshot-2026-09-05_01-27-26" src="https://github.com/user-attachments/assets/69b3c0f7-43ab-47d2-b2ac-8922d4bc00d0" />

A dynamic GTK4 CSS template for the Nautilus file manager, designed specifically for the Omarchy Quattro desktop environment.

Whenever you switch your Omarchy theme, this template automatically generates a new GTK4 stylesheet to match your system's background, foreground, and accent colors. It also keeps Nautilus in sync with your live system font, and forces the running Nautilus process to reload the new stylesheet immediately — no manual restart, no logout.

## How it works

Three moving parts, all included in this repo:

1. **`gtk.css.tpl`** — a template using Omarchy's `{{ placeholder }}` syntax. Installed to `~/.config/omarchy/themed/gtk.css.tpl`, Omarchy renders it into `~/.local/state/omarchy/current/theme/gtk.css` on every theme switch.
2. **`bin/nautilus-gtk-refresh.sh`** — takes that rendered file, stamps in the *current* system font (read live from `gsettings`), deploys it to `~/.config/gtk-4.0/gtk.css` and restarts Nautilus.
3. **`hooks/theme-set.d/` and `hooks/font-set.d/`** — one-line Omarchy hook wrappers that call the script above whenever the theme or the system font changes.

### Why Nautilus has to restart

GTK4/libadwaita reads the user stylesheet (`~/.config/gtk-4.0/gtk.css`) only once, at process startup. Nautilus runs as a D-Bus-activatable `--gapplication-service` daemon — closing an open Files window is **not** enough to make it pick up a new stylesheet, since the background daemon survives and keeps painting the old theme. `nautilus -q` terminates that daemon; it respawns automatically the next time Files (or anything calling it over D-Bus) is opened, and reads the fresh `gtk.css` at that point. There is no live-reload mechanism in libadwaita for custom `@define-color` overrides — a toggle of `org.gnome.desktop.interface color-scheme` does **not** achieve this, since that setting only switches between Adwaita's own built-in light/dark palettes, not user-supplied stylesheets.

### Why the CSS file is always rewritten, never edited in place

`~/.config/gtk-4.0/gtk.css` may end up being a symlink in some setups. Editing it with `sed -i` replaces whatever is at that path outright, which silently turns a symlink into a disconnected regular file — after that, future theme switches keep rendering the *source* correctly but the file GTK actually reads stops updating. The refresh script always renders to a temp file and `install`s it over the destination, which is safe regardless of what currently sits there.

## Requirements

* Omarchy Quattro (uses `~/.local/state/omarchy/current/theme/`, not the pre-Quattro `~/.config/omarchy/current/theme/` path).
* GTK4 / libadwaita apps (GNOME 43+).

## Installation

### Automatic

```bash
git clone https://github.com/ilJapo/omarchy-nautilus-theme.git
cd omarchy-nautilus-theme
./install.sh
```

The installer copies the template, the refresh script, and both hooks into place, and prints the one command you need to run once to force the first render.

### Manual

1. Install the template:
   ```bash
   mkdir -p ~/.config/omarchy/themed
   cp gtk.css.tpl ~/.config/omarchy/themed/gtk.css.tpl
   ```
2. Install the refresh script:
   ```bash
   mkdir -p ~/.local/bin
   cp bin/nautilus-gtk-refresh.sh ~/.local/bin/
   chmod +x ~/.local/bin/nautilus-gtk-refresh.sh
   ```
3. Install the hooks:
   ```bash
   mkdir -p ~/.config/omarchy/hooks/theme-set.d ~/.config/omarchy/hooks/font-set.d
   cp hooks/theme-set.d/nautilus-theme-set.sh ~/.config/omarchy/hooks/theme-set.d/
   cp hooks/font-set.d/nautilus-font-set.sh   ~/.config/omarchy/hooks/font-set.d/
   chmod +x ~/.config/omarchy/hooks/theme-set.d/nautilus-theme-set.sh \
             ~/.config/omarchy/hooks/font-set.d/nautilus-font-set.sh
   ```
4. Trigger the first render (the template only renders on the *next* theme switch, so re-apply the current one):
   ```bash
   omarchy theme set "$(cat ~/.local/state/omarchy/current/theme.name)"
   ```

From that point on, switching your Omarchy theme or changing your system font both refresh Nautilus automatically.

## Troubleshooting

* **Colors don't update after a theme switch** — check that `~/.local/state/omarchy/current/theme/gtk.css` itself changed (`diff` it against `~/.config/gtk-4.0/gtk.css`, minus the `font-family` line). If the source file is wrong, the issue is in template rendering, not the hooks. If the source is right but the destination isn't, check that both hook files are executable (`ls -l ~/.config/omarchy/hooks/*/nautilus-*.sh`) — a hook that lost its `+x` bit is silently skipped by Omarchy.
* **Font doesn't update** — run `bash -x ~/.local/bin/nautilus-gtk-refresh.sh` to see exactly where it stops; a `gsettings get` failure falls back to `Sans` rather than aborting.
* **Nautilus doesn't restart** — run `nautilus -q; echo $?` on its own to rule out an unrelated Nautilus issue.

## Notes

* **This script extends theme integration to all GTK4/Libadwaita applications,** perfectly matching them to your active Omarchy theme. If you want other GNOME applications to automatically restart and apply the new theme, you can simply add them inside the nautilus-theme-set.sh and natilus-font-set.sh files.
* Requires GTK4 (GNOME 43+).
* `gtk.css.tpl` bundles JetBrains Mono as its default; the refresh script immediately overwrites that with your live system font on every run, so having the font installed is only needed if you don't run the hooks (i.e. a purely static install).

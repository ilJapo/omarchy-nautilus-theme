"""
Omarchy Live Theme Extension for GNOME Nautilus.

Enables instant, in-process GTK4 stylesheet reloading when Omarchy themes change,
eliminating the need to quit or restart Nautilus (no window flicker, tab loss, or UI freezes).
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, List

from gi import require_version

require_version("Nautilus", "4.1")
require_version("Gtk", "4.0")
require_version("Gdk", "4.0")

from gi.repository import Gdk, Gio, GLib, GObject, Gtk, Nautilus  # noqa: E402

try:
    require_version("Adw", "1")
    from gi.repository import Adw
except (ValueError, ImportError):
    Adw = None  # type: ignore[assignment]

if TYPE_CHECKING:
    pass


class OmarchyLiveThemeExtension(GObject.GObject, Nautilus.MenuProvider):
    """Nautilus extension providing in-process GTK4 CSS reload on theme switch."""

    def __init__(
        self,
        css_path: str | None = None,
        trigger_path: str | None = None,
        theme_dir_path: str | None = None,
    ) -> None:
        super().__init__()
        self.css_path = css_path or os.path.expanduser("~/.config/gtk-4.0/gtk.css")
        self.trigger_path = trigger_path or os.path.expanduser(
            "~/.local/state/omarchy/nautilus-reload"
        )
        self.theme_dir_path = theme_dir_path or os.path.expanduser(
            "~/.local/state/omarchy/current/theme"
        )
        self.provider: Gtk.CssProvider | None = None
        self._monitors: list[Gio.FileMonitor] = []
        self._settings: Gio.Settings | None = None
        self._debounce_source_id: int | None = None
        self.reload_count = 0

        # Defer initialization to main loop idle to guarantee Gdk.Display is ready
        GLib.idle_add(self._setup)

    def _setup(self) -> bool:
        if self.provider is not None:
            return GLib.SOURCE_REMOVE

        display = Gdk.Display.get_default()
        if not display:
            # Retry next idle if display is not yet initialized
            return GLib.SOURCE_CONTINUE

        self.provider = Gtk.CssProvider()
        # STYLE_PROVIDER_PRIORITY_USER (800) + 10 = 810 to override static ~/.config/gtk-4.0/gtk.css
        Gtk.StyleContext.add_provider_for_display(
            display,
            self.provider,
            Gtk.STYLE_PROVIDER_PRIORITY_USER + 10,
        )

        # Initial stylesheet load
        self.reload_css()

        # Set up filesystem monitors & desktop interface listeners
        self._setup_monitors()
        return GLib.SOURCE_REMOVE

    def reload_css(self) -> bool:
        """Reload the CSS provider from disk."""
        if self.provider is None:
            return False

        if not os.path.exists(self.css_path):
            return False

        try:
            if os.path.getsize(self.css_path) == 0:
                return False
            self.provider.load_from_path(self.css_path)
            self.reload_count += 1
            return True
        except Exception as err:
            print(f"[omarchy-live-theme] Failed to reload CSS from {self.css_path}: {err}")
            return False

    def _setup_monitors(self) -> None:
        """Watch the reload trigger file, active theme directory, and desktop settings."""
        trigger_dir = os.path.dirname(self.trigger_path)
        if not os.path.exists(trigger_dir):
            try:
                os.makedirs(trigger_dir, exist_ok=True)
            except OSError:
                pass

        if not os.path.exists(self.trigger_path):
            try:
                open(self.trigger_path, "a").close()
            except OSError:
                pass

        # 1. Monitor the dedicated trigger file
        trigger_file = Gio.File.new_for_path(self.trigger_path)
        trigger_monitor = trigger_file.monitor_file(Gio.FileMonitorFlags.NONE, None)
        trigger_monitor.connect("changed", self._on_file_changed)
        self._monitors.append(trigger_monitor)

        # 2. Monitor ~/.config/gtk-4.0/gtk.css directly as fallback
        if os.path.exists(self.css_path):
            css_file = Gio.File.new_for_path(self.css_path)
            css_monitor = css_file.monitor_file(Gio.FileMonitorFlags.NONE, None)
            css_monitor.connect("changed", self._on_file_changed)
            self._monitors.append(css_monitor)

        # 3. Monitor ~/.local/state/omarchy/current/theme directory for atomic theme swaps
        if os.path.exists(self.theme_dir_path):
            theme_dir = Gio.File.new_for_path(self.theme_dir_path)
            theme_dir_monitor = theme_dir.monitor_directory(Gio.FileMonitorFlags.NONE, None)
            theme_dir_monitor.connect("changed", self._on_file_changed)
            self._monitors.append(theme_dir_monitor)

        # 4. Connect to GNOME desktop interface settings for instant color-scheme switches
        try:
            self._settings = Gio.Settings.new("org.gnome.desktop.interface")
            self._settings.connect("changed::color-scheme", self._on_setting_changed)
            self._settings.connect("changed::gtk-theme", self._on_setting_changed)
            self._settings.connect("changed::icon-theme", self._on_setting_changed)
        except Exception:
            pass

    def _on_setting_changed(self, _settings: Gio.Settings, _key: str) -> None:
        """Trigger debounced CSS reload immediately when color-scheme or theme changes."""
        self._schedule_reload()

    def _on_file_changed(
        self,
        _monitor: Gio.FileMonitor,
        _file: Gio.File,
        _other_file: Gio.File | None,
        _event_type: Gio.FileMonitorEvent,
    ) -> None:
        """Trigger debounced CSS reload when filesystem changes occur."""
        self._schedule_reload()

    def _schedule_reload(self) -> None:
        """Debounce rapid successive events (GSettings change + atomic directory swap + hook)."""
        if self._debounce_source_id is not None:
            GLib.source_remove(self._debounce_source_id)

        self._debounce_source_id = GLib.timeout_add(50, self._debounced_reload)

    def _debounced_reload(self) -> bool:
        self._debounce_source_id = None
        self.reload_css()
        return GLib.SOURCE_REMOVE

    def get_file_items(self, *args: object) -> List[Nautilus.MenuItem]:
        return []

    def get_background_items(self, *args: object) -> List[Nautilus.MenuItem]:
        return []

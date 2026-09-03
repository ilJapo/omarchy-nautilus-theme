#!/usr/bin/env python3
"""
Automated Test & Validation Harness for Omarchy Nautilus GTK4 Theme.

Validates template rendering, variable substitution, color mixing functions,
GTK4 CSS parsing validity via Gtk.CssProvider, and template structural rules.
"""

from __future__ import annotations

import math
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest

# Ensure GTK 4.0 is required before importing Gtk
try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk
except (ValueError, ImportError) as e:
    Gtk = None
    GTK_IMPORT_ERROR = str(e)
else:
    GTK_IMPORT_ERROR = None

# Attempt to import live theming extension for Nautilus testing
try:
    import gi
    gi.require_version("Nautilus", "4.1")
    gi.require_version("Gtk", "4.0")
    gi.require_version("Gdk", "4.0")
    from gi.repository import Nautilus, Gdk, GLib, Gio
    EXTENSION_DIR = str(Path(__file__).resolve().parent.parent / "extension")
    if EXTENSION_DIR not in sys.path:
        sys.path.insert(0, EXTENSION_DIR)
    from omarchy_live_theme import OmarchyLiveThemeExtension
except (ValueError, ImportError) as e:
    OmarchyLiveThemeExtension = None
    LIVE_THEME_IMPORT_ERROR = str(e)
else:
    LIVE_THEME_IMPORT_ERROR = None

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "gtk.css.tpl"

# Standard test palettes matching Omarchy theme specifications
DARK_PALETTE: dict[str, str] = {
    "background": "#1e1e2e",
    "foreground": "#cdd6f4",
    "accent": "#89b4fa",
    "color8": "#585b70",
    "selection": "#45475a",
    "selection_foreground": "#cdd6f4",
    "bright_foreground": "#cdd6f4",
    "red": "#f38ba8",
    "green": "#a6e3a1",
    "yellow": "#f9e2af",
    "blue": "#89b4fa",
    "magenta": "#cba6f7",
    "cyan": "#94e2d5",
    "theme_selected_bg_color": "#89b4fa",
    "theme_selected_fg_color": "#1e1e2e",
    "sidebar_backdrop_color": "#181825",
    "secondary_sidebar_bg_color": "#181825",
}

LIGHT_PALETTE: dict[str, str] = {
    "background": "#eff1f5",
    "foreground": "#4c4f69",
    "accent": "#1e66f5",
    "color8": "#9ca0b0",
    "selection": "#bcc0cc",
    "selection_foreground": "#4c4f69",
    "bright_foreground": "#4c4f69",
    "red": "#d20f39",
    "green": "#40a02b",
    "yellow": "#df8e1d",
    "blue": "#1e66f5",
    "magenta": "#8839ef",
    "cyan": "#179299",
    "theme_selected_bg_color": "#1e66f5",
    "theme_selected_fg_color": "#eff1f5",
    "sidebar_backdrop_color": "#e6e9ef",
    "secondary_sidebar_bg_color": "#e6e9ef",
}

OLED_PALETTE: dict[str, str] = {
    "background": "#000000",
    "foreground": "#ffffff",
    "accent": "#e5a50a",
    "color8": "#222222",
    "selection": "#333333",
    "selection_foreground": "#ffffff",
    "bright_foreground": "#ffffff",
    "red": "#ff5555",
    "green": "#50fa7b",
    "yellow": "#f1fa8c",
    "blue": "#bd93f9",
    "magenta": "#ff79c6",
    "cyan": "#8be9fd",
    "theme_selected_bg_color": "#e5a50a",
    "theme_selected_fg_color": "#000000",
    "sidebar_backdrop_color": "#000000",
    "secondary_sidebar_bg_color": "#000000",
}


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert a 6-digit hex color string (e.g. #1e1e2e or 1e1e2e) to (r, g, b) tuple."""
    clean_hex = hex_color.lstrip("#")
    if len(clean_hex) != 6:
        raise ValueError(f"Invalid hex color length: '{hex_color}'")
    r = int(clean_hex[0:2], 16)
    g = int(clean_hex[2:4], 16)
    b = int(clean_hex[4:6], 16)
    return r, g, b


def rgb_to_hex(r: int, g: int, b: int) -> str:
    """Convert (r, g, b) integers to a 6-digit lowercase hex color string."""
    r_clamped = max(0, min(255, r))
    g_clamped = max(0, min(255, g))
    b_clamped = max(0, min(255, b))
    return f"#{r_clamped:02x}{g_clamped:02x}{b_clamped:02x}"


def mix_color(start_hex: str, end_hex: str, amount: str | float) -> str:
    """
    Linearly interpolate RGB between two hex colors, replicating Omarchy's mix engine.

    Amount can be a percentage string ('6%', '50%'), decimal string ('0.06', '0.5'),
    number > 1 ('6' treated as 6%), or float.
    """
    if isinstance(amount, str):
        cleaned = amount.strip()
        if cleaned.endswith("%"):
            amt = float(cleaned[:-1]) / 100.0
        else:
            amt = float(cleaned)
            if amt > 1.0:
                amt = amt / 100.0
    else:
        amt = float(amount)
        if amt > 1.0:
            amt = amt / 100.0

    amt = max(0.0, min(1.0, amt))

    s_r, s_g, s_b = hex_to_rgb(start_hex)
    e_r, e_g, e_b = hex_to_rgb(end_hex)

    # Replicate standard Omarchy rounding: int(val + 0.5)
    red = int(s_r * (1.0 - amt) + e_r * amt + 0.5)
    green = int(s_g * (1.0 - amt) + e_g * amt + 0.5)
    blue = int(s_b * (1.0 - amt) + e_b * amt + 0.5)

    return rgb_to_hex(red, green, blue)


def render_template(template_str: str, palette: dict[str, str]) -> str:
    """
    Renders an Omarchy template string using the provided color palette dictionary.

    Supports:
      - {{ mix start_key end_key amount }}
      - {{ mix_strip start_key end_key amount }}
      - {{ mix_rgb start_key end_key amount }}
      - {{ key }}
      - {{ key_strip }}
      - {{ key_rgb }}
    """
    rendered = template_str

    # 1. Process mix functions: {{ mix var1 var2 percentage }}
    mix_pattern = re.compile(
        r"\{\{\s*(mix(?:_strip|_rgb)?)\s+([A-Za-z0-9_]+)\s+([A-Za-z0-9_]+)\s+([0-9]+(?:\.[0-9]+)?%?)\s*\}\}"
    )

    def replace_mix(match: re.Match) -> str:
        fn_name = match.group(1)
        start_key = match.group(2)
        end_key = match.group(3)
        amount_val = match.group(4)

        if start_key not in palette or end_key not in palette:
            return match.group(0)

        mixed = mix_color(palette[start_key], palette[end_key], amount_val)
        if fn_name == "mix":
            return mixed
        elif fn_name == "mix_strip":
            return mixed.lstrip("#")
        elif fn_name == "mix_rgb":
            r, g, b = hex_to_rgb(mixed)
            return f"{r},{g},{b}"
        return match.group(0)

    rendered = mix_pattern.sub(replace_mix, rendered)

    # 2. Process variable placeholders: {{ var }}, {{ var_strip }}, {{ var_rgb }}
    var_pattern = re.compile(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}")

    def replace_var(match: re.Match) -> str:
        token = match.group(1)
        if token in palette:
            return palette[token]
        elif token.endswith("_strip") and token[:-6] in palette:
            return palette[token[:-6]].lstrip("#")
        elif token.endswith("_rgb") and token[:-4] in palette:
            r, g, b = hex_to_rgb(palette[token[:-4]])
            return f"{r},{g},{b}"
        return match.group(0)

    rendered = var_pattern.sub(replace_var, rendered)
    return rendered


def find_unrendered_tokens(rendered_content: str) -> list[str]:
    """Return a list of unrendered {{ ... }} tokens found in the rendered text."""
    return re.findall(r"\{\{.*?\}\}", rendered_content)


def validate_gtk4_css(css_text: str) -> list[str]:
    """
    Parses and validates CSS content using GTK4's CssProvider.

    Returns a list of parser error/warning strings. If empty, CSS is fully valid.
    """
    if Gtk is None:
        raise RuntimeError(f"GTK4 GObject bindings not available: {GTK_IMPORT_ERROR}")

    errors: list[str] = []
    provider = Gtk.CssProvider()

    def on_parsing_error(
        _provider: Gtk.CssProvider,
        section: Gtk.CssSection,
        error: BaseException,
    ) -> None:
        loc_str = "unknown location"
        if hasattr(section, "get_start_location"):
            start_loc = section.get_start_location()
            if start_loc:
                loc_str = f"line {start_loc.lines + 1}:{start_loc.line_chars + 1}"
        err_msg = getattr(error, "message", str(error))
        errors.append(f"GTK4 CSS parsing error at {loc_str}: {err_msg}")

    provider.connect("parsing-error", on_parsing_error)

    try:
        if hasattr(provider, "load_from_string"):
            provider.load_from_string(css_text)
        else:
            provider.load_from_data(css_text.encode("utf-8"))
    except Exception as exc:
        errors.append(f"CssProvider load exception: {exc}")

    return errors


def find_font_size_declarations(content: str) -> list[dict[str, str | int]]:
    """
    Parses CSS/template text and returns all font-size declarations with line numbers,
    selectors, and values.
    """
    # Replace comments with same number of newlines to preserve line numbering
    def repl_comment(m: re.Match) -> str:
        return "\n" * m.group(0).count("\n")

    clean = re.sub(r"/\*.*?\*/", repl_comment, content, flags=re.DOTALL)

    declarations: list[dict[str, str | int]] = []
    for match in re.finditer(r"([^{}]+)\{([^{}]+)\}", clean):
        raw_selector = match.group(1).strip()
        # Clean up any preceding statement semicolons (e.g. from @define-color)
        if ";" in raw_selector:
            raw_selector = raw_selector.split(";")[-1].strip()
        body = match.group(2)
        match_start = match.start(2)

        for prop_match in re.finditer(r"font-size\s*:\s*([^;]+);", body):
            prop_offset = match_start + prop_match.start(0)
            line_num = clean[:prop_offset].count("\n") + 1
            declarations.append({
                "selector": raw_selector,
                "value": prop_match.group(1).strip(),
                "line": line_num,
            })

    return declarations


class TestTemplateEngine(unittest.TestCase):
    """Unit tests for template substitution and color mixing."""

    def test_mix_color_percentage(self) -> None:
        self.assertEqual(mix_color("#1e1e2e", "#cdd6f4", "6%"), "#29293a")
        self.assertEqual(mix_color("#1e1e2e", "#cdd6f4", "8%"), "#2c2d3e")
        self.assertEqual(mix_color("#1e1e2e", "#cdd6f4", "3%"), "#232434")
        self.assertEqual(mix_color("#000000", "#ffffff", "50%"), "#808080")
        self.assertEqual(mix_color("#112233", "#445566", "0%"), "#112233")
        self.assertEqual(mix_color("#112233", "#445566", "100%"), "#445566")

    def test_mix_color_decimals_and_integers(self) -> None:
        self.assertEqual(mix_color("#112233", "#445566", "0.25"), "#1e2f40")
        self.assertEqual(mix_color("#112233", "#445566", "25"), "#1e2f40")
        self.assertEqual(mix_color("#112233", "#445566", 0.5), "#2b3c4d")

    def test_render_simple_variables(self) -> None:
        palette = {"background": "#1e1e2e", "foreground": "#cdd6f4"}
        tpl = "@define-color bg {{ background }}; @define-color fg {{ foreground }};"
        rendered = render_template(tpl, palette)
        self.assertEqual(rendered, "@define-color bg #1e1e2e; @define-color fg #cdd6f4;")

    def test_render_rgb_and_strip_modifiers(self) -> None:
        palette = {"background": "#1e1e2e"}
        tpl = "bg_hex: {{ background }}; bg_strip: {{ background_strip }}; bg_rgb: {{ background_rgb }};"
        rendered = render_template(tpl, palette)
        self.assertEqual(rendered, "bg_hex: #1e1e2e; bg_strip: 1e1e2e; bg_rgb: 30,30,46;")

    def test_render_mix_templates(self) -> None:
        palette = {"background": "#1e1e2e", "foreground": "#cdd6f4"}
        tpl = "@define-color card {{ mix background foreground 6% }};"
        rendered = render_template(tpl, palette)
        self.assertEqual(rendered, "@define-color card #29293a;")

    def test_unrendered_token_detection(self) -> None:
        palette = {"background": "#1e1e2e"}
        tpl = "@define-color bg {{ background }}; @define-color missing {{ missing_key }};"
        rendered = render_template(tpl, palette)
        tokens = find_unrendered_tokens(rendered)
        self.assertEqual(tokens, ["{{ missing_key }}"])


class TestPalettes(unittest.TestCase):
    """Validates template rendering across dark, light, and OLED palettes."""

    def setUp(self) -> None:
        self.assertTrue(TEMPLATE_PATH.is_file(), f"Template file not found at {TEMPLATE_PATH}")
        self.template_content = TEMPLATE_PATH.read_text(encoding="utf-8")

    def test_render_dark_palette_has_no_unrendered_tokens(self) -> None:
        rendered = render_template(self.template_content, DARK_PALETTE)
        unrendered = find_unrendered_tokens(rendered)
        self.assertEqual(
            unrendered,
            [],
            f"Found unrendered tokens in dark palette output: {unrendered}",
        )

    def test_render_light_palette_has_no_unrendered_tokens(self) -> None:
        rendered = render_template(self.template_content, LIGHT_PALETTE)
        unrendered = find_unrendered_tokens(rendered)
        self.assertEqual(
            unrendered,
            [],
            f"Found unrendered tokens in light palette output: {unrendered}",
        )

    def test_render_oled_palette_has_no_unrendered_tokens(self) -> None:
        rendered = render_template(self.template_content, OLED_PALETTE)
        unrendered = find_unrendered_tokens(rendered)
        self.assertEqual(
            unrendered,
            [],
            f"Found unrendered tokens in OLED palette output: {unrendered}",
        )


@unittest.skipIf(Gtk is None, f"GTK4 GObject bindings not available: {GTK_IMPORT_ERROR}")
class TestGtk4CssValidation(unittest.TestCase):
    """Validates that rendered CSS parses cleanly in GTK4 without errors."""

    def setUp(self) -> None:
        self.assertTrue(TEMPLATE_PATH.is_file(), f"Template file not found at {TEMPLATE_PATH}")
        self.template_content = TEMPLATE_PATH.read_text(encoding="utf-8")

    def test_gtk4_css_validity_dark_palette(self) -> None:
        rendered = render_template(self.template_content, DARK_PALETTE)
        errors = validate_gtk4_css(rendered)
        self.assertEqual(errors, [], f"GTK4 CSS parsing errors in dark theme:\n" + "\n".join(errors))

    def test_gtk4_css_validity_light_palette(self) -> None:
        rendered = render_template(self.template_content, LIGHT_PALETTE)
        errors = validate_gtk4_css(rendered)
        self.assertEqual(errors, [], f"GTK4 CSS parsing errors in light theme:\n" + "\n".join(errors))

    def test_gtk4_css_validity_oled_palette(self) -> None:
        rendered = render_template(self.template_content, OLED_PALETTE)
        errors = validate_gtk4_css(rendered)
        self.assertEqual(errors, [], f"GTK4 CSS parsing errors in OLED theme:\n" + "\n".join(errors))


class TestTemplateStructure(unittest.TestCase):
    """
    Enforces architectural and structural CSS rules on gtk.css.tpl:
      - font-size: 85% must only be set once at the root window.nautilus-window
      - font-size must not be duplicated on child selectors (view, headerbar, placessidebar, etc.)
    """

    def setUp(self) -> None:
        self.assertTrue(TEMPLATE_PATH.is_file(), f"Template file not found at {TEMPLATE_PATH}")
        self.template_content = TEMPLATE_PATH.read_text(encoding="utf-8")

    def test_no_duplicate_child_font_sizes(self) -> None:
        declarations = find_font_size_declarations(self.template_content)

        # We expect font-size: 85% ONLY on window.nautilus-window root selector
        child_violations: list[str] = []
        root_count = 0

        for decl in declarations:
            selector = str(decl["selector"]).strip()
            line = decl["line"]
            val = decl["value"]

            # Normalize selector whitespace
            norm_sel = re.sub(r"\s+", " ", selector)

            if norm_sel == "window.nautilus-window":
                root_count += 1
            else:
                child_violations.append(
                    f"Line {line}: Selector '{norm_sel}' redeclares font-size: {val};"
                )

        error_msg = (
            f"Found {len(child_violations)} redundant child font-size declaration(s) in gtk.css.tpl:\n"
            + "\n".join(child_violations)
            + "\nfont-size: 85% should only be declared on root 'window.nautilus-window' to prevent cascading compounding bugs."
        )

        self.assertEqual(child_violations, [], error_msg)
        self.assertEqual(
            root_count,
            1,
            f"Expected exactly 1 root window.nautilus-window font-size declaration, found {root_count}",
        )


@unittest.skipIf(
    OmarchyLiveThemeExtension is None,
    f"Nautilus / GTK4 PyGObject bindings not available: {LIVE_THEME_IMPORT_ERROR}",
)
class TestLiveThemeExtension(unittest.TestCase):
    """Validate in-process live theming Nautilus extension behavior."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.css_file = Path(self.tmp_dir.name) / "gtk.css"
        self.trigger_file = Path(self.tmp_dir.name) / "nautilus-reload"
        self.css_file.write_text("window.nautilus-window { background-color: #123456; }")

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_extension_menu_items_empty(self) -> None:
        ext = OmarchyLiveThemeExtension(
            css_path=str(self.css_file),
            trigger_path=str(self.trigger_file),
        )
        self.assertEqual(ext.get_file_items(), [])
        self.assertEqual(ext.get_background_items(), [])

    def test_live_css_reload(self) -> None:
        ext = OmarchyLiveThemeExtension(
            css_path=str(self.css_file),
            trigger_path=str(self.trigger_file),
        )
        # Force immediate setup on default display
        ext._setup()
        self.assertIsNotNone(ext.provider)
        self.assertEqual(ext.reload_count, 1)

        # Update CSS file content and trigger reload
        self.css_file.write_text("window.nautilus-window { background-color: #abcdef; }")
        success = ext.reload_css()
        self.assertTrue(success)
        self.assertEqual(ext.reload_count, 2)


if __name__ == "__main__":
    print(f"Running Omarchy Nautilus GTK4 Theme Validation Suite against: {TEMPLATE_PATH}")
    unittest.main(verbosity=2)

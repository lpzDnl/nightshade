#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════╗
║  NIGHTSHADE — Blue Light Filter for Raspberry Pi ║
║  Software overlay for displays without gamma LUT  ║
╚══════════════════════════════════════════════════╝

Works around Pi 5 V3D driver limitation by drawing
transparent colored overlays on all screens.

Dependencies: python3-gi, python3-gi-cairo, gir1.2-gtk-3.0, gir1.2-appindicator3-0.1
"""

import gi
gi.require_version('Gtk', '3.0')
try:
    gi.require_version('AyatanaAppIndicator3', '0.1')
    from gi.repository import AyatanaAppIndicator3 as AppIndicator3
    HAS_INDICATOR = True
except (ValueError, ImportError):
    try:
        gi.require_version('AppIndicator3', '0.1')
        from gi.repository import AppIndicator3
        HAS_INDICATOR = True
    except (ValueError, ImportError):
        HAS_INDICATOR = False

from gi.repository import Gtk, Gdk, GLib, GdkPixbuf
import cairo
import subprocess
import os
import json
import signal
import sys

APP_NAME = "nightshade"
CONFIG_DIR = os.path.expanduser(f"~/.config/{APP_NAME}")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

# Color temperature presets (R, G, B multipliers relative to full white)
# These simulate color temperatures by tinting the overlay
PRESETS = {
    "Sunlight (6500K)":   {"r": 0, "g": 0, "b": 0, "temp": 6500},
    "Halogen (4200K)":    {"r": 30, "g": 15, "b": 0, "temp": 4200},
    "Warm White (3500K)": {"r": 45, "g": 20, "b": 0, "temp": 3500},
    "Candle (2700K)":     {"r": 60, "g": 25, "b": 0, "temp": 2700},
    "Ember (2000K)":      {"r": 80, "g": 30, "b": 0, "temp": 2000},
    "Deep Amber (1500K)": {"r": 100, "g": 35, "b": 0, "temp": 1500},
}

DEFAULT_CONFIG = {
    "enabled": False,
    "intensity": 40,  # 0-100
    "preset": "Warm White (3500K)",
    "custom_r": 45,
    "custom_g": 20,
    "custom_b": 0,
}


class OverlayWindow:
    """A transparent click-through overlay window for a single monitor."""

    def __init__(self, monitor_geometry):
        self.window = Gtk.Window(type=Gtk.WindowType.POPUP)
        self.window.set_app_paintable(True)
        self.window.set_decorated(False)
        self.window.set_skip_taskbar_hint(True)
        self.window.set_skip_pager_hint(True)
        self.window.set_accept_focus(False)
        self.window.set_keep_above(True)
        self.window.stick()

        # Set size and position to cover the monitor
        self.window.move(monitor_geometry.x, monitor_geometry.y)
        self.window.set_default_size(monitor_geometry.width, monitor_geometry.height)
        self.window.resize(monitor_geometry.width, monitor_geometry.height)

        # Enable transparency
        screen = self.window.get_screen()
        visual = screen.get_rgba_visual()
        if visual:
            self.window.set_visual(visual)

        # Click-through: let all input pass through
        self.window.connect("draw", self._on_draw)
        self.window.connect("realize", self._on_realize)

        self.color = (1.0, 0.5, 0.0)  # RGB
        self.alpha = 0.0
        self.visible = False

    def _on_realize(self, widget):
        """Make the window input-transparent (click-through)."""
        region = cairo.Region(cairo.RectangleInt(0, 0, 0, 0))
        self.window.input_shape_combine_region(region)
        # Also set as non-interactive via window type hint
        self.window.get_window().set_type_hint(Gdk.WindowTypeHint.NOTIFICATION)

    def _on_draw(self, widget, cr):
        """Draw the colored overlay."""
        cr.set_source_rgba(self.color[0], self.color[1], self.color[2], self.alpha)
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.paint()
        return False

    def update(self, r, g, b, intensity):
        """Update overlay color and intensity."""
        self.color = (r / 255.0, g / 255.0, b / 255.0)
        # Map intensity (0-100) to alpha (0.0 - 0.45)
        # Cap at 0.45 so the screen stays usable
        self.alpha = (intensity / 100.0) * 0.45
        self.window.queue_draw()

    def show(self):
        if not self.visible:
            self.window.show_all()
            self.visible = True
            # Re-apply input shape after showing
            GLib.idle_add(self._reapply_passthrough)

    def hide(self):
        if self.visible:
            self.window.hide()
            self.visible = False

    def _reapply_passthrough(self):
        """Re-apply click-through after window is mapped."""
        if self.window.get_realized():
            region = cairo.Region(cairo.RectangleInt(0, 0, 0, 0))
            self.window.input_shape_combine_region(region)
        return False

    def destroy(self):
        self.window.destroy()


class NightshadeApp:
    """Main application managing overlays and system tray."""

    def __init__(self):
        self.config = self._load_config()
        self.overlays = []
        self.control_window = None
        self._setup_overlays()
        self._setup_tray()

        if self.config["enabled"]:
            self._enable_filter()

    # ── Config ──────────────────────────────────────────────

    def _load_config(self):
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, "r") as f:
                    cfg = json.load(f)
                    # Merge with defaults for any missing keys
                    merged = {**DEFAULT_CONFIG, **cfg}
                    return merged
        except Exception:
            pass
        return dict(DEFAULT_CONFIG)

    def _save_config(self):
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(CONFIG_FILE, "w") as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save config: {e}")

    # ── Overlays ────────────────────────────────────────────

    def _setup_overlays(self):
        """Create an overlay window for each monitor."""
        display = Gdk.Display.get_default()
        # Try the modern GdkMonitor API first, fall back to screen
        try:
            n_monitors = display.get_n_monitors()
            for i in range(n_monitors):
                monitor = display.get_monitor(i)
                geom = monitor.get_geometry()
                overlay = OverlayWindow(geom)
                self.overlays.append(overlay)
        except AttributeError:
            screen = display.get_default_screen()
            n_monitors = screen.get_n_monitors()
            for i in range(n_monitors):
                geom = screen.get_monitor_geometry(i)
                overlay = OverlayWindow(geom)
                self.overlays.append(overlay)

        print(f"[Nightshade] Created overlays for {len(self.overlays)} monitor(s)")

    def _get_color(self):
        """Get current RGB values from preset or custom."""
        preset = self.config.get("preset", "")
        if preset in PRESETS:
            p = PRESETS[preset]
            return p["r"], p["g"], p["b"]
        return self.config["custom_r"], self.config["custom_g"], self.config["custom_b"]

    def _update_overlays(self):
        """Update all overlay windows with current settings."""
        r, g, b = self._get_color()
        intensity = self.config["intensity"]
        for overlay in self.overlays:
            overlay.update(r, g, b, intensity)

    def _enable_filter(self):
        self.config["enabled"] = True
        self._update_overlays()
        for overlay in self.overlays:
            overlay.show()
        self._save_config()
        self._update_tray_icon()

    def _disable_filter(self):
        self.config["enabled"] = False
        for overlay in self.overlays:
            overlay.hide()
        self._save_config()
        self._update_tray_icon()

    def _toggle_filter(self, *args):
        if self.config["enabled"]:
            self._disable_filter()
        else:
            self._enable_filter()

    # ── System Tray ─────────────────────────────────────────

    def _create_tray_icon(self, color_hex):
        """Create a simple colored circle icon for the tray."""
        size = 22
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
        cr = cairo.Context(surface)

        # Draw circle
        cr.arc(size / 2, size / 2, size / 2 - 1, 0, 2 * 3.14159)

        if self.config["enabled"]:
            # Warm amber when active
            cr.set_source_rgb(0.95, 0.65, 0.15)
        else:
            # Gray when inactive
            cr.set_source_rgb(0.5, 0.5, 0.5)

        cr.fill_preserve()
        cr.set_source_rgb(0.2, 0.2, 0.2)
        cr.set_line_width(1)
        cr.stroke()

        # Inner highlight
        cr.arc(size / 2, size / 2, size / 2 - 4, 0, 2 * 3.14159)
        if self.config["enabled"]:
            cr.set_source_rgba(1.0, 0.9, 0.5, 0.4)
        else:
            cr.set_source_rgba(0.7, 0.7, 0.7, 0.3)
        cr.fill()

        # Save to tmp file for AppIndicator
        icon_path = os.path.join(CONFIG_DIR, "tray_icon.png")
        os.makedirs(CONFIG_DIR, exist_ok=True)
        surface.write_to_png(icon_path)
        return icon_path

    def _update_tray_icon(self):
        """Refresh the tray icon to reflect current state."""
        if HAS_INDICATOR and hasattr(self, 'indicator'):
            icon_path = self._create_tray_icon("#F0A020" if self.config["enabled"] else "#808080")
            self.indicator.set_icon_full(icon_path, APP_NAME)
        elif hasattr(self, 'status_icon'):
            icon_path = self._create_tray_icon("#F0A020" if self.config["enabled"] else "#808080")
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(icon_path)
            self.status_icon.set_from_pixbuf(pixbuf)

    def _setup_tray(self):
        """Set up system tray icon with menu."""
        if HAS_INDICATOR:
            self._setup_app_indicator()
        else:
            self._setup_status_icon()

    def _setup_app_indicator(self):
        """Use AppIndicator3 for modern tray support."""
        icon_path = self._create_tray_icon("#F0A020")
        self.indicator = AppIndicator3.Indicator.new(
            APP_NAME,
            icon_path,
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS
        )
        self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self.indicator.set_menu(self._build_menu())

    def _setup_status_icon(self):
        """Fallback to GtkStatusIcon for XFCE compatibility."""
        icon_path = self._create_tray_icon("#F0A020")
        self.status_icon = Gtk.StatusIcon()
        pixbuf = GdkPixbuf.Pixbuf.new_from_file(icon_path)
        self.status_icon.set_from_pixbuf(pixbuf)
        self.status_icon.set_tooltip_text("Nightshade — Blue Light Filter")
        self.status_icon.set_visible(True)
        self.status_icon.connect("activate", self._toggle_filter)
        self.status_icon.connect("popup-menu", self._on_status_icon_popup)

    def _on_status_icon_popup(self, icon, button, time):
        menu = self._build_menu()
        menu.popup(None, None, Gtk.StatusIcon.position_menu, icon, button, time)

    def _build_menu(self):
        """Build the right-click context menu."""
        menu = Gtk.Menu()

        # Toggle
        toggle_label = "⏻  Disable Filter" if self.config["enabled"] else "⏻  Enable Filter"
        item_toggle = Gtk.MenuItem(label=toggle_label)
        item_toggle.connect("activate", self._toggle_filter)
        menu.append(item_toggle)

        menu.append(Gtk.SeparatorMenuItem())

        # Intensity submenu
        item_intensity = Gtk.MenuItem(label=f"◐  Intensity: {self.config['intensity']}%")
        sub_intensity = Gtk.Menu()
        for val in [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]:
            label = f"{'● ' if val == self.config['intensity'] else '  '}{val}%"
            item = Gtk.MenuItem(label=label)
            item.connect("activate", self._set_intensity, val)
            sub_intensity.append(item)
        item_intensity.set_submenu(sub_intensity)
        menu.append(item_intensity)

        menu.append(Gtk.SeparatorMenuItem())

        # Presets submenu
        item_presets = Gtk.MenuItem(label="🌡  Color Temperature")
        sub_presets = Gtk.Menu()
        current_preset = self.config.get("preset", "")
        for name in PRESETS:
            label = f"{'● ' if name == current_preset else '  '}{name}"
            item = Gtk.MenuItem(label=label)
            item.connect("activate", self._set_preset, name)
            sub_presets.append(item)
        item_presets.set_submenu(sub_presets)
        menu.append(item_presets)

        menu.append(Gtk.SeparatorMenuItem())

        # Settings window
        item_settings = Gtk.MenuItem(label="⚙  Settings...")
        item_settings.connect("activate", self._show_settings)
        menu.append(item_settings)

        menu.append(Gtk.SeparatorMenuItem())

        # Quit
        item_quit = Gtk.MenuItem(label="✕  Quit")
        item_quit.connect("activate", self._quit)
        menu.append(item_quit)

        menu.show_all()
        return menu

    def _refresh_menu(self):
        """Refresh the indicator menu to reflect state changes."""
        if HAS_INDICATOR and hasattr(self, 'indicator'):
            self.indicator.set_menu(self._build_menu())

    def _set_intensity(self, widget, value):
        self.config["intensity"] = value
        if self.config["enabled"]:
            self._update_overlays()
        self._save_config()
        self._refresh_menu()

    def _set_preset(self, widget, name):
        self.config["preset"] = name
        if self.config["enabled"]:
            self._update_overlays()
            for overlay in self.overlays:
                overlay.show()
        self._save_config()
        self._refresh_menu()

    # ── Settings Window ─────────────────────────────────────

    def _show_settings(self, *args):
        if self.control_window and self.control_window.get_visible():
            self.control_window.present()
            return

        win = Gtk.Window(title="Nightshade Settings")
        win.set_default_size(380, 320)
        win.set_resizable(False)
        win.set_position(Gtk.WindowPosition.CENTER)
        win.set_keep_above(True)
        self.control_window = win

        # Styling
        css = Gtk.CssProvider()
        css.load_from_data(b"""
            window {
                background-color: #1a1a2e;
            }
            label {
                color: #e0d8c8;
                font-family: monospace;
            }
            .title-label {
                font-size: 18px;
                font-weight: bold;
                color: #f0a030;
            }
            .subtitle-label {
                font-size: 11px;
                color: #887766;
            }
            scale trough {
                background-color: #2a2a3e;
                min-height: 6px;
                border-radius: 3px;
            }
            scale highlight {
                background-color: #f0a030;
                min-height: 6px;
                border-radius: 3px;
            }
            scale slider {
                background-color: #f0a030;
                min-width: 16px;
                min-height: 16px;
                border-radius: 8px;
            }
            button {
                background-color: #2a2a3e;
                color: #e0d8c8;
                border: 1px solid #3a3a4e;
                border-radius: 4px;
                padding: 6px 16px;
                font-family: monospace;
            }
            button:hover {
                background-color: #3a3a4e;
            }
            combobox button {
                background-color: #2a2a3e;
                color: #e0d8c8;
            }
        """)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        vbox.set_margin_top(20)
        vbox.set_margin_bottom(20)
        vbox.set_margin_start(24)
        vbox.set_margin_end(24)

        # Title
        title = Gtk.Label(label="NIGHTSHADE")
        title.get_style_context().add_class("title-label")
        vbox.pack_start(title, False, False, 0)

        subtitle = Gtk.Label(label="Blue Light Filter for Raspberry Pi")
        subtitle.get_style_context().add_class("subtitle-label")
        vbox.pack_start(subtitle, False, False, 4)

        # Enable toggle
        hbox_toggle = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        lbl_enable = Gtk.Label(label="Filter")
        lbl_enable.set_halign(Gtk.Align.START)
        switch = Gtk.Switch()
        switch.set_active(self.config["enabled"])
        switch.connect("state-set", self._on_switch_toggled)
        hbox_toggle.pack_start(lbl_enable, True, True, 0)
        hbox_toggle.pack_end(switch, False, False, 0)
        vbox.pack_start(hbox_toggle, False, False, 8)

        # Intensity slider
        lbl_intensity = Gtk.Label(label="Intensity")
        lbl_intensity.set_halign(Gtk.Align.START)
        vbox.pack_start(lbl_intensity, False, False, 0)

        self.intensity_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 5, 100, 5
        )
        self.intensity_scale.set_value(self.config["intensity"])
        self.intensity_scale.set_draw_value(True)
        self.intensity_scale.set_value_pos(Gtk.PositionType.RIGHT)
        self.intensity_scale.connect("value-changed", self._on_intensity_changed)
        vbox.pack_start(self.intensity_scale, False, False, 0)

        # Preset selector
        lbl_preset = Gtk.Label(label="Color Temperature")
        lbl_preset.set_halign(Gtk.Align.START)
        vbox.pack_start(lbl_preset, False, False, 4)

        self.preset_combo = Gtk.ComboBoxText()
        preset_names = list(PRESETS.keys())
        for name in preset_names:
            self.preset_combo.append_text(name)
        current = self.config.get("preset", "Warm White (3500K)")
        if current in preset_names:
            self.preset_combo.set_active(preset_names.index(current))
        self.preset_combo.connect("changed", self._on_preset_changed)
        vbox.pack_start(self.preset_combo, False, False, 0)

        # Close button
        btn_close = Gtk.Button(label="Close")
        btn_close.connect("clicked", lambda w: win.hide())
        vbox.pack_end(btn_close, False, False, 8)

        win.add(vbox)
        win.connect("delete-event", lambda w, e: w.hide() or True)
        win.show_all()

    def _on_switch_toggled(self, switch, state):
        if state:
            self._enable_filter()
        else:
            self._disable_filter()
        self._refresh_menu()

    def _on_intensity_changed(self, scale):
        val = int(scale.get_value())
        self.config["intensity"] = val
        if self.config["enabled"]:
            self._update_overlays()
        self._save_config()

    def _on_preset_changed(self, combo):
        name = combo.get_active_text()
        if name:
            self.config["preset"] = name
            if self.config["enabled"]:
                self._update_overlays()
            self._save_config()

    # ── Lifecycle ───────────────────────────────────────────

    def _quit(self, *args):
        for overlay in self.overlays:
            overlay.destroy()
        self._save_config()
        Gtk.main_quit()

    def run(self):
        signal.signal(signal.SIGINT, lambda *a: self._quit())
        signal.signal(signal.SIGTERM, lambda *a: self._quit())
        # Periodically check for signals
        GLib.timeout_add(500, lambda: True)
        print(f"[Nightshade] Running — filter {'enabled' if self.config['enabled'] else 'disabled'}")
        print(f"[Nightshade] Preset: {self.config['preset']}, Intensity: {self.config['intensity']}%")
        Gtk.main()


if __name__ == "__main__":
    app = NightshadeApp()
    app.run()

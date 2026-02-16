<p align="center">
  <img src="assets/nightshade-banner.png" alt="Nightshade Banner" width="700">
</p>

<h1 align="center">NIGHTSHADE</h1>

<p align="center">
  <strong>Software blue light filter for Raspberry Pi 5</strong><br>
  <em>Because the V3D driver won't let you adjust gamma — so we built our own.</em>
</p>

<p align="center">
  <a href="#installation">Install</a> •
  <a href="#usage">Usage</a> •
  <a href="#configuration">Config</a> •
  <a href="#how-it-works">How It Works</a> •
  <a href="#troubleshooting">Troubleshooting</a>
</p>

---

## The Problem

The Raspberry Pi 5 uses a Broadcom V3D GPU driver that **does not support hardware gamma LUT manipulation** through `xrandr`. This means:

- `xrandr --gamma` silently fails (accepts values but doesn't apply them)
- **Redshift** doesn't work
- **Gammastep** doesn't work
- XFCE has no built-in night light
- Your eyes burn at 2 AM

## The Solution

Nightshade bypasses the GPU entirely. Instead of manipulating gamma tables, it draws **transparent, click-through overlay windows** across all your displays with an amber/orange tint. It lives in your system tray and stays out of your way.

## Features

- **System tray integration** — left-click to toggle, right-click for full menu
- **6 color temperature presets** — from 6500K (daylight) down to 1500K (deep amber)
- **Adjustable intensity** — 5% to 100% via slider or tray menu
- **Multi-monitor support** — automatically detects and covers all connected displays
- **Fully click-through** — overlays never interfere with mouse or keyboard input
- **Settings GUI** — dark-themed control panel accessible from the tray
- **Persistent config** — remembers your settings between sessions
- **Autostart on login** — set it and forget it
- **Lightweight** — pure Python/GTK, no heavy dependencies

## Screenshots

<p align="center">
  <em>Screenshots coming soon — contributions welcome!</em>
</p>

<!--
<p align="center">
  <img src="assets/tray-menu.png" alt="Tray Menu" width="300">
  <img src="assets/settings-window.png" alt="Settings Window" width="300">
</p>
-->

## Requirements

- Raspberry Pi 5 (or any Linux system where `xrandr --gamma` doesn't work)
- X11 session (Wayland is not supported)
- Python 3
- GTK 3
- XFCE, LXDE, or any desktop with a system tray

## Installation

```bash
git clone https://github.com/lpzDnl/nightshade.git
cd nightshade
chmod +x install.sh
bash install.sh
```

The installer will:
1. Install Python/GTK dependencies via `apt`
2. Copy `nightshade` to `/usr/local/bin/`
3. Add a `.desktop` entry to your applications menu
4. Enable autostart on login
5. Create the config directory at `~/.config/nightshade/`

### Manual Install

If you prefer to do it yourself:

```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1
sudo cp nightshade.py /usr/local/bin/nightshade
sudo chmod +x /usr/local/bin/nightshade
mkdir -p ~/.config/nightshade
```

## Usage

### Launch

```bash
nightshade
```

An icon will appear in your system tray panel.

### Controls

| Action | Effect |
|---|---|
| **Left-click** tray icon | Toggle filter on/off |
| **Right-click** tray icon | Open menu with presets, intensity, settings |
| **Settings window** | Full GUI with slider and dropdown |

### Tray Icon States

- **Amber circle** — filter is active
- **Gray circle** — filter is disabled

## Configuration

Config is stored at `~/.config/nightshade/config.json`:

```json
{
  "enabled": true,
  "intensity": 40,
  "preset": "Warm White (3500K)",
  "custom_r": 45,
  "custom_g": 20,
  "custom_b": 0
}
```

### Available Presets

| Preset | Temperature | Feel |
|---|---|---|
| Sunlight | 6500K | No filter (off) |
| Halogen | 4200K | Slight warmth |
| Warm White | 3500K | Comfortable evening use |
| Candle | 2700K | Warm and relaxed |
| Ember | 2000K | Very warm, low strain |
| Deep Amber | 1500K | Maximum blue light reduction |

### Autostart

Enabled by default after installation. To manage:

```bash
# Disable autostart
rm ~/.config/autostart/nightshade.desktop

# Re-enable autostart
cp ~/.local/share/applications/nightshade.desktop ~/.config/autostart/
```

## How It Works

Since the Pi 5's V3D driver ignores gamma LUT changes via `xrandr`, Nightshade takes a different approach:

1. **Detects all connected monitors** using GDK's display/monitor API
2. **Creates a transparent GTK window** for each monitor, sized and positioned to cover the full screen
3. **Sets the window as click-through** using `input_shape_combine_region` with an empty region — all mouse and keyboard events pass straight through
4. **Draws a colored overlay** using Cairo with configurable RGB values and alpha transparency
5. **Keeps windows above all others** so the tint is always visible
6. **Manages everything from the system tray** via AppIndicator3 or the legacy GtkStatusIcon

The overlay alpha is capped at 0.45 (even at 100% intensity) to keep the screen usable.

## Troubleshooting

### Tray icon doesn't appear

Make sure your XFCE panel has a **Status Tray Plugin** or **Notification Area** widget:

1. Right-click your panel → **Panel** → **Panel Preferences**
2. Go to the **Items** tab
3. Add **Status Tray Plugin** if it's not listed

### Overlay doesn't cover full screen

This can happen if your display scaling is set to something other than 100%. Nightshade reads the monitor geometry from GDK, which should account for scaling, but if you see gaps, file an issue.

### Filter looks too orange / not orange enough

Adjust intensity from the tray menu or settings window. You can also edit `~/.config/nightshade/config.json` directly to fine-tune the RGB values using the `custom_r`, `custom_g`, `custom_b` fields.

### Want to use it on a non-Pi system

Nightshade works on any Linux system running X11 where gamma manipulation doesn't work. It's not Pi-specific — the overlay approach is universal.

## Uninstall

```bash
sudo rm /usr/local/bin/nightshade
rm ~/.local/share/applications/nightshade.desktop
rm ~/.config/autostart/nightshade.desktop
rm -rf ~/.config/nightshade
```

## License

MIT

## Contributing

Issues and pull requests welcome. If you get it working on a setup not listed here, let us know.

---

<p align="center">
  <sub>Built because Broadcom said no to gamma. We said yes to sleep.</sub>
</p>

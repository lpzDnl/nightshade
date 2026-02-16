#!/bin/bash
# Nightshade Installer

echo "╔══════════════════════════════════════════╗"
echo "║  NIGHTSHADE — Blue Light Filter Install  ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# Install dependencies
echo "[*] Installing dependencies..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1 2>/dev/null

# If ayatana isn't available, try the older appindicator
if ! python3 -c "import gi; gi.require_version('AyatanaAppIndicator3', '0.1')" 2>/dev/null; then
    echo "[*] Trying legacy AppIndicator3..."
    sudo apt-get install -y -qq gir1.2-appindicator3-0.1 2>/dev/null
fi

# Install the main script
echo "[*] Installing nightshade to /usr/local/bin..."
sudo cp nightshade.py /usr/local/bin/nightshade
sudo chmod +x /usr/local/bin/nightshade

# Install desktop entry for app menu
echo "[*] Adding to applications menu..."
cp nightshade.desktop ~/.local/share/applications/ 2>/dev/null
mkdir -p ~/.local/share/applications
cp nightshade.desktop ~/.local/share/applications/

# Install autostart entry
echo "[*] Setting up autostart..."
mkdir -p ~/.config/autostart
cp nightshade.desktop ~/.config/autostart/

# Create config directory
mkdir -p ~/.config/nightshade

echo ""
echo "[✓] Nightshade installed successfully!"
echo ""
echo "  Launch:     nightshade"
echo "  Autostart:  Enabled (runs on login)"
echo "  Config:     ~/.config/nightshade/config.json"
echo ""
echo "  The tray icon will appear in your panel."
echo "  Left-click to toggle, right-click for options."
echo ""

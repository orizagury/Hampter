#!/bin/bash
# install_deps.sh - Install system dependencies for Hampter Link on Ubuntu/Debian

set -e

echo "[*] Updating apt repositories..."
sudo apt update

echo "[*] Installing Python, GStreamer, Qt6, and Network tools..."
sudo apt install -y \
    python3-pip python3-venv \
    libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev \
    gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly \
    gstreamer1.0-tools gstreamer1.0-alsa \
    iw hostapd \
    build-essential libssl-dev libffi-dev \
    libgirepository1.0-dev libcairo2-dev pkg-config python3-dev

echo "[*] Installing PyQt6 via apt (required for ARM64)..."
sudo apt install -y python3-pyqt6 || {
    echo "[!] python3-pyqt6 not available, trying alternative..."
    sudo apt install -y python3-pyqt5
    echo "[!] Installed PyQt5 instead - you may need to adjust imports"
}

echo "[*] Creating virtual environment with system packages..."
if [ ! -d "venv" ]; then
    # Use --system-site-packages to access apt-installed PyQt6
    python3 -m venv --system-site-packages venv
    echo "[+] venv created with system packages."
else
    echo "[.] venv already exists."
fi

echo "[*] Installing Python requirements..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "[SUCCESS] Dependencies installed. You are ready to Link."
echo ""
echo "To activate the environment: source venv/bin/activate"
echo "To run the application:      python main.py"

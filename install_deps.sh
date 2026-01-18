#!/bin/bash
# install_deps.sh - Install system dependencies for Hampter Link on Ubuntu/Debian

set -e

echo "[*] Updating apt repositories..."
sudo apt update

echo "[*] Installing Python, GStreamer, Qt, and Network tools..."
sudo apt install -y \
    python3-pip python3-venv \
    libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev \
    gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly \
    gstreamer1.0-tools gstreamer1.0-alsa \
    libqt5gui5 libqt5core5a qt6-base-dev \
    iw wireless-tools hostapd \
    build-essential libssl-dev libffi-dev \
    libgirepository1.0-dev libcairo2-dev pkg-config python3-dev

echo "[*] Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "[+] venv created."
else
    echo "[.] venv already exists."
fi

echo "[*] Installing Python requirements..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "[SUCCESS] Dependencies installed. You are ready to Link."

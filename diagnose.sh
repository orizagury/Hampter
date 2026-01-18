#!/bin/bash
# diagnose.sh - Hampter Link Connectivity Checker
# Usage: sudo ./diagnose.sh <interface> <target_ip>

IFACE=$1
TARGET=$2

if [ -z "$IFACE" ] || [ -z "$TARGET" ]; then
    echo "Usage: sudo ./diagnose.sh <interface> <target_ip>"
    exit 1
fi

echo "=== DIAGNOSTICS FOR $IFACE ==="
echo "[1] Interface Status:"
ip addr show "$IFACE" | grep -E "inet |state"

echo -e "\n[2] Wireless Mode (Should be IBSS):"
iw dev "$IFACE" info | grep type

echo -e "\n[3] Ad-Hoc Link Status (Check SSID and Freq):"
iw dev "$IFACE" link

echo -e "\n[4] Firewall Rules (Looking for DROP):"
iptables -L INPUT -n | head -n 5

echo -e "\n[5] Pinging Target ($TARGET)..."
ping -c 4 -I "$IFACE" "$TARGET"

echo "=============================="

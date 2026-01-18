#!/bin/bash
# setup_network.sh - Ad-Hoc Network Setup Helper
# Usage: sudo ./setup_network.sh <interface> <ip_address> <channel>

IFACE=$1
IP_ADDR=$2
CHANNEL=${3:-1} # Default to channel 1

if [ -z "$IFACE" ] || [ -z "$IP_ADDR" ]; then
    echo "Usage: sudo ./setup_network.sh <interface> <ip_address> [channel]"
    exit 1
fi

echo "[*] Ensuring clean state for $IFACE..."

# Instead of killing NetworkManager (which kills SSH), tell it to ignore THIS device
if command -v nmcli &> /dev/null; then
    echo "[*] Setting $IFACE as unmanaged in NetworkManager..."
    nmcli device set "$IFACE" managed no
else
    echo "[!] nmcli not found, skipping specific unmanagement. Warning: wpa_supplicant might interfere."
fi

# Stop wpa_supplicant JUST for this interface if possible, or kill if it's strictly interfering.
# But killing wpa_supplicant global might kill SSH too if it's wifi-based.
# We will rely on 'ip link set down' clearing state mostly.

echo "[*] Bringing down $IFACE..."
ip link set "$IFACE" down
ip addr flush dev "$IFACE"

echo "[*] Setting ad-hoc (IBSS) mode on channel $CHANNEL..."
# Try to set type ibss directly
if ! iw dev "$IFACE" set type ibss; then
    echo "[-] Failed to set type IBSS. Attempting manual disconnect..."
    iw dev "$IFACE" disconnect 2>/dev/null
    iw dev "$IFACE" set type ibss
fi

echo "[*] Configuring static IP $IP_ADDR..."
ip addr add "$IP_ADDR/16" broadcast + dev "$IFACE"

echo "[*] Bringing up $IFACE..."
ip link set "$IFACE" up

# Join the mesh/ibss network explicitly
# Fixed frequency for 2.4GHz: 2412 + (Channel-1)*5
FREQ=$((2412 + (CHANNEL-1)*5))
echo "[*] Joining IBSS network 'hampter-net' on $FREQ MHz..."
iw dev "$IFACE" ibss join "hampter-net" $FREQ

echo "[SUCCESS] $IFACE is ready on $IP_ADDR (Ch $CHANNEL)"

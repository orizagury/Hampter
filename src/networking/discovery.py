"""
Discovery Module.
Handles UDP Beacon broadcasting and listening.
Enhanced for Robustness: Explicit Broadcast Address and Interface Binding.
"""
import asyncio
import socket
import logging
import json
import netifaces
from config import cfg

logger = logging.getLogger("Discovery")

class DiscoveryProtocol(asyncio.DatagramProtocol):
    def __init__(self, on_peer_found_callback, dashboard=None):
        self.on_peer_found = on_peer_found_callback
        self.transport = None
        self.dashboard = dashboard

    def connection_made(self, transport):
        self.transport = transport
        sock = transport.get_extra_info('socket')
        
        # Enable Broadcast
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        # Bind to specific device (Linux only) - Critical for multi-interface setups
        if cfg.interface and hasattr(socket, 'SO_BINDTODEVICE'):
            try:
                # Ensure it's bytes
                iface_bytes = cfg.interface.encode('utf-8')
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, iface_bytes)
                if self.dashboard:
                    self.dashboard.add_debug(f"Bound UDP to {cfg.interface}")
            except Exception as e:
                if self.dashboard:
                    self.dashboard.add_debug(f"Failed to bind UDP: {e}")

    def datagram_received(self, data, addr):
        try:
            if data.startswith(cfg.BEACON_MAGIC):
                payload = data[len(cfg.BEACON_MAGIC):]
                info = json.loads(payload)
                
                # Filter out ourselves (using hostname is a simple way)
                if info.get('hostname') == cfg.get_hostname():
                    return
                
                if self.dashboard:
                    self.dashboard.add_debug(f"RX Beacon from {addr[0]}")
                    
                self.on_peer_found(info, addr[0])
        except Exception:
            pass

class DiscoveryService:
    def __init__(self, on_peer_found, dashboard=None):
        self.on_peer_found = on_peer_found
        self.dashboard = dashboard
        self.transport = None
        self.protocol = None
        self.broadcasting = False

    async def start(self):
        loop = asyncio.get_running_loop()
        
        # Calculate Broadcast Address
        broadcast_addr = '<broadcast>'
        try:
            # Try to get the specific broadcast address for the subnet (e.g. 10.0.0.255)
            # This is more reliable than 255.255.255.255 in some ad-hoc scenarios
            if_addrs = netifaces.ifaddresses(cfg.interface)
            if netifaces.AF_INET in if_addrs:
                # Get the first ipv4 config
                ipv4_config = if_addrs[netifaces.AF_INET][0]
                if 'broadcast' in ipv4_config:
                    broadcast_addr = ipv4_config['broadcast']
        except Exception as e:
            if self.dashboard:
                self.dashboard.add_debug(f"Broadcast addr calc failed: {e}")

        if self.dashboard:
            self.dashboard.add_debug(f"UDP Target: {broadcast_addr}")

        # Bind to 0.0.0.0 to receive, but we rely on SO_BINDTODEVICE in protocol
        self.transport, self.protocol = await loop.create_datagram_endpoint(
            lambda: DiscoveryProtocol(self.on_peer_found, self.dashboard),
            local_addr=('0.0.0.0', cfg.DISCOVERY_PORT),
            allow_broadcast=True
        )
        
        # Start broadcast loop
        self.broadcasting = True
        asyncio.create_task(self._broadcast_loop(broadcast_addr))

    async def _broadcast_loop(self, broadcast_addr):
        while self.broadcasting:
            if self.transport:
                msg = {
                    "hostname": cfg.get_hostname(),
                    "status": "READY"
                }
                payload = cfg.BEACON_MAGIC + json.dumps(msg).encode()
                try:
                    self.transport.sendto(payload, (broadcast_addr, cfg.DISCOVERY_PORT))
                    # if self.dashboard: self.dashboard.add_debug("TX Beacon")
                except Exception as e:
                    if self.dashboard:
                        self.dashboard.add_debug(f"TX Fail: {e}")
            
            await asyncio.sleep(cfg.BEACON_INTERVAL)

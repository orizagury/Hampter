"""
Hampter Link Orchestrator.
Combines Networking, Protocol, and UI.
Now implements a custom Raw Input Loop for artifact-free TUI.
"""
import asyncio
import logging
import sys
import tty
import termios
import select

# Core Modules
from config import cfg
from src.networking.interface_mgr import InterfaceManager
from src.networking.discovery import DiscoveryService
from src.protocol.certificates import CertificateManager
from src.protocol.quic_server import HampterProtocol, build_quic_config
from src.protocol.quic_client import QuicClient
from src.ui.dashboard import Dashboard

from aioquic.asyncio import serve

# Logging: Write to file for debugging
logging.basicConfig(
    filename='hampter_debug.log', 
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("Main")

class HamperLinkApp:
    def __init__(self):
        self.dashboard = Dashboard()
        self.loop = None
        self.quic_client = None
        self.peer_info = None
        self.running = True
        self.input_buffer = ""
        self.connecting = False  # Prevent duplicate connections
        
    def start(self):
        # 1. Interface Selection (Standard Print Mode before TUI)
        try:
            ifaces = InterfaceManager.scan_interfaces()
            print("\n[+] Available Interfaces:")
            for idx, i in enumerate(ifaces):
                print(f" {idx}. {i['name']} ({i['driver']}) {'[AX210]' if i['is_ax210'] else ''}")
            
            sel = input("\nSelect Interface ID (default 0): ") or "0"
            if int(sel) < len(ifaces):
                selected_iface = ifaces[int(sel)]
            else:
                selected_iface = ifaces[0]
            
            # 2. Network Config
            ip = input(f"Enter IP for {selected_iface['name']} (e.g. 10.0.0.1): ")
            channel = input("Enter Channel (default 1): ") or "1"
            
            print(f"[+] Configuring {selected_iface['name']}...")
            if not InterfaceManager.configure_adhoc(selected_iface['name'], ip, int(channel)):
                print("[-] Configuration Failed. Check sudo?")
                return

            cfg.interface = selected_iface['name']
            cfg.ip_address = ip
            self.dashboard.update_info(cfg.interface, cfg.ip_address)

            # 3. Certs
            CertificateManager.ensure_certs()
            
            # 4. Asyncio Loop Start
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_until_complete(self.async_main())
            
        except KeyboardInterrupt:
            pass
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Fatal Error: {e}")
        finally:
            print("Shutting down...")

    async def async_main(self):
        logger.info("Starting async_main")
        self.dashboard.add_debug("Init: Starting servers...")
        
        # Start QUIC Server
        quic_config = build_quic_config(cfg.CERT_PATH, cfg.KEY_PATH)
        
        def on_server_msg(data, peer):
            self.dashboard.add_log("PEER", data)
            logger.info(f"Server received: {data} from {peer}")
        
        HampterProtocol._on_message_callback = on_server_msg

        try:
            server = await serve(
                "0.0.0.0", cfg.DEFAULT_PORT,
                configuration=quic_config,
                create_protocol=HampterProtocol,
            )
            self.dashboard.add_debug(f"QUIC Server on :{cfg.DEFAULT_PORT}")
            logger.info(f"QUIC Server started on port {cfg.DEFAULT_PORT}")
        except Exception as e:
            self.dashboard.add_debug(f"Server Error: {e}")
            logger.error(f"Server failed: {e}")
            return
        
        # Start Discovery
        discovery = DiscoveryService(self.on_peer_found, dashboard=self.dashboard)
        await discovery.start()
        
        # Start TUI Loop
        await self.tui_loop()

    def on_peer_found(self, info, ip):
        """Called from sync context when a peer is discovered."""
        logger.info(f"Peer found callback: {ip}")
        
        # Prevent duplicate connection attempts
        if self.connecting:
            logger.debug("Already connecting, skipping")
            return
        if self.peer_info and self.peer_info.get('ip') == ip:
            return
            
        self.peer_info = info.copy()
        self.peer_info['ip'] = ip
        self.dashboard.update_peer("FOUND", ip, name=info.get('hostname'))
        self.dashboard.add_log("SYSTEM", f"Peer found: {ip}")
        
        # Schedule QUIC connection safely
        self.connecting = True
        self.dashboard.add_debug(f"Scheduling QUIC to {ip}")
        logger.info(f"Scheduling connect_quic to {ip}")
        
        # Use ensure_future which works from sync callbacks in running loop
        future = asyncio.ensure_future(self.connect_quic(ip))
        future.add_done_callback(self._on_connect_done)

    def _on_connect_done(self, future):
        """Handle completion/failure of connect task."""
        self.connecting = False
        try:
            future.result()  # This will raise if there was an exception
        except Exception as e:
            self.dashboard.add_debug(f"Connect failed: {e}")
            logger.exception(f"Connect task failed: {e}")

    async def connect_quic(self, ip):
        logger.info(f"connect_quic started for {ip}")
        self.dashboard.add_debug(f"QUIC: Connecting {ip}:{cfg.DEFAULT_PORT}")
        
        client = QuicClient(cfg.CERT_PATH, dashboard=self.dashboard)
        self.quic_client = client
        
        def on_client_msg(data, _):
            self.dashboard.add_log("PEER", data)
            logger.info(f"Client received: {data}")
        
        def on_connected():
            self.dashboard.update_peer("CONNECTED", ip, name=self.peer_info.get('hostname'))
            self.dashboard.add_log("SYSTEM", "QUIC Link Established!")
            logger.info("QUIC connected!")
            
        self.dashboard.add_log("SYSTEM", f"Connecting to {ip}...")
        
        # This blocks until connection closes
        await client.connect_to(ip, cfg.DEFAULT_PORT, on_client_msg, on_connected)

    async def handle_input(self, msg):
        self.dashboard.add_log("ME", msg)
        if self.quic_client and self.quic_client.connected:
            self.quic_client.send_message(msg)
        else:
            self.dashboard.add_log("SYSTEM", "Not connected to peer.")

    async def tui_loop(self):
        """Main Loop that handles UI updates and Raw Input."""
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        
        try:
            tty.setcbreak(fd)
            
            with self.dashboard.get_live() as live:
                while self.running:
                    live.update(self.dashboard.generate_layout())
                    
                    if select.select([sys.stdin], [], [], 0)[0]:
                        ch = sys.stdin.read(1)
                        if ch == '\x03':  # Ctrl+C
                            self.running = False
                            break
                        elif ch == '\n' or ch == '\r':
                            if self.input_buffer:
                                await self.handle_input(self.input_buffer)
                                self.input_buffer = ""
                        elif ch == '\x7f':  # Backspace
                            self.input_buffer = self.input_buffer[:-1]
                        elif ch.isprintable():
                            self.input_buffer += ch
                            
                        self.dashboard.update_input(self.input_buffer)
                        
                    await asyncio.sleep(0.01)
                    
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

if __name__ == "__main__":
    app = HamperLinkApp()
    app.start()

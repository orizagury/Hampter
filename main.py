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
import traceback
import ipaddress
from aioquic.asyncio import serve

# Core Modules
from config import cfg
from src.networking.interface_mgr import InterfaceManager
from src.networking.discovery import DiscoveryService
from src.protocol.certificates import CertificateManager
from src.protocol.quic_server import HampterProtocol, build_quic_config
from src.protocol.quic_client import QuicClient
from src.ui.dashboard import Dashboard

# Logging: Redirect all logs to a file to keep TUI clean
logging.basicConfig(
    filename='hampter_debug.log',
    level=logging.DEBUG,
    format='%(asctime)s %(name)s %(levelname)s: %(message)s'
)
logger = logging.getLogger("Main")

class HamperLinkApp:
    def __init__(self):
        self.dashboard = Dashboard()
        self.loop = asyncio.new_event_loop()
        self.quic_client = None
        self.active_link = None # Client or Server protocol object
        self.peer_info = None
        self.running = True
        self.input_buffer = ""
        
    def start(self):
        # 1. Interface Selection
        try:
            ifaces = InterfaceManager.scan_interfaces()
            print("\n[+] Available Interfaces:")
            for idx, i in enumerate(ifaces):
                print(f" {idx}. {i['name']} ({i['driver']}) {'[AX210]' if i['is_ax210'] else ''}")
            
            sel = input("\nSelect Interface ID (default 0): ") or "0"
            selected_iface = ifaces[int(sel)]
            
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
            
            # 4. Asyncio Loop
            asyncio.set_event_loop(self.loop)
            self.loop.run_until_complete(self.async_main())
            
        except KeyboardInterrupt:
            pass
        except Exception as e:
            traceback.print_exc()
            print(f"Fatal Error: {e}")
        finally:
            self.running = False
            print("Shutting down...")

    async def async_main(self):
        self.dashboard.add_debug("SYSTEM: Starting Core...")
        
        # Start QUIC Server
        quic_config = build_quic_config(cfg.CERT_PATH, cfg.KEY_PATH)
        
        def on_server_msg(data, peer):
            try:
                ip = peer[0] if (peer and len(peer) > 0) else "Peer"
                self.dashboard.add_log(f"PEER({ip})", data)
                self.dashboard.add_debug(f"SRV: RX Data from {ip}")
            except Exception as e:
                logger.error(f"on_server_msg Error: {e}")
        
        def on_server_connect(peer, protocol):
            try:
                ip = peer[0] if (peer and len(peer) > 0) else "Unknown"
                self.dashboard.add_debug(f"SRV: New Conn from {ip}")
                self.dashboard.update_peer("CONNECTED", ip)
                self.active_link = protocol # Adopt server side for sending
            except Exception as e:
                logger.error(f"on_server_connect Error: {e}")
        
        # Inject callbacks into Protocol class (Hack for aioquic architecture)
        HampterProtocol._on_message_callback = on_server_msg
        HampterProtocol._on_connect_callback = on_server_connect

        try:
            server = await serve(
                "0.0.0.0", cfg.DEFAULT_PORT,
                configuration=quic_config,
                create_protocol=HampterProtocol,
            )
            self.dashboard.add_debug(f"SRV: Listening on {cfg.DEFAULT_PORT}")
        except Exception as e:
            self.dashboard.add_debug(f"SRV Error: {e}")

        # Start Discovery
        discovery = DiscoveryService(self.on_peer_found, dashboard=self.dashboard)
        await discovery.start()
        
        # Start TUI Loop
        await self.tui_loop()

    def on_peer_found(self, info, ip):
        # Tie-breaking rule: Only connect if my IP is "smaller"
        # This prevents both nodes from calling each other and fighting.
        try:
            my_val = int(ipaddress.ip_address(cfg.ip_address))
            peer_val = int(ipaddress.ip_address(ip))
            if my_val > peer_val:
                return
        except:
            if cfg.ip_address > ip: return

        # Prevent connection storm
        if self.quic_client:
            if self.quic_client.connected or getattr(self.quic_client, 'connecting', False):
                if getattr(self.quic_client, 'target_ip', None) == ip:
                    return 
            
        self.peer_info = info
        self.peer_info['ip'] = ip
        self.dashboard.update_peer("FOUND", ip, name=info.get('hostname'))
        self.dashboard.add_debug(f"DISC: Peer {info.get('hostname')} at {ip}")
        
        # Initiate QUIC Connection
        asyncio.create_task(self.connect_quic(ip))

    async def connect_quic(self, ip):
        self.dashboard.add_debug(f"CLI: Targeting {ip}")
        try:
            client = QuicClient(cfg.CERT_PATH, dashboard=self.dashboard)
            self.quic_client = client
            
            def on_client_msg(data, _):
                self.dashboard.add_log("PEER", data)
            
            def on_connected():
                try:
                    self.active_link = client.protocol # Adopt client side for sending
                    self.dashboard.update_peer("CONNECTED", ip, name=self.peer_info.get('hostname'))
                    self.dashboard.add_log("SYSTEM", f"Link to {ip} Up!")
                    self.dashboard.add_debug(f"CLI: Connected to {ip}")
                except Exception as e:
                    logger.error(f"on_connected Error: {e}")
                
            self.dashboard.add_log("SYSTEM", f"Connecting to {ip}...")
            await client.connect_to(ip, cfg.DEFAULT_PORT, on_client_msg, on_connected)
            
        except Exception as e:
            self.dashboard.add_debug(f"CLI Task Error: {e}")
            self.quic_client = None
            if self.active_link == client.protocol:
                self.active_link = None

    async def handle_input(self, msg):
        self.dashboard.add_log("ME", msg)
        
        # Determine how to send
        target = None
        if self.quic_client and self.quic_client.connected:
            target = self.quic_client
        elif self.active_link:
            target = self.active_link

        if target:
            try:
                # Both QuicClient and HampterProtocol (server) should have send_message
                target.send_message(msg)
            except Exception as e:
                self.dashboard.add_debug(f"Send Error: {e}")
                self.dashboard.add_log("SYSTEM", "Send Failed.")
        else:
            self.dashboard.add_log("SYSTEM", "No active link.")

    async def tui_loop(self):
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            with self.dashboard.get_live() as live:
                while self.running:
                    try:
                        live.update(self.dashboard.generate_layout())
                        if select.select([sys.stdin], [], [], 0)[0]:
                            ch = sys.stdin.read(1)
                            if ch == '\x03': self.running = False; break
                            elif ch in ('\n', '\r'):
                                if self.input_buffer.strip():
                                    await self.handle_input(self.input_buffer)
                                    self.input_buffer = ""
                            elif ch == '\x7f': self.input_buffer = self.input_buffer[:-1]
                            elif ch.isprintable(): self.input_buffer += ch
                            self.dashboard.update_input(self.input_buffer)
                    except Exception as e:
                        logger.error(f"TUI Loop Error: {e}")
                    await asyncio.sleep(0.01)
        except Exception as fatal_e:
            logger.error(f"TUI Fatal: {fatal_e}\n{traceback.format_exc()}")
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

if __name__ == "__main__":
    app = HamperLinkApp()
    app.start()

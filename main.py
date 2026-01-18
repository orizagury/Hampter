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
from src.hw.display import LCDDisplay

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
        self.lcd = LCDDisplay()
        self.loop = asyncio.new_event_loop()
        
        # Peer Registry: { "ip": { "type": "client|server", "protocol": protocol_obj, "name": "hostname" } }
        self.peers = {} 
        self.connecting_ips = set() 
        
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
                self.lcd.show_msg(ip, data)
            except Exception as e:
                logger.error(f"on_server_msg Error: {e}")
        
        def on_server_connect(peer, protocol):
            try:
                ip = peer[0] if (peer and len(peer) > 0) else "Unknown"
                self.dashboard.add_debug(f"SRV: New Conn from {ip}")
                
                if ip not in self.peers:
                    self.peers[ip] = {"type": "server", "protocol": protocol, "name": "Unknown"}
                    self.dashboard.update_peer("MESH", ip, count=len(self.peers))
                    self.dashboard.add_log("SYSTEM", f"Node {ip} joined mesh.")
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
        try:
            my_val = int(ipaddress.ip_address(cfg.ip_address))
            peer_val = int(ipaddress.ip_address(ip))
            if my_val > peer_val:
                return
        except:
            if cfg.ip_address > ip: return

        # Check if already connected or connecting
        if ip in self.peers or ip in self.connecting_ips:
            return
            
        self.dashboard.add_debug(f"DISC: Discovered {ip}")
        # Initiate QUIC Connection
        asyncio.create_task(self.connect_quic(ip, info))

    async def connect_quic(self, ip, info):
        self.dashboard.add_debug(f"CLI: Connecting to {ip}")
        self.connecting_ips.add(ip)
        try:
            client = QuicClient(cfg.CERT_PATH, dashboard=self.dashboard)
            
            def on_client_msg(data, _):
                # Wrapped in try as a precaution
                try:
                    self.dashboard.add_log(f"PEER({ip})", data)
                    self.lcd.show_msg(ip, data)
                except: pass
            
            def on_connected():
                try:
                    self.peers[ip] = {"type": "client", "protocol": client, "name": info.get('hostname')}
                    self.dashboard.update_peer("MESH", ip, name=info.get('hostname'), count=len(self.peers))
                    self.dashboard.add_log("SYSTEM", f"Mesh Link to {ip} Up!")
                    self.dashboard.add_debug(f"CLI: Linked with {ip}")
                except Exception as e:
                    logger.error(f"on_connected Error: {e}")
                
            self.dashboard.add_debug(f"CLI: Handshaking {ip}...")
            await client.connect_to(ip, cfg.DEFAULT_PORT, on_client_msg, on_connected)
            
        except Exception as e:
            self.dashboard.add_debug(f"CLI Fail {ip}: {e}")
        finally:
            self.connecting_ips.discard(ip)

    async def handle_input(self, msg):
        msg = msg.strip()
        if not msg: return

        # Command Parsing
        if msg.startswith("/"):
            cmd = msg[1:].lower()
            if cmd == "clear":
                self.dashboard.clear_logs()
                return
            elif cmd == "help":
                self.dashboard.add_log("SYSTEM", "Available commands: /clear, /help")
                return
            else:
                self.dashboard.add_log("SYSTEM", f"Unknown command: {msg}")
                return

        self.dashboard.add_log("ME", msg)
        
        # Broadcast to all peers
        if not self.peers:
            self.dashboard.add_log("SYSTEM", "No active links to send to.")
            return

        for ip, info in list(self.peers.items()):
            try:
                target = info['protocol']
                # Both QuicClient and HampterProtocol (server) have send_message
                target.send_message(msg)
            except Exception as e:
                self.dashboard.add_debug(f"Send Fail to {ip}: {e}")
                # Optional: Remove failed peers
                # del self.peers[ip]

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

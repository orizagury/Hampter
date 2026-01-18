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
from concurrent.futures import ThreadPoolExecutor

# Core Modules
from config import cfg
from src.networking.interface_mgr import InterfaceManager
from src.networking.discovery import DiscoveryService
from src.protocol.certificates import CertificateManager
from src.protocol.quic_server import HampterProtocol, build_quic_config
from src.protocol.quic_client import QuicClient
from src.ui.dashboard import Dashboard

from aioquic.asyncio import serve

# Logging: Disable standard logging to stdout as it breaks TUI
logging.basicConfig(level=logging.CRITICAL) 
# We could redirect logs to a file if needed for debug:
# logging.basicConfig(filename='hampter.log', level=logging.INFO)

class HamperLinkApp:
    def __init__(self):
        self.dashboard = Dashboard()
        self.loop = asyncio.new_event_loop()
        self.quic_client = None
        self.peer_info = None
        self.running = True
        self.input_buffer = ""
        
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
        # Start QUIC Server
        quic_config = build_quic_config(cfg.CERT_PATH, cfg.KEY_PATH)
        
        def on_server_msg(data, peer):
            self.dashboard.add_log(f"PEER", data)
        
        HampterProtocol._on_message_callback = on_server_msg

        server = await serve(
            "0.0.0.0", cfg.DEFAULT_PORT,
            configuration=quic_config,
            create_protocol=HampterProtocol,
        )
        
        # Start Discovery
        discovery = DiscoveryService(self.on_peer_found, dashboard=self.dashboard)
        await discovery.start()
        
        # Start TUI Loop
        await self.tui_loop()

    def on_peer_found(self, info, ip):
        if self.peer_info and self.peer_info['ip'] == ip:
            return 
            
        self.peer_info = info
        self.peer_info['ip'] = ip
        self.dashboard.update_peer("FOUND", ip, name=info.get('hostname'))
        self.dashboard.add_log("SYSTEM", f"Peer found: {ip}")
        
        # Initiate QUIC Connection
        asyncio.create_task(self.connect_quic(ip))

    async def connect_quic(self, ip):
        self.dashboard.add_debug(f"Starting QUIC to {ip}")
        try:
            client = QuicClient(cfg.CERT_PATH, dashboard=self.dashboard)
            self.quic_client = client
            
            def on_client_msg(data, _):
                self.dashboard.add_log("PEER", data)
            
            def on_connected():
                self.dashboard.update_peer("CONNECTED", ip, name=self.peer_info.get('hostname'))
                self.dashboard.add_log("SYSTEM", "QUIC Link Established!")
                
            self.dashboard.add_log("SYSTEM", f"Connecting to {ip}...")
            
            # This runs in background, the callback fires when connected
            await client.connect_to(ip, cfg.DEFAULT_PORT, on_client_msg, on_connected)
        except Exception as e:
            self.dashboard.add_debug(f"QUIC Error: {e}")

    async def handle_input(self, msg):
        self.dashboard.add_log("ME", msg)
        if self.quic_client and self.quic_client.connected:
            self.quic_client.send_message(msg)
        else:
            self.dashboard.add_log("SYSTEM", "Not connected to peer.")

    async def tui_loop(self):
        """
        Main Loop that handles UI updates and Raw Input.
        """
        # Save terminal settings
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        
        try:
            tty.setcbreak(fd) # Enable non-blocking/raw input
            
            with self.dashboard.get_live() as live:
                while self.running:
                    # 1. Update UI
                    live.update(self.dashboard.generate_layout())
                    
                    # 2. Check Input (Non-blocking)
                    if select.select([sys.stdin], [], [], 0)[0]:
                        ch = sys.stdin.read(1)
                        if ch == '\x03': # Ctrl+C
                            self.running = False
                            break
                        elif ch == '\n' or ch == '\r': # Enter
                            if self.input_buffer:
                                await self.handle_input(self.input_buffer)
                                self.input_buffer = ""
                        elif ch == '\x7f': # Backspace
                            self.input_buffer = self.input_buffer[:-1]
                        else:
                            # Simple filter for printable chars
                            if ch.isprintable():
                                self.input_buffer += ch
                                
                        self.dashboard.update_input(self.input_buffer)
                        
                    # 3. Async Sleep to let other tasks run
                    await asyncio.sleep(0.01)
                    
        finally:
            # Restore terminal settings
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

if __name__ == "__main__":
    app = HamperLinkApp()
    app.start()

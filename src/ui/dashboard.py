"""
Cyber Dashboard for Hampter Link.
Uses Rich for layout. Now renders input buffer manually to avoid cursor artifacts.
"""
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.live import Live
from rich.console import Console
from datetime import datetime
from collections import deque
from config import cfg

class Dashboard:
    def __init__(self):
        self.console = Console()
        self.layout = Layout()
        self.messages = deque(maxlen=20)
        self.debug_log = deque(maxlen=10) # New Debug Log
        self.peer_data = {"status": "SEARCHING", "ip": "N/A", "ping": "N/A", "name": "N/A"}
        self.my_info = {"iface": "Unknown", "ip": "Unknown"}
        self.input_buffer = ""
        
        # Initial Setup
        self.layout.split(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=3)
        )
        self.layout["main"].split_row(
            Layout(name="status", ratio=2),
            Layout(name="log", ratio=3)
        )
        # Split log into Data and Debug
        self.layout["log"].split_column(
            Layout(name="data_log", ratio=3),
            Layout(name="debug_log", ratio=1)
        )

    def update_peer(self, status, ip="N/A", ping="N/A", name="N/A"):
        self.peer_data = {"status": status, "ip": ip, "ping": ping, "name": name}

    def update_info(self, iface, ip):
        self.my_info = {"iface": iface, "ip": ip}

    def add_log(self, sender, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.messages.append(f"[{timestamp}] [bold]{sender}[/bold]: {message}")

    def add_debug(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.debug_log.append(f"[{timestamp}] {message}")

    def update_input(self, text):
        self.input_buffer = text

    def generate_layout(self):
        # Header
        self.layout["header"].update(
            Panel(Text("HAMPTER LINK PROTOTYPE v1.6 (DEBUG MODE)", justify="center", style="bold magenta"), style="on black")
        )
        
        # Status Panel
        status_table = Table.grid(padding=1)
        status_table.add_column(style="bold cyan")
        status_table.add_column()
        
        status_color = "green" if self.peer_data["status"] == "CONNECTED" else "red blink"
        
        status_table.add_row("STATUS", Text(self.peer_data["status"], style=status_color))
        status_table.add_row("PEER IP", self.peer_data["ip"])
        status_table.add_row("PEER ID", self.peer_data["name"])
        status_table.add_row("PING", str(self.peer_data["ping"]))
        status_table.add_row(" ", " ")
        status_table.add_row("MY IFACE", self.my_info["iface"])
        status_table.add_row("MY IP", self.my_info["ip"])
        
        self.layout["status"].update(
            Panel(status_table, title="SYSTEM STATUS", border_style="cyan")
        )
        
        # Data Log Panel
        log_text = "\n".join(self.messages)
        self.layout["data_log"].update(
            Panel(log_text, title="DATA LINK LOG", border_style="green", padding=(0, 1))
        )

        # Debug Log Panel
        debug_text = "\n".join(self.debug_log)
        self.layout["debug_log"].update(
            Panel(debug_text, title="DEBUG TELEMETRY", border_style="yellow", style="dim")
        )
        
        # Footer (Input)
        cursor = "█" 
        self.layout["footer"].update(
             Panel(Text(f"> {self.input_buffer}{cursor}", style="bold white"), title="COMMAND INPUT", border_style="dim")
        )
        
        return self.layout

    def get_live(self):
        return Live(self.generate_layout(), refresh_per_second=10, screen=True)

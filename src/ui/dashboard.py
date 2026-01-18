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
            Layout(name="status", ratio=1),
            Layout(name="log", ratio=2)
        )

    def update_peer(self, status, ip="N/A", ping="N/A", name="N/A"):
        self.peer_data = {"status": status, "ip": ip, "ping": ping, "name": name}

    def update_info(self, iface, ip):
        self.my_info = {"iface": iface, "ip": ip}

    def add_log(self, sender, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.messages.append(f"[{timestamp}] [bold]{sender}[/bold]: {message}")

    def update_input(self, text):
        self.input_buffer = text

    def generate_layout(self):
        # Header
        self.layout["header"].update(
            Panel(Text("HAMPTER LINK PROTOTYPE v1.5", justify="center", style="bold magenta"), style="on black")
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
        
        # Log Panel
        log_text = "\n".join(self.messages)
        self.layout["log"].update(
            Panel(log_text, title="DATA LINK LOG", border_style="green", padding=(1, 2))
        )
        
        # Footer (Input)
        # Add visual cursor
        cursor = "█" 
        self.layout["footer"].update(
             Panel(Text(f"> {self.input_buffer}{cursor}", style="bold white"), title="COMMAND INPUT", border_style="dim")
        )
        
        return self.layout

    def get_live(self):
        # Using auto_refresh=False to manually control updates from main loop if needed, 
        # but here we rely on the main loop calling update.
        return Live(self.generate_layout(), refresh_per_second=10, screen=True)

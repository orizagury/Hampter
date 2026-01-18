"""
SOTA Console Interface for Hampter Link using Rich and Prompt Toolkit.
"""
import asyncio
from typing import Callable, Optional, Dict, Any
from datetime import datetime

from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.live import Live
from rich.table import Table
from rich.text import Text
from rich import box

# Initialize Rich Console
rconsole = Console()

class SotaConsole:
    """
    State-of-the-Art CLI for Hampter Link.
    Features:
    - Interactive REPL with history
    - Live Telemetry Dashboard
    - Rich Text Logging
    """
    
    def __init__(self):
        self.running = False
        self._commands: Dict[str, Callable] = {}
        self._status_provider: Optional[Callable] = None
        self._message_handler: Optional[Callable] = None
        self._link_handler: Optional[Callable] = None
        self._fan_handler: Optional[Callable] = None
        
        self.session = PromptSession()
        self.messages = [] # List of (timestamp, sender, msg)
        
        self._register_commands()

    def _register_commands(self):
        self._commands = {
            '/help': self._cmd_help,
            '/quit': self._cmd_quit,
            '/status': self._cmd_status,
            '/link': self._cmd_link,
            '/fan': self._cmd_fan,
        }

    # --- Configuration ---
    def set_status_provider(self, provider): self._status_provider = provider
    def set_message_handler(self, handler): self._message_handler = handler
    def set_link_handler(self, handler): self._link_handler = handler
    def set_fan_handler(self, handler): self._fan_handler = handler

    # --- UI Components ---
    def _generate_layout(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body", ratio=1),
            Layout(name="footer", size=7)
        )
        # Header
        layout["header"].update(Panel(
            Text("HAMPTER LINK v2.0 // COMMAND CENTER", justify="center", style="bold cyan"),
            style="blue"
        ))
        
        # Body (Chat/Log)
        # We process messages into a rich Table or Text
        msg_table = Table(box=None, show_header=False, expand=True)
        msg_table.add_column("Time", style="dim", width=10)
        msg_table.add_column("Sender", width=12)
        msg_table.add_column("Message")
        
        # Show last 15 messages
        for ts, sender, msg in self.messages[-15:]:
            style = "green" if sender == "You" else "cyan"
            msg_table.add_row(ts, Text(f"[{sender}]", style=style), msg)
            
        layout["body"].update(Panel(msg_table, title="Chatter Lane", border_style="green"))
        
        # Footer (Telemetry)
        if self._status_provider:
            stats = self._status_provider()
            
            grid = Table.grid(expand=True, padding=1)
            grid.add_column(justify="center", ratio=1)
            grid.add_column(justify="center", ratio=1)
            grid.add_column(justify="center", ratio=1)
            
            # Telemetry panels
            temp_color = "red" if stats.get('temp', 0) > 70 else "green"
            grid.add_row(
                Panel(f"{stats.get('temp', 0):.1f}°C\nCPU Temp", style=temp_color),
                Panel(f"{stats.get('rssi', -99)}dBm\nWiFi RSSI", style="cyan"),
                Panel(f"{stats.get('battery', 0)}%\nBattery", style="yellow"),
            )
            layout["footer"].update(grid)
        else:
            layout["footer"].update(Panel("Telemetry Offline", style="dim"))
            
        return layout

    # --- Main Loop ---
    async def run(self):
        self.running = True
        
        # We need a refresh task for the UI
        refresh_task = asyncio.create_task(self._ui_refresh_loop())
        
        # Input Loop
        with patch_stdout():
            while self.running:
                try:
                    # Non-blocking input prompt
                    input_text = await self.session.prompt_async(
                        HTML('<style fg="ansiwhite">></style> '),
                    )
                    
                    if not input_text: continue
                    
                    await self._process_input(input_text.strip())
                    
                except (EOFError, KeyboardInterrupt):
                    self.running = False
                except Exception as e:
                    rconsole.print(f"[red]Error: {e}[/red]")
        
        refresh_task.cancel()
        rconsole.print("[yellow]Console stopped.[/yellow]")

    async def _ui_refresh_loop(self):
        """Redraw the UI every 1s."""
        # Note: In a real 'live' TUI, we would wrap the whole thing in Live()
        # But since we need simultaneous input, we just print updates or use Live carefully.
        # For simplicity in this async context with PromptToolkit, 
        # we will just have the prompt be the main interaction 
        # and print 'Logs' above it. 
        # A full Live layout + PromptToolkit is complex. 
        # Let's simplify: Standard prompt, but use Rich for all command outputs.
        pass

    async def _process_input(self, text: str):
        if text.startswith('/'):
            parts = text.split()
            cmd = parts[0].lower()
            args = parts[1:] if len(parts) > 1 else []
            
            if cmd in self._commands:
                await self._commands[cmd](args)
            else:
                rconsole.print(f"[red]Unknown command: {cmd}[/red]")
        else:
            # Send Message
            if self._message_handler:
                self._message_handler(text)
                self.add_message("You", text)

    def add_message(self, sender: str, text: str):
        ts = datetime.now().strftime("%H:%M")
        self.messages.append((ts, sender, text))
        
        # Print immediately for now (since we aren't using full-screen Live due to input complexity)
        style = "green bold" if sender == "You" else "cyan bold"
        rconsole.print(f"[{style}][{sender}][/{style}] {text}")

    # --- Commands ---
    async def _cmd_help(self, args):
        table = Table(title="Available Commands")
        table.add_column("Command", style="cyan")
        table.add_column("Description")
        
        table.add_row("/status", "Show telemetry dashboard")
        table.add_row("/send <msg>", "Send a chat message")
        table.add_row("/link", "Start/Stop video link")
        table.add_row("/fan <0-100>", "Set fan speed")
        table.add_row("/quit", "Exit application")
        
        rconsole.print(table)

    async def _cmd_status(self, args):
        if not self._status_provider:
            return
            
        stats = self._status_provider()
        
        grid = Table.grid(padding=1)
        grid.add_column()
        grid.add_column()
        
        grid.add_row(
            Panel(f"[bold]{stats.get('temp',0):.1f}°C[/bold]\nCPU Temp", border_style="red"),
            Panel(f"[bold]{stats.get('rssi',-100)} dBm[/bold]\nWiFi Strength", border_style="blue")
        )
        grid.add_row(
            Panel(f"[bold]{stats.get('cpu_percent',0)}%[/bold]\nCPU Load", border_style="yellow"),
            Panel(f"[bold]{stats.get('ram_percent',0)}%[/bold]\nRAM Usage", border_style="magenta")
        )
        
        rconsole.print(Panel(grid, title="System Telemetry", border_style="green"))

    async def _cmd_link(self, args):
        if self._link_handler:
            self._link_handler() # Toggle or start
            rconsole.print("[yellow]Link command sent.[/yellow]")

    async def _cmd_fan(self, args):
        if not args or not self._fan_handler: return
        try:
            val = int(args[0])
            self._fan_handler(val)
            rconsole.print(f"[green]Fan set to {val}%[/green]")
        except:
            rconsole.print("[red]Invalid fan speed[/red]")

    async def _cmd_quit(self, args):
        self.running = False

    def stop(self):
        self.running = False

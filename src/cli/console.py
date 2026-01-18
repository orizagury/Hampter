"""
SOTA Console Interface for Hampter Link.
Uses PromptToolkit for the REPL and Rich for beautiful output.
"""
import asyncio
from typing import Callable, Optional, Dict, Any
from datetime import datetime

from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.styles import Style as PtStyle

from rich.console import Console as RichConsole
from rich.panel import Panel
from rich.table import Table
from rich import box

# Global Rich Console
console = RichConsole()

class SotaConsole:
    """
    State-of-the-Art CLI for Hampter Link.
    
    Structure:
    - Top: Scrolling logs/chat (Rich)
    - Bottom: Sticky status bar (PromptToolkit)
    - Prompt: High-performance input (PromptToolkit)
    """
    
    def __init__(self):
        self.running = False
        self._commands: Dict[str, Callable] = {}
        self._status_provider: Optional[Callable] = None
        self._message_handler: Optional[Callable] = None
        
        # PromptToolkit Session with styling
        self.session = PromptSession()
        
        # Register commands
        self._commands = {
            '/help': self._cmd_help,
            '/status': self._cmd_status,
            '/quit': self._cmd_quit,
            '/fan': self._pass, # Hooks added later
            '/link': self._pass,
        }
        self._fan_handler = None
        self._link_handler = None

    def set_status_provider(self, provider): self._status_provider = provider
    def set_message_handler(self, handler): self._message_handler = handler
    def set_fan_handler(self, handler): self._fan_handler = handler
    def set_link_handler(self, handler): self._link_handler = handler

    def _pass(self, args): pass # Placeholder

    def _get_bottom_toolbar(self):
        """Generate the status bar text."""
        if not self._status_provider:
            return HTML(' <b><style bg="red" fg="white"> OFFLINE </style></b> System Initializing...')
        
        stats = self._status_provider()
        
        # Format status items
        cpu = f"{stats.get('cpu_percent', 0):.0f}%"
        temp = f"{stats.get('temp', 0):.1f}°C"
        rssi = f"{stats.get('rssi', -100)}dBm"
        batt = f"{stats.get('battery', 0):.0f}%"
        
        # Determine colors based on values
        temp_color = "red" if stats.get('temp', 0) > 75 else "green"
        rssi_color = "red" if stats.get('rssi', -100) < -80 else "green"
        
        return HTML(
            f' <b><style bg="#444444" fg="#aaaaaa"> CPU </style></b> {cpu} '
            f'<b><style bg="#444444" fg="#aaaaaa"> TEMP </style></b> <style fg="{temp_color}">{temp}</style> '
            f'<b><style bg="#444444" fg="#aaaaaa"> WIFI </style></b> <style fg="{rssi_color}">{rssi}</style> '
            f'<b><style bg="#444444" fg="#aaaaaa"> BATT </style></b> {batt} '
            f'   <style fg="#666666">Type /help for commands</style>'
        )

    async def run(self):
        self.running = True
        
        # Print Banner
        console.print(Panel(
            "[bold cyan]HAMPTER LINK v2.0[/bold cyan]\n[dim]Secure. Off-Grid. Connected.[/dim]",
            border_style="blue",
            box=box.ROUNDED
        ))
        
        # Main Loop
        with patch_stdout():
            while self.running:
                try:
                    # The prompt call handles the UI refresh automatically
                    command = await self.session.prompt_async(
                        HTML('<style fg="#00ffff"><b>[hampter]</b></style> <style fg="#bbbbbb">></style> '),
                        bottom_toolbar=self._get_bottom_toolbar,
                        refresh_interval=1.0, # Update toolbar every second
                    )
                    
                    if not command.strip(): continue
                    await self._process_command(command)
                    
                except (EOFError, KeyboardInterrupt):
                    self.running = False
                    
        console.print("[yellow]Shutting down console...[/yellow]")

    async def _process_command(self, text: str):
        text = text.strip()
        if text.startswith('/'):
            parts = text.split()
            cmd = parts[0].lower()
            args = parts[1:]
            
            # Dispatch command
            if cmd == '/quit': self.running = False
            elif cmd == '/help': await self._cmd_help(args)
            elif cmd == '/status': await self._cmd_status(args)
            elif cmd == '/fan': await self._cmd_fan_proxy(args)
            elif cmd == '/link': await self._cmd_link_proxy(args)
            else:
                console.print(f"[red]Unknown command: {cmd}[/red]")
        else:
            # Chat message
            if self._message_handler:
                self._message_handler(text)
                timestamp = datetime.now().strftime("%H:%M")
                console.print(f"[dim]{timestamp}[/dim] [bold green]Me:[/bold green] {text}")

    # --- Command Handlers ---
    
    async def _cmd_help(self, args):
        t = Table(show_header=False, box=None)
        t.add_column("Cmd", style="bold cyan")
        t.add_column("Desc")
        t.add_row("/status", "Show full system telemetry")
        t.add_row("/send", "Send message (or just type)")
        t.add_row("/fan", "Set fan speed (0-100 or auto)")
        t.add_row("/link", "Toggle video link")
        t.add_row("/quit", "Exit application")
        console.print(Panel(t, title="Available Commands", border_style="grey50"))

    async def _cmd_status(self, args):
        if not self._status_provider: return
        s = self._status_provider()
        
        # Create a dashboard grid
        grid = Table.grid(padding=2)
        grid.add_column(); grid.add_column(); grid.add_column()
        
        grid.add_row(
            f"[b]CPU[/b]: {s.get('cpu_percent')}%",
            f"[b]RAM[/b]: {s.get('ram_percent')}%",
            f"[b]SSD[/b]: {s.get('disk_percent', 'N/A')}%"
        )
        grid.add_row(
            f"[b]Temp[/b]: {s.get('temp'):.1f}°C",
            f"[b]Fan[/b]: {s.get('fan_speed', 'Auto')}",
            f"[b]Bat[/b]: {s.get('battery')}%"
        )
        console.print(Panel(grid, title="System Status", border_style="blue"))

    async def _cmd_fan_proxy(self, args):
        if self._fan_handler and args:
            try:
                val = int(args[0])
                self._fan_handler(val)
                console.print(f"[green]Fan set to {val}%[/green]")
            except:
                console.print("[red]Invalid speed[/red]")
        elif self._fan_handler and not args:
             # Auto
             self._fan_handler(-1)
             console.print("[green]Fan set to Auto[/green]")

    async def _cmd_link_proxy(self, args):
        if self._link_handler:
            self._link_handler()
            console.print("[yellow]Toggled Video Link[/yellow]")

    async def _cmd_quit(self, args):
        """Exit command."""
        self.running = False


    def stop(self):
        self.running = False

"""
Console Interface for Hampter Link.
Provides an interactive CLI for system control without GUI dependencies.
"""
import asyncio
import logging
import sys
from typing import Callable, Optional, Dict, Any

logger = logging.getLogger("Console")


class Console:
    """
    Interactive console interface for Hampter Link.
    
    Provides commands for:
    - Sending messages
    - Viewing system status
    - Controlling hardware
    - Managing connections
    """
    
    PROMPT = "\n\033[94m[hampter]\033[0m > "
    
    HELP_TEXT = """
\033[1mHampter Link Console Commands:\033[0m

  \033[92m/status\033[0m          - Show system telemetry
  \033[92m/send <msg>\033[0m      - Send a chat message
  \033[92m/link\033[0m            - Start video link
  \033[92m/stop\033[0m            - Stop video link
  \033[92m/fan <0-100>\033[0m     - Set fan speed (or 'auto')
  \033[92m/peers\033[0m           - Show connected peers
  \033[92m/help\033[0m            - Show this help
  \033[92m/quit\033[0m            - Exit application

  Or just type a message to send it directly.
"""
    
    def __init__(self):
        self.running = False
        self._commands: Dict[str, Callable] = {}
        self._status_provider: Optional[Callable] = None
        self._message_handler: Optional[Callable] = None
        self._link_start_handler: Optional[Callable] = None
        self._link_stop_handler: Optional[Callable] = None
        self._fan_handler: Optional[Callable] = None
        
        # Register built-in commands
        self._register_commands()
    
    def _register_commands(self):
        """Register all console commands."""
        self._commands = {
            '/help': self._cmd_help,
            '/status': self._cmd_status,
            '/send': self._cmd_send,
            '/link': self._cmd_link,
            '/stop': self._cmd_stop,
            '/fan': self._cmd_fan,
            '/peers': self._cmd_peers,
            '/quit': self._cmd_quit,
            '/exit': self._cmd_quit,
            '/q': self._cmd_quit,
        }
    
    def set_status_provider(self, provider: Callable[[], Dict[str, Any]]):
        """Set callback to get current system status."""
        self._status_provider = provider
    
    def set_message_handler(self, handler: Callable[[str], None]):
        """Set callback for sending messages."""
        self._message_handler = handler
    
    def set_link_handlers(self, start: Callable, stop: Callable):
        """Set callbacks for video link control."""
        self._link_start_handler = start
        self._link_stop_handler = stop
    
    def set_fan_handler(self, handler: Callable[[int], None]):
        """Set callback for fan speed control."""
        self._fan_handler = handler
    
    def print_banner(self):
        """Print the startup banner."""
        banner = """
\033[94m╔═══════════════════════════════════════════════════════════╗
║                                                               ║
║   ██╗  ██╗ █████╗ ███╗   ███╗██████╗ ████████╗███████╗██████╗   ║
║   ██║  ██║██╔══██╗████╗ ████║██╔══██╗╚══██╔══╝██╔════╝██╔══██╗  ║
║   ███████║███████║██╔████╔██║██████╔╝   ██║   █████╗  ██████╔╝  ║
║   ██╔══██║██╔══██║██║╚██╔╝██║██╔═══╝    ██║   ██╔══╝  ██╔══██╗  ║
║   ██║  ██║██║  ██║██║ ╚═╝ ██║██║        ██║   ███████╗██║  ██║  ║
║   ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝╚═╝        ╚═╝   ╚══════╝╚═╝  ╚═╝  ║
║                                                               ║
║             \033[93mL I N K   T E R M I N A L\033[94m                        ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝\033[0m
"""
        print(banner)
        print("  Type \033[92m/help\033[0m for commands, or just type to chat.\n")
    
    async def run(self):
        """Run the interactive console loop."""
        self.running = True
        self.print_banner()
        
        # Use asyncio-friendly input
        loop = asyncio.get_event_loop()
        
        while self.running:
            try:
                # Read input asynchronously
                line = await loop.run_in_executor(None, self._read_input)
                
                if line is None:
                    continue
                
                line = line.strip()
                if not line:
                    continue
                
                await self._process_input(line)
                
            except EOFError:
                self.running = False
            except KeyboardInterrupt:
                print("\n\033[93mUse /quit to exit.\033[0m")
            except Exception as e:
                logger.error(f"Console error: {e}")
    
    def _read_input(self) -> Optional[str]:
        """Read a line of input from stdin."""
        try:
            return input(self.PROMPT)
        except EOFError:
            return None
    
    async def _process_input(self, line: str):
        """Process a line of user input."""
        if line.startswith('/'):
            # Command
            parts = line.split(maxsplit=1)
            cmd = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ""
            
            if cmd in self._commands:
                await self._commands[cmd](args)
            else:
                print(f"\033[91mUnknown command: {cmd}\033[0m")
                print("Type /help for available commands.")
        else:
            # Direct message
            if self._message_handler:
                self._message_handler(line)
                print(f"\033[92m[You]\033[0m {line}")
            else:
                print("\033[91mMessage handler not configured.\033[0m")
    
    async def _cmd_help(self, args: str):
        """Show help text."""
        print(self.HELP_TEXT)
    
    async def _cmd_status(self, args: str):
        """Show system status."""
        if not self._status_provider:
            print("\033[91mStatus provider not configured.\033[0m")
            return
        
        stats = self._status_provider()
        
        print("\n\033[1m=== System Status ===\033[0m")
        print(f"  CPU Temp:     {stats.get('temp', 0):.1f}°C")
        print(f"  CPU Usage:    {stats.get('cpu_percent', 0):.1f}%")
        print(f"  RAM Usage:    {stats.get('ram_percent', 0):.1f}%")
        print(f"  Battery:      {stats.get('battery', 0):.0f}%")
        print()
        print("\033[1m=== WiFi Status ===\033[0m")
        print(f"  RSSI:         {stats.get('rssi', -100)} dBm")
        print(f"  Link Quality: {stats.get('link_quality', 0)}%")
        print(f"  Band:         {stats.get('band', 'Unknown')}")
        print(f"  Connected:    {'Yes' if stats.get('connected') else 'No'}")
    
    async def _cmd_send(self, args: str):
        """Send a message."""
        if not args:
            print("\033[91mUsage: /send <message>\033[0m")
            return
        
        if self._message_handler:
            self._message_handler(args)
            print(f"\033[92m[You]\033[0m {args}")
        else:
            print("\033[91mMessage handler not configured.\033[0m")
    
    async def _cmd_link(self, args: str):
        """Start video link."""
        if self._link_start_handler:
            self._link_start_handler()
            print("\033[92mVideo link starting...\033[0m")
        else:
            print("\033[91mLink handler not configured.\033[0m")
    
    async def _cmd_stop(self, args: str):
        """Stop video link."""
        if self._link_stop_handler:
            self._link_stop_handler()
            print("\033[93mVideo link stopped.\033[0m")
        else:
            print("\033[91mLink handler not configured.\033[0m")
    
    async def _cmd_fan(self, args: str):
        """Set fan speed."""
        if not args:
            print("\033[91mUsage: /fan <0-100> or /fan auto\033[0m")
            return
        
        if not self._fan_handler:
            print("\033[91mFan handler not configured.\033[0m")
            return
        
        if args.lower() == 'auto':
            self._fan_handler(-1)  # -1 means auto
            print("\033[92mFan set to automatic mode.\033[0m")
        else:
            try:
                speed = int(args)
                if 0 <= speed <= 100:
                    self._fan_handler(speed)
                    print(f"\033[92mFan speed set to {speed}%\033[0m")
                else:
                    print("\033[91mSpeed must be 0-100.\033[0m")
            except ValueError:
                print("\033[91mInvalid speed. Use 0-100 or 'auto'.\033[0m")
    
    async def _cmd_peers(self, args: str):
        """Show connected peers."""
        # TODO: Implement when protocol is connected
        print("\033[93mNo peers connected (protocol not active).\033[0m")
    
    async def _cmd_quit(self, args: str):
        """Exit the application."""
        print("\033[93mShutting down...\033[0m")
        self.running = False
    
    def display_message(self, sender: str, message: str):
        """Display an incoming message."""
        color = "\033[96m" if sender != "You" else "\033[92m"
        print(f"\n{color}[{sender}]\033[0m {message}")
        print(self.PROMPT, end="", flush=True)
    
    def stop(self):
        """Stop the console loop."""
        self.running = False

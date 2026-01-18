"""
Hampter Link - Main Entry Point
Supports GUI and CLI modes.
"""
import warnings
# Suppress noisy warnings immediately
warnings.filterwarnings("ignore")

import sys
import asyncio
import argparse
import logging
import json
import signal
from typing import Optional

# Setup Logging
logging.basicConfig(level=logging.ERROR, format='%(asctime)s [%(name)s] %(message)s')
logger = logging.getLogger("Main")
logging.getLogger("asyncio").setLevel(logging.CRITICAL) # Silence asyncio

# Global shutdown event
shutdown_event = asyncio.Event()

def signal_handler(sig, frame):
    """Handle Ctrl+C cleanly."""
    shutdown_event.set()

def load_config(path: str = "config.json") -> dict:
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return {
            "node_type": "A",
            "network": {"interface": "wlan0"},
            "hardware": {"lcd_address": 0x27, "fan_pin": 2},
            "security": {}
        }

async def async_main(args, config):
    """Main async entry point."""
    
    # Import modules inside async main to avoid global side-effects
    from src.hardware.fan_ctrl import fan_ctrl
    from src.hardware.telemetry import Telemetry
    
    lcd = None
    if not args.no_lcd:
        from src.hardware.lcd_drv import LCDDriver
        lcd = LCDDriver(address=config['hardware'].get('lcd_address', 0x27))

    wifi = None
    if not args.no_wifi:
        from src.hardware.wifi_monitor import WifiMonitor
        wifi = WifiMonitor(interface=config['network'].get('interface', 'wlan0'))

    # Start Hardware Tasks
    tasks = []
    if not args.no_fan:
        tasks.append(asyncio.create_task(fan_ctrl.start_loop()))
    
    if lcd:
        tasks.append(asyncio.create_task(lcd.start_scroller()))

    # Interface Mode
    if args.mode == 'cli':
        from src.cli.console import SotaConsole
        console = SotaConsole()
        
        # Wire up console callbacks
        console.set_status_provider(lambda: {
            **Telemetry.get_status_dict(),
            **(wifi.get_stats() if wifi else {})
        })
        
        console.set_fan_handler(lambda s: fan_ctrl.set_manual_speed(s) if s >= 0 else fan_ctrl.set_auto_mode())
        
        # Run console
        console_task = asyncio.create_task(console.run())
        
        # Wait for shutdown signal OR console exit
        await asyncio.wait(
            [asyncio.create_task(shutdown_event.wait()), console_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # Ensure console stops
        console.stop()
        
    else:
        print("GUI mode requires local display. Use --mode cli for headless.")
        return

    # Cleanup Sequence
    fan_ctrl.stop()
    if lcd: lcd.stop()
    
    for t in tasks: t.cancel()
    
    # Allow tasks to cancel silently
    try:
        await asyncio.gather(*tasks, return_exceptions=True)
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(description="Hampter Link")
    # Allow --cli as a shortcut flag
    parser.add_argument('--cli', action='store_true', help="Shortcut for --mode cli")
    parser.add_argument('--mode', choices=['gui','cli'], default='gui')
    parser.add_argument('--config', default='config.json')
    parser.add_argument('--no-lcd', action='store_true')
    parser.add_argument('--no-fan', action='store_true')
    parser.add_argument('--no-wifi', action='store_true')
    args = parser.parse_args()

    # Handle the --cli shortcut
    if args.cli:
        args.mode = 'cli'

    config = load_config(args.config)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if args.mode == 'gui':
        print("Please run with --mode cli (or --cli) for the console.")
    else:
        try:
            asyncio.run(async_main(args, config))
        except KeyboardInterrupt:
            pass

if __name__ == "__main__":
    main()

"""
Hampter Link - Main Entry Point
Supports GUI and CLI modes.
"""
import sys
import asyncio
import argparse
import logging
import json
import signal
from typing import Optional

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(message)s')
logger = logging.getLogger("Main")
# Suppress noisy logs
logging.getLogger("asyncio").setLevel(logging.WARNING)

# Global shutdown event
shutdown_event = asyncio.Event()

def signal_handler(sig, frame):
    """Handle Ctrl+C cleanly."""
    logger.info("Shutdown signal received...")
    shutdown_event.set()

def load_config(path: str = "config.json") -> dict:
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        # Default config fallback
        return {
            "node_type": "A",
            "network": {"interface": "wlan0"},
            "hardware": {"lcd_address": 0x27, "fan_pin": 18},
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
        
        console.set_fan_handler(lambda s: fan_ctrl.set_manual_speed(s))
        
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
        # GUI Mode
        # TODO: GUI integration with asyncio.Event based shutdown
        # For now, we keep the simpler GUI loop if user requested GUI
        logger.error("GUI mode requires refactor for new signal handling. Use --mode cli")
        return

    # Cleanup Sequence
    logger.info("Cleaning up resources...")
    
    fan_ctrl.stop()
    if lcd: lcd.stop()
    
    for t in tasks:
        t.cancel()
    
    # Allow tasks to cancel
    await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("Shutdown complete.")


def main():
    parser = argparse.ArgumentParser(description="Hampter Link")
    parser.add_argument('--mode', choices=['gui','cli'], default='gui')
    parser.add_argument('--config', default='config.json')
    parser.add_argument('--no-lcd', action='store_true')
    parser.add_argument('--no-fan', action='store_true')
    parser.add_argument('--no-wifi', action='store_true')
    args = parser.parse_args()

    config = load_config(args.config)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if args.mode == 'gui':
        # Legacy GUI entry (simpler to keep separate for now given PyQt constraints)
        print("Please run with --mode cli for the new SOTA console.")
    else:
        try:
            asyncio.run(async_main(args, config))
        except KeyboardInterrupt:
            # Catch the one that might leak through
            pass

if __name__ == "__main__":
    main()

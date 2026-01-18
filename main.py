"""
Hampter Link - Main Entry Point
A secure, off-grid, high-bandwidth P2P multimedia system.

Supports both GUI and CLI modes with configurable hardware options.
"""
import sys
import asyncio
import argparse
import logging
import json

# Configure Logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger("Main")


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Hampter Link - Secure P2P Communication System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                    # Start with GUI (default)
  python main.py --mode cli         # Console mode only
  python main.py --no-lcd --no-fan  # Disable hardware
  python main.py -v                 # Verbose logging
        """
    )
    
    parser.add_argument(
        '--mode', '-m',
        choices=['gui', 'cli'],
        default='gui',
        help='Interface mode: gui (default) or cli (console only)'
    )
    
    parser.add_argument(
        '--config', '-c',
        default='config.json',
        help='Path to configuration file (default: config.json)'
    )
    
    # Hardware toggles
    parser.add_argument(
        '--no-lcd',
        action='store_true',
        help='Disable LCD display'
    )
    
    parser.add_argument(
        '--no-fan',
        action='store_true',
        help='Disable fan control'
    )
    
    parser.add_argument(
        '--no-wifi',
        action='store_true',
        help='Disable WiFi monitoring'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable debug logging'
    )
    
    return parser.parse_args()


def load_config(path: str = "config.json") -> dict:
    """Load configuration from JSON file."""
    try:
        with open(path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"{path} not found! Run setup first.")
        logger.info("Create config.json or copy from config.example.json")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {path}: {e}")
        sys.exit(1)


def run_cli_mode(config: dict, args):
    """Run in console-only mode."""
    from src.cli.console import Console
    from src.hardware.telemetry import Telemetry
    from src.hardware.fan_ctrl import fan_ctrl
    
    # Optional hardware
    lcd = None
    wifi = None
    
    if not args.no_lcd:
        from src.hardware.lcd_drv import LCDDriver
        lcd = LCDDriver(
            address=config['hardware']['lcd_address'],
            enabled=True
        )
    
    if not args.no_wifi:
        from src.hardware.wifi_monitor import WifiMonitor
        interface = config['network'].get('interface', 'wlan0')
        wifi = WifiMonitor(interface=interface)
    
    # Create console
    console = Console()
    
    # Status provider
    def get_status():
        stats = Telemetry.get_status_dict()
        if wifi:
            stats.update(wifi.get_stats())
        return stats
    
    console.set_status_provider(get_status)
    
    # Message handler (loopback for now)
    def send_message(msg: str):
        logger.info(f"TX: {msg}")
        if lcd:
            lcd.update_status(f"TX: {msg[:12]}")
        # TODO: Send via protocol when connected
    
    console.set_message_handler(send_message)
    
    # Fan handler
    def set_fan(speed: int):
        if speed < 0:
            fan_ctrl.set_auto_mode()
        else:
            fan_ctrl.set_manual_speed(speed)
    
    console.set_fan_handler(set_fan)
    
    # Run async loop
    async def async_main():
        # Start background tasks
        tasks = []
        
        if not args.no_fan:
            tasks.append(asyncio.create_task(fan_ctrl.start_loop()))
        
        if lcd:
            tasks.append(asyncio.create_task(lcd.start_scroller()))
        
        # Run console
        try:
            await console.run()
        finally:
            # Cleanup
            fan_ctrl.stop()
            if lcd:
                lcd.stop()
            
            for task in tasks:
                task.cancel()
    
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logger.info("Interrupted.")


def run_gui_mode(config: dict, args):
    """Run with GUI interface."""
    # Import GUI dependencies only when needed
    try:
        from PyQt6.QtWidgets import QApplication
        import qasync
    except ImportError as e:
        logger.error(f"GUI dependencies not available: {e}")
        logger.info("Install PyQt6: sudo apt install python3-pyqt6")
        logger.info("Or run in CLI mode: python main.py --mode cli")
        sys.exit(1)
    
    from src.gui.main_window import MainWindow
    from src.hardware.telemetry import Telemetry
    from src.hardware.fan_ctrl import fan_ctrl
    
    # Optional hardware
    lcd = None
    wifi = None
    
    if not args.no_lcd:
        from src.hardware.lcd_drv import LCDDriver
        lcd = LCDDriver(
            address=config['hardware']['lcd_address'],
            enabled=True
        )
    
    if not args.no_wifi:
        from src.hardware.wifi_monitor import WifiMonitor
        interface = config['network'].get('interface', 'wlan0')
        wifi = WifiMonitor(interface=interface)
    
    # Setup Qt Application and async event loop
    app = QApplication(sys.argv)
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    
    with loop:
        # Start hardware tasks
        if not args.no_fan:
            loop.create_task(fan_ctrl.start_loop())
        
        if lcd:
            loop.create_task(lcd.start_scroller())
            lcd.update_status("Hampter UI Ready")
        
        # Initialize GUI
        window = MainWindow()
        window.show()
        
        # Initialize media streamer
        from src.media.streamer import Streamer
        streamer = Streamer(xid=window.get_video_handle())
        
        # Connect signals
        def handle_send_msg(msg: str):
            logger.info(f"TX: {msg}")
            window.append_chat("System", f"Loopback: {msg}")
            if lcd:
                lcd.update_status(f"TX: {msg[:12]}")
        
        window.send_message_signal.connect(handle_send_msg)
        
        # Video link controls
        def start_video_link():
            logger.info("Starting Video Link...")
            streamer.start_receiver_display()
            if lcd:
                lcd.update_status("Video Link Active")
        
        def stop_video_link():
            logger.info("Stopping Video Link...")
            streamer.stop()
            if lcd:
                lcd.update_status("Video Link Stopped")
        
        window.btn_play.clicked.connect(start_video_link)
        window.btn_stop.clicked.connect(stop_video_link)
        
        # Telemetry update loop
        async def telemetry_loop():
            while True:
                try:
                    stats = Telemetry.get_status_dict()
                    if wifi:
                        stats.update(wifi.get_stats())
                    window.update_telemetry(stats)
                except Exception as e:
                    logger.error(f"Telemetry error: {e}")
                await asyncio.sleep(1)
        
        loop.create_task(telemetry_loop())
        
        logger.info("Hampter Link GUI initialized.")
        loop.run_forever()


def main():
    """Main entry point."""
    args = parse_args()
    
    # Set log level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Load configuration
    config = load_config(args.config)
    logger.info("Configuration loaded.")
    
    # Run appropriate mode
    if args.mode == 'cli':
        logger.info("Starting in CLI mode...")
        run_cli_mode(config, args)
    else:
        logger.info("Starting in GUI mode...")
        run_gui_mode(config, args)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

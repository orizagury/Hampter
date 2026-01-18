"""
Hampter Link - Main Entry Point
A secure, off-grid, high-bandwidth P2P multimedia system.
"""
import sys
import asyncio
import logging
import json
from PyQt6.QtWidgets import QApplication
import qasync

from src.gui.main_window import MainWindow
from src.protocol.quic_engine import HampterNode, create_quic_config
from src.protocol.packet_def import Lane
from src.hardware.fan_ctrl import fan_ctrl
from src.hardware.lcd_drv import LCDDriver
from src.hardware.telemetry import Telemetry
from src.hardware.wifi_monitor import WifiMonitor

# Configure Logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger("Main")


def load_config(path: str = "config.json") -> dict:
    """Load configuration from JSON file."""
    try:
        with open(path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"{path} not found! Run setup first.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {path}: {e}")
        sys.exit(1)


def setup_hardware(config: dict, loop: asyncio.AbstractEventLoop) -> tuple:
    """Initialize hardware controllers and start background tasks."""
    # Fan Controller
    loop.create_task(fan_ctrl.start_loop())
    
    # LCD Display
    lcd = LCDDriver(address=config['hardware']['lcd_address'])
    loop.create_task(lcd.start_scroller())
    
    # WiFi Monitor
    interface = config['network'].get('interface', 'wlan0')
    wifi = WifiMonitor(interface=interface)
    
    return lcd, wifi


def setup_media(window: MainWindow):
    """Initialize media streamer with GUI video container."""
    from src.media.streamer import Streamer
    return Streamer(xid=window.get_video_handle())


def connect_signals(window: MainWindow, streamer, lcd: LCDDriver):
    """Connect GUI signals to application logic."""
    
    # Chat message handler
    def handle_send_msg(msg: str):
        logger.info(f"TX: {msg}")
        # TODO: In full implementation, send via HampterNode
        # node.send_str(msg)
        window.append_chat("System", f"Loopback: {msg}")
    
    window.send_message_signal.connect(handle_send_msg)
    
    # Video link controls
    def start_video_link():
        logger.info("Starting Video Link...")
        streamer.start_receiver_display()
        lcd.update_status("Video Link Active")
    
    def stop_video_link():
        logger.info("Stopping Video Link...")
        streamer.stop()
        lcd.update_status("Video Link Stopped")
    
    window.btn_play.clicked.connect(start_video_link)
    window.btn_stop.clicked.connect(stop_video_link)


async def telemetry_loop(window: MainWindow, wifi: WifiMonitor):
    """Background task to update GUI with telemetry data."""
    while True:
        try:
            # Get system stats
            stats = Telemetry.get_status_dict()
            
            # Get WiFi stats
            wifi_stats = wifi.get_stats()
            stats.update(wifi_stats)
            
            # Update GUI
            window.update_telemetry(stats)
            
        except Exception as e:
            logger.error(f"Telemetry error: {e}")
        
        await asyncio.sleep(1)


def main():
    """Main application entry point."""
    # Load configuration
    config = load_config()
    logger.info("Configuration loaded.")
    
    # Setup Qt Application and async event loop
    app = QApplication(sys.argv)
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    
    with loop:
        # Initialize hardware
        lcd, wifi = setup_hardware(config, loop)
        
        # Initialize GUI
        window = MainWindow()
        window.show()
        lcd.update_status("Hampter UI Ready")
        
        # Initialize media streamer
        streamer = setup_media(window)
        
        # Connect signals
        connect_signals(window, streamer, lcd)
        
        # Start telemetry updates
        loop.create_task(telemetry_loop(window, wifi))
        
        # TODO: Start QUIC protocol engine
        # The protocol would be started here when ready for P2P connection
        # quic_cfg = create_quic_config(config, is_client=False)
        # loop.create_task(start_quic_server(config, quic_cfg))
        
        logger.info("Hampter Link initialized. Running event loop.")
        loop.run_forever()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.fatal(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

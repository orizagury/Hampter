"""
LCD Driver for Hampter Link.
Controls external SparkFun LCD display via I2C.
"""
import asyncio
import logging
from typing import List, Optional

logger = logging.getLogger("LCD")

# Track mock mode
MOCK_I2C = False
_smbus_error = None

# Try to import I2C library
try:
    from smbus2 import SMBus
except ImportError as e:
    MOCK_I2C = True
    _smbus_error = str(e)
    logger.warning("SMBus2 not found. Using Mock LCD.")
    SMBus = None


class LCDDriver:
    """
    I2C LCD Display Driver for 16x2 character displays.
    
    Supports scrolling status messages and direct text output.
    Gracefully degrades to mock mode if I2C is unavailable.
    
    Attributes:
        address: I2C address of the LCD (typically 0x27 or 0x3F)
        bus_id: I2C bus number (typically 1 on Raspberry Pi)
        enabled: Whether LCD hardware is enabled
    """
    
    LCD_WIDTH = 16
    MAX_MESSAGES = 5
    SCROLL_DELAY = 3.0  # Seconds between message changes
    
    def __init__(self, address: int = 0x27, bus_id: int = 1, enabled: bool = True):
        self.address = address
        self.bus_id = bus_id
        self.messages: List[str] = ["Hampter Link"]
        self.msg_idx = 0
        self.running = False
        self.enabled = enabled
        self.bus: Optional[object] = None
        self._mock_mode = MOCK_I2C or not enabled
        
        if not enabled:
            logger.info("LCD disabled by configuration.")
            return
        
        if MOCK_I2C:
            logger.warning(f"LCD mock mode: {_smbus_error}")
            return
        
        # Try to open the I2C bus
        try:
            self.bus = SMBus(bus_id)
            logger.info(f"LCD initialized on I2C bus {bus_id}, address 0x{address:02X}")
        except PermissionError as e:
            self._mock_mode = True
            logger.warning(f"LCD permission denied: {e}. Using mock mode.")
            logger.warning("Fix: sudo usermod -aG dialout $USER (then re-login)")
        except FileNotFoundError as e:
            self._mock_mode = True
            logger.warning(f"I2C bus not found: {e}. Using mock mode.")
        except Exception as e:
            self._mock_mode = True
            logger.warning(f"LCD init error: {e}. Using mock mode.")

    def init_display(self):
        """Initialize the LCD display with default settings."""
        if self._mock_mode:
            return
            
        try:
            # Standard HD44780 initialization sequence
            self._send_command(0x33)  # Initialize
            self._send_command(0x32)  # Set to 4-bit mode
            self._send_command(0x28)  # 2 lines, 5x7 matrix
            self._send_command(0x0C)  # Display ON, cursor OFF
            self._send_command(0x06)  # Entry mode: increment cursor
            self._send_command(0x01)  # Clear display
            asyncio.sleep(0.002)  # Wait for clear command
            
            logger.debug("LCD display initialized.")
        except Exception as e:
            logger.error(f"LCD init failed: {e}")
            self._mock_mode = True

    async def start_scroller(self):
        """Start the message scrolling loop."""
        self.running = True
        
        if not self._mock_mode:
            self.init_display()
        
        logger.info("LCD scroller started." + (" (mock)" if self._mock_mode else ""))
        
        while self.running:
            try:
                if self.messages:
                    msg = self.messages[self.msg_idx % len(self.messages)]
                    self.write_text(msg)
                    self.msg_idx += 1
            except Exception as e:
                logger.error(f"LCD scroll error: {e}")
            
            await asyncio.sleep(self.SCROLL_DELAY)

    def stop(self):
        """Stop the scroller and clear the display."""
        self.running = False
        self.clear()
        
        if self.bus:
            try:
                self.bus.close()
            except Exception:
                pass
        
        logger.info("LCD stopped.")

    def update_status(self, text: str):
        """
        Add a status message to the scroll queue.
        
        Args:
            text: Message to display (will be truncated to LCD_WIDTH)
        """
        # Truncate and pad to LCD width
        text = text[:self.LCD_WIDTH].ljust(self.LCD_WIDTH)
        self.messages.append(text)
        
        # Keep only recent messages
        if len(self.messages) > self.MAX_MESSAGES:
            self.messages.pop(0)
        
        logger.debug(f"LCD status: {text.strip()}")

    def write_text(self, text: str, line: int = 0):
        """
        Write text directly to the LCD.
        
        Args:
            text: Text to display
            line: Line number (0 or 1)
        """
        if self._mock_mode:
            return

        try:
            # Set cursor position
            if line == 0:
                self._send_command(0x80)  # Line 1
            else:
                self._send_command(0xC0)  # Line 2
            
            # Write characters
            for char in text[:self.LCD_WIDTH]:
                self._send_data(ord(char))
                
        except Exception as e:
            logger.error(f"LCD write error: {e}")

    def clear(self):
        """Clear the LCD display."""
        if self._mock_mode:
            return
            
        try:
            self._send_command(0x01)
        except Exception:
            pass

    def _send_command(self, cmd: int):
        """Send a command byte to the LCD."""
        if self.bus:
            self.bus.write_byte_data(self.address, 0x00, cmd)

    def _send_data(self, data: int):
        """Send a data byte to the LCD."""
        if self.bus:
            self.bus.write_byte_data(self.address, 0x40, data)

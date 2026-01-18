"""
LCD Driver for Hampter Link.
Controls external SparkFun LCD display via I2C.
"""
import asyncio
import logging
from typing import List

logger = logging.getLogger("LCD")

# Try to import I2C library
try:
    from smbus2 import SMBus
    MOCK_I2C = False
except ImportError:
    MOCK_I2C = True
    logger.warning("SMBus2 not found. Using Mock LCD.")
    
    class SMBus:
        """Mock SMBus for development environments."""
        def __init__(self, bus: int):
            pass
        
        def write_byte_data(self, addr: int, cmd: int, val: int):
            pass
        
        def write_i2c_block_data(self, addr: int, cmd: int, vals: list):
            pass
        
        def close(self):
            pass


class LCDDriver:
    """
    I2C LCD Display Driver for 16x2 character displays.
    
    Supports scrolling status messages and direct text output.
    
    Attributes:
        address: I2C address of the LCD (typically 0x27 or 0x3F)
        bus_id: I2C bus number (typically 1 on Raspberry Pi)
    """
    
    LCD_WIDTH = 16
    MAX_MESSAGES = 5
    SCROLL_DELAY = 3.0  # Seconds between message changes
    
    def __init__(self, address: int = 0x27, bus_id: int = 1):
        self.address = address
        self.bus_id = bus_id
        self.messages: List[str] = ["Hampter Link"]
        self.msg_idx = 0
        self.running = False
        
        self.bus = SMBus(bus_id)

    def init_display(self):
        """Initialize the LCD display with default settings."""
        if MOCK_I2C:
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
            
            logger.info("LCD initialized.")
        except Exception as e:
            logger.error(f"LCD init failed: {e}")

    async def start_scroller(self):
        """Start the message scrolling loop."""
        self.running = True
        self.init_display()
        
        logger.info("LCD scroller started.")
        
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
        if MOCK_I2C:
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
        if MOCK_I2C:
            return
            
        try:
            self._send_command(0x01)
        except Exception:
            pass

    def _send_command(self, cmd: int):
        """Send a command byte to the LCD."""
        self.bus.write_byte_data(self.address, 0x00, cmd)

    def _send_data(self, data: int):
        """Send a data byte to the LCD."""
        self.bus.write_byte_data(self.address, 0x40, data)

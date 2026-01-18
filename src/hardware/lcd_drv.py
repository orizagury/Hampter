"""
LCD Driver for Hampter Link.
Controls external SparkFun LCD display via I2C.
"""
import asyncio
import logging
from typing import List, Optional

logger = logging.getLogger("LCD")

MOCK_I2C = False
try:
    from smbus2 import SMBus
except ImportError:
    MOCK_I2C = True
    SMBus = None


class LCDDriver:
    """
    I2C LCD Display Driver.
    Gracefully falls back to mock if I2C is unavailable.
    """
    
    LCD_WIDTH = 16
    MAX_MESSAGES = 5
    SCROLL_DELAY = 3.0
    
    def __init__(self, address: int = 0x27, bus_id: int = 1, enabled: bool = True):
        self.address = address
        self.bus_id = bus_id
        self.messages: List[str] = ["Hampter Link"]
        self.msg_idx = 0
        self.running = False
        self.enabled = enabled
        self.bus = None
        
        if not enabled:
            return
            
        self._mock_mode = MOCK_I2C
        
        if not self._mock_mode:
            try:
                self.bus = SMBus(bus_id)
            except (PermissionError, FileNotFoundError, OSError):
                self._mock_mode = True
                logger.debug("I2C unavailable (Mock LCD active).")

    def init_display(self):
        """Initialize the LCD display."""
        if self._mock_mode or not self.bus:
            return
            
        try:
            self._send_command(0x33) # Init
            self._send_command(0x32) # 4-bit
            self._send_command(0x28) # 2 lines
            self._send_command(0x0C) # Display ON
            self._send_command(0x06) # Cursor Inc
            self._send_command(0x01) # Clear
        except Exception:
            self._mock_mode = True # Switch to mock on error

    async def start_scroller(self):
        """Start the message scrolling loop."""
        if not self.enabled: 
            return

        self.running = True
        self.init_display()
        logger.info("LCD scroller started.")
        
        while self.running:
            try:
                if self.messages:
                    msg = self.messages[self.msg_idx % len(self.messages)]
                    self.write_text(msg)
                    self.msg_idx += 1
            except Exception:
                pass # Prevent crash
            
            # Responsive sleep for clean shutdown
            for _ in range(30):
                if not self.running: break
                await asyncio.sleep(0.1)

    def stop(self):
        """Stop the scroller and cleanup."""
        self.running = False
        try:
            self.clear()
            if self.bus:
                self.bus.close()
        except Exception:
            pass

    def update_status(self, text: str):
        text = text[:self.LCD_WIDTH].ljust(self.LCD_WIDTH)
        self.messages.append(text)
        if len(self.messages) > self.MAX_MESSAGES:
            self.messages.pop(0)

    def write_text(self, text: str, line: int = 0):
        if self._mock_mode or not self.bus:
            return
        try:
            cmd = 0x80 if line == 0 else 0xC0
            self._send_command(cmd)
            for char in text[:self.LCD_WIDTH]:
                self._send_data(ord(char))
        except Exception:
            pass # Swallow IO errors

    def clear(self):
        if self._mock_mode or not self.bus:
            return
        try:
            self._send_command(0x01)
        except Exception:
            pass

    def _send_command(self, cmd: int):
        if self.bus:
            self.bus.write_byte_data(self.address, 0x00, cmd)

    def _send_data(self, data: int):
        if self.bus:
            self.bus.write_byte_data(self.address, 0x40, data)

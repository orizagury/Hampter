"""
Hardware Display Module for Qwiic SerLCD.
Displays peer messages on external 16x2 LCD.
"""
import qwiic_serlcd
import sys
import logging

logger = logging.getLogger("Hardware")

class LCDDisplay:
    def __init__(self):
        self.lcd = qwiic_serlcd.QwiicSerlcd()
        self.connected = False
        try:
            if self.lcd.connected:
                self.connected = True
                self.lcd.clearScreen()
                self.lcd.setBacklight(0, 100, 255) # Cyber Blue
                self.lcd.print("Hampter Link Up")
            else:
                logger.error("LCD not found on I2C bus.")
        except Exception as e:
            logger.error(f"LCD Init error: {e}")

    def show_msg(self, sender, message):
        """Displays a message on the LCD."""
        if not self.connected:
            return
            
        try:
            self.lcd.clearScreen()
            # Line 1: Peer Name/IP
            self.lcd.print(f"FR: {sender[:12]}")
            # Line 2: Message content
            self.lcd.setCursor(0, 1)
            self.lcd.print(message[:16])
        except Exception as e:
            logger.error(f"LCD Print error: {e}")

    def show_system(self, text):
        """Displays system status."""
        if not self.connected:
            return
        try:
            self.lcd.clearScreen()
            self.lcd.print("SYSTEM:")
            self.lcd.setCursor(0, 1)
            self.lcd.print(text[:16])
        except Exception as e:
            logger.error(f"LCD System blink error: {e}")

if __name__ == '__main__':
    # Test block
    d = LCDDisplay()
    if d.connected:
        d.show_msg("TEST", "Hello World!")

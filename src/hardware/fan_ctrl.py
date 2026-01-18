"""
Fan Controller for Hampter Link.
Provides PWM-based fan speed control based on CPU temperature.
"""
import asyncio
import logging

logger = logging.getLogger("FanCtrl")

# Try to import GPIO library
try:
    from gpiozero import PWMOutputDevice
    MOCK_GPIO = False
except ImportError:
    MOCK_GPIO = True
    logger.warning("GPIOZero not found. Using Mock Fan.")
    
    class PWMOutputDevice:
        """Mock PWM device for development environments."""
        def __init__(self, pin: int):
            self._value = 0.0
        
        @property
        def value(self) -> float:
            return self._value
        
        @value.setter
        def value(self, val: float):
            self._value = val

# Try to import psutil for temperature reading
try:
    import psutil
except ImportError:
    psutil = None
    logger.warning("psutil not found. Using mock temperature.")


class FanController:
    """
    PWM Fan Controller with automatic temperature-based speed adjustment.
    
    Attributes:
        pin: GPIO pin number for PWM output
        running: Whether the control loop is active
    """
    
    # Temperature thresholds for fan curve (Celsius -> Speed 0.0-1.0)
    FAN_CURVE = [
        (40, 0.0),   # Below 40°C: fan off
        (50, 0.3),   # 50°C: 30%
        (60, 0.6),   # 60°C: 60%
        (70, 0.8),   # 70°C: 80%
        (80, 1.0),   # 80°C+: 100%
    ]
    
    def __init__(self, pin: int = 18):
        self.pin = pin
        self.fan = PWMOutputDevice(pin)
        self.running = False
        self._current_speed = 0.0
        self._manual_override = False
        self._manual_speed = 0.0

    async def start_loop(self):
        """Start the automatic fan control loop."""
        self.running = True
        logger.info("Fan control loop started.")
        
        while self.running:
            try:
                if not self._manual_override:
                    temp = self._get_cpu_temp()
                    speed = self._calculate_speed(temp)
                    
                    if abs(speed - self._current_speed) > 0.05:
                        self.fan.value = speed
                        self._current_speed = speed
                        logger.debug(f"Temp: {temp:.1f}°C -> Fan: {speed*100:.0f}%")
                
            except Exception as e:
                logger.error(f"Fan control error: {e}")
            
            await asyncio.sleep(2)

    def stop(self):
        """Stop the fan control loop and turn off fan."""
        self.running = False
        self.fan.value = 0
        self._current_speed = 0
        logger.info("Fan control stopped.")

    def set_manual_speed(self, speed_percent: int):
        """
        Set fan speed manually (overrides automatic control).
        
        Args:
            speed_percent: Fan speed 0-100%
        """
        self._manual_override = True
        self._manual_speed = max(0.0, min(1.0, speed_percent / 100))
        self.fan.value = self._manual_speed
        self._current_speed = self._manual_speed
        logger.info(f"Manual fan speed: {speed_percent}%")

    def set_auto_mode(self):
        """Return to automatic temperature-based control."""
        self._manual_override = False
        logger.info("Fan control returned to auto mode.")

    def _get_cpu_temp(self) -> float:
        """Get current CPU temperature in Celsius."""
        if psutil is None:
            return 45.0  # Mock temperature
        
        try:
            temps = psutil.sensors_temperatures()
            
            # Try common sensor names
            for sensor_name in ['cpu_thermal', 'coretemp', 'k10temp', 'acpitz']:
                if sensor_name in temps and temps[sensor_name]:
                    return temps[sensor_name][0].current
            
            # Fallback: return first available sensor
            for name, entries in temps.items():
                if entries:
                    return entries[0].current
                    
        except Exception as e:
            logger.debug(f"Temperature read error: {e}")
        
        return 45.0  # Default fallback

    def _calculate_speed(self, temp: float) -> float:
        """
        Calculate fan speed based on temperature using smooth curve interpolation.
        
        Args:
            temp: Current CPU temperature in Celsius
            
        Returns:
            Fan speed as float 0.0 to 1.0
        """
        # Below minimum threshold
        if temp <= self.FAN_CURVE[0][0]:
            return self.FAN_CURVE[0][1]
        
        # Above maximum threshold
        if temp >= self.FAN_CURVE[-1][0]:
            return self.FAN_CURVE[-1][1]
        
        # Linear interpolation between curve points
        for i in range(len(self.FAN_CURVE) - 1):
            t1, s1 = self.FAN_CURVE[i]
            t2, s2 = self.FAN_CURVE[i + 1]
            
            if t1 <= temp < t2:
                # Linear interpolation
                ratio = (temp - t1) / (t2 - t1)
                return s1 + ratio * (s2 - s1)
        
        return 1.0  # Safety fallback

    @property
    def current_speed_percent(self) -> int:
        """Get current fan speed as percentage."""
        return int(self._current_speed * 100)


# Singleton instance
fan_ctrl = FanController()

"""
Fan Controller for Hampter Link.
Provides PWM-based fan speed control based on CPU temperature.
"""
import asyncio
import logging

logger = logging.getLogger("FanCtrl")

MOCK_GPIO = False

try:
    from gpiozero import PWMOutputDevice, Device
    from gpiozero.exc import BadPinFactory
    
    # Test if GPIO is actually accessible
    try:
        Device.ensure_pin_factory()
    except (BadPinFactory, Exception):
        MOCK_GPIO = True
        
except ImportError:
    MOCK_GPIO = True

if MOCK_GPIO:
    # Quietly switch to mock without loud warnings unless verbose
    logger.debug("Using Mock Fan (GPIO unavailable).")


class MockPWMDevice:
    """Mock PWM device for development/simulation."""
    def __init__(self, pin: int):
        self._value = 0.0
    
    @property
    def value(self) -> float:
        return self._value
    
    @value.setter
    def value(self, val: float):
        self._value = val
    
    def close(self):
        pass


# Try to import psutil for temperature reading
try:
    import psutil
except ImportError:
    psutil = None
    logger.debug("Using mock temperature (psutil unavailable).")


class FanController:
    """
    PWM Fan Controller with automatic temperature-based speed adjustment.
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
        self.running = False
        self._current_speed = 0.0
        self._manual_override = False
        self._manual_speed = 0.0
        
        if MOCK_GPIO:
            self.fan = MockPWMDevice(pin)
        else:
            try:
                self.fan = PWMOutputDevice(pin)
            except Exception as e:
                logger.error(f"GPIO Init Failed: {e}. Falling back to mock.")
                self.fan = MockPWMDevice(pin)

    async def start_loop(self):
        """Start the automatic fan control loop."""
        self.running = True
        logger.info("Fan control started.")
        
        while self.running:
            try:
                if not self._manual_override:
                    temp = self._get_cpu_temp()
                    speed = self._calculate_speed(temp)
                    
                    if abs(speed - self._current_speed) > 0.05:
                        try:
                            self.fan.value = speed
                        except Exception:
                            pass # Swallow GPIO errors during runtime
                        self._current_speed = speed
                
            except Exception:
                pass # Prevent loop crash
            
            # Use a longer sleep to check running flag more often for cleaner exit
            for _ in range(20): 
                if not self.running: break
                await asyncio.sleep(0.1)

    def stop(self):
        """Stop the fan control loop and turn off fan."""
        self.running = False
        try:
            self.fan.value = 0
            self.fan.close()
        except Exception:
            pass
        logger.info("Fan control stopped.")

    def set_manual_speed(self, speed_percent: int):
        """Set fan speed manually (overrides automatic control)."""
        self._manual_override = True
        self._manual_speed = max(0.0, min(1.0, speed_percent / 100))
        try:
            self.fan.value = self._manual_speed
        except Exception:
            pass
        self._current_speed = self._manual_speed

    def set_auto_mode(self):
        """Return to automatic temperature-based control."""
        self._manual_override = False

    def _get_cpu_temp(self) -> float:
        """Get current CPU temperature in Celsius."""
        if psutil is None:
            return 45.0
        
        try:
            temps = psutil.sensors_temperatures()
            for sensor_name in ['cpu_thermal', 'coretemp', 'k10temp', 'acpitz']:
                if sensor_name in temps and temps[sensor_name]:
                    return temps[sensor_name][0].current
            
            for entries in temps.values():
                if entries:
                    return entries[0].current
        except Exception:
            pass
        
        return 45.0

    def _calculate_speed(self, temp: float) -> float:
        if temp <= self.FAN_CURVE[0][0]:
            return self.FAN_CURVE[0][1]
        
        if temp >= self.FAN_CURVE[-1][0]:
            return self.FAN_CURVE[-1][1]
        
        for i in range(len(self.FAN_CURVE) - 1):
            t1, s1 = self.FAN_CURVE[i]
            t2, s2 = self.FAN_CURVE[i + 1]
            if t1 <= temp < t2:
                ratio = (temp - t1) / (t2 - t1)
                return s1 + ratio * (s2 - s1)
        
        return 1.0


fan_ctrl = FanController()

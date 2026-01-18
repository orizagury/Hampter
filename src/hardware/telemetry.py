"""
System Telemetry for Hampter Link.
Provides CPU, memory, battery, and temperature statistics.
"""
import logging
from typing import Dict, Any

logger = logging.getLogger("Telemetry")

# Try to import psutil
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    PSUTIL_AVAILABLE = False
    logger.warning("psutil not found. Using mock telemetry.")


class Telemetry:
    """
    System telemetry collector.
    
    Provides a unified interface for reading system statistics
    with graceful fallback for missing sensors.
    """
    
    @staticmethod
    def get_status_dict() -> Dict[str, Any]:
        """
        Get current system status as a dictionary.
        
        Returns:
            Dict with keys: cpu_percent, ram_percent, battery, temp
        """
        if PSUTIL_AVAILABLE:
            return {
                "cpu_percent": psutil.cpu_percent(interval=None),
                "ram_percent": psutil.virtual_memory().percent,
                "battery": Telemetry._get_battery(),
                "temp": Telemetry._get_temp(),
            }
        else:
            return {
                "cpu_percent": 0.0,
                "ram_percent": 0.0,
                "battery": 100.0,
                "temp": 45.0,
            }

    @staticmethod
    def _get_battery() -> float:
        """
        Get battery percentage.
        
        Returns:
            Battery percentage (0-100), or 100 if no battery present
        """
        if not PSUTIL_AVAILABLE:
            return 100.0
        
        try:
            batt = psutil.sensors_battery()
            if batt is not None:
                return batt.percent
        except Exception as e:
            logger.debug(f"Battery read error: {e}")
        
        return 100.0  # AC power / no battery

    @staticmethod
    def _get_temp() -> float:
        """
        Get CPU temperature in Celsius.
        
        Returns:
            Temperature in Celsius, or 0.0 if unavailable
        """
        if not PSUTIL_AVAILABLE:
            return 45.0
        
        try:
            temps = psutil.sensors_temperatures()
            
            # Try common sensor names in priority order
            priority_sensors = ['cpu_thermal', 'coretemp', 'k10temp', 'acpitz']
            
            for sensor_name in priority_sensors:
                if sensor_name in temps and temps[sensor_name]:
                    return temps[sensor_name][0].current
            
            # Fallback: use first available sensor
            for entries in temps.values():
                if entries:
                    return entries[0].current
                    
        except Exception as e:
            logger.debug(f"Temperature read error: {e}")
        
        return 0.0

    @staticmethod
    def get_disk_usage(path: str = "/") -> Dict[str, Any]:
        """
        Get disk usage statistics.
        
        Args:
            path: Filesystem path to check
            
        Returns:
            Dict with total, used, free (bytes) and percent
        """
        if not PSUTIL_AVAILABLE:
            return {"total": 0, "used": 0, "free": 0, "percent": 0}
        
        try:
            usage = psutil.disk_usage(path)
            return {
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent": usage.percent
            }
        except Exception:
            return {"total": 0, "used": 0, "free": 0, "percent": 0}

    @staticmethod
    def get_network_io() -> Dict[str, int]:
        """
        Get network I/O statistics.
        
        Returns:
            Dict with bytes_sent and bytes_recv
        """
        if not PSUTIL_AVAILABLE:
            return {"bytes_sent": 0, "bytes_recv": 0}
        
        try:
            io = psutil.net_io_counters()
            return {
                "bytes_sent": io.bytes_sent,
                "bytes_recv": io.bytes_recv
            }
        except Exception:
            return {"bytes_sent": 0, "bytes_recv": 0}

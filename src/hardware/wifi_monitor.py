"""
WiFi Adapter Monitor for Hampter Link.
Provides RSSI, band, and link quality information from the Intel AX210.
"""
import logging
import subprocess
import re
from typing import Optional, Dict, Any

logger = logging.getLogger("WifiMonitor")


class WifiMonitor:
    """
    Monitor WiFi adapter status using iw/iwconfig commands.
    Provides mock data when not running on a system with WiFi.
    """
    
    def __init__(self, interface: str = "wlan0"):
        self.interface = interface
        self._mock_mode = not self._check_interface_exists()
        
        if self._mock_mode:
            logger.warning(f"Interface '{interface}' not found. Using mock WiFi data.")
    
    def _check_interface_exists(self) -> bool:
        """Check if the WiFi interface exists on the system."""
        try:
            result = subprocess.run(
                ["ip", "link", "show", self.interface],
                capture_output=True,
                text=True,
                timeout=2
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get current WiFi statistics.
        
        Returns:
            Dict with keys: rssi, link_quality, frequency, band, connected
        """
        if self._mock_mode:
            return self._get_mock_stats()
        
        return self._get_real_stats()
    
    def _get_real_stats(self) -> Dict[str, Any]:
        """Get actual WiFi stats from the system."""
        stats = {
            'rssi': -70,
            'link_quality': 50,
            'frequency': 0,
            'band': 'Unknown',
            'connected': False
        }
        
        try:
            # Try iw first (more modern)
            result = subprocess.run(
                ["iw", "dev", self.interface, "link"],
                capture_output=True,
                text=True,
                timeout=2
            )
            
            if result.returncode == 0 and "Connected" in result.stdout:
                stats['connected'] = True
                stats.update(self._parse_iw_output(result.stdout))
            
            # Get signal strength from station dump
            result = subprocess.run(
                ["iw", "dev", self.interface, "station", "dump"],
                capture_output=True,
                text=True,
                timeout=2
            )
            
            if result.returncode == 0:
                stats.update(self._parse_station_dump(result.stdout))
                
        except subprocess.SubprocessError as e:
            logger.debug(f"iw command failed: {e}")
        except FileNotFoundError:
            logger.debug("iw not found, trying iwconfig")
            stats.update(self._get_iwconfig_stats())
        
        return stats
    
    def _parse_iw_output(self, output: str) -> Dict[str, Any]:
        """Parse iw link output for connection info."""
        stats = {}
        
        # Parse frequency
        freq_match = re.search(r'freq:\s*(\d+)', output)
        if freq_match:
            freq = int(freq_match.group(1))
            stats['frequency'] = freq
            stats['band'] = self._freq_to_band(freq)
        
        return stats
    
    def _parse_station_dump(self, output: str) -> Dict[str, Any]:
        """Parse iw station dump for signal stats."""
        stats = {}
        
        # Parse signal strength (RSSI)
        signal_match = re.search(r'signal:\s*(-?\d+)', output)
        if signal_match:
            rssi = int(signal_match.group(1))
            stats['rssi'] = rssi
            stats['link_quality'] = self._rssi_to_quality(rssi)
        
        return stats
    
    def _get_iwconfig_stats(self) -> Dict[str, Any]:
        """Fallback to iwconfig for older systems."""
        stats = {}
        
        try:
            result = subprocess.run(
                ["iwconfig", self.interface],
                capture_output=True,
                text=True,
                timeout=2
            )
            
            if result.returncode == 0:
                output = result.stdout
                
                # Parse signal level
                signal_match = re.search(r'Signal level[=:](-?\d+)', output)
                if signal_match:
                    rssi = int(signal_match.group(1))
                    stats['rssi'] = rssi
                    stats['link_quality'] = self._rssi_to_quality(rssi)
                
                # Parse frequency
                freq_match = re.search(r'Frequency[=:](\d+\.?\d*)\s*GHz', output)
                if freq_match:
                    freq_ghz = float(freq_match.group(1))
                    freq_mhz = int(freq_ghz * 1000)
                    stats['frequency'] = freq_mhz
                    stats['band'] = self._freq_to_band(freq_mhz)
                    
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
        
        return stats
    
    def _get_mock_stats(self) -> Dict[str, Any]:
        """Return mock WiFi stats for development environments."""
        import random
        
        # Simulate fluctuating signal
        base_rssi = -55
        rssi = base_rssi + random.randint(-10, 10)
        
        return {
            'rssi': rssi,
            'link_quality': self._rssi_to_quality(rssi),
            'frequency': 6115,  # 6 GHz band (WiFi 6E)
            'band': '6 GHz',
            'connected': True
        }
    
    @staticmethod
    def _freq_to_band(freq_mhz: int) -> str:
        """Convert frequency in MHz to band name."""
        if freq_mhz < 3000:
            return '2.4 GHz'
        elif freq_mhz < 6000:
            return '5 GHz'
        else:
            return '6 GHz'
    
    @staticmethod
    def _rssi_to_quality(rssi: int) -> int:
        """
        Convert RSSI (dBm) to link quality percentage.
        
        Typical ranges:
        - Excellent: -30 to -50 dBm
        - Good: -50 to -60 dBm
        - Fair: -60 to -70 dBm
        - Weak: -70 to -80 dBm
        - Poor: < -80 dBm
        """
        if rssi >= -50:
            return 100
        elif rssi <= -100:
            return 0
        else:
            # Linear interpolation between -50 (100%) and -100 (0%)
            return int(2 * (rssi + 100))
    
    def get_band_capabilities(self) -> Dict[str, bool]:
        """
        Check which frequency bands the adapter supports.
        Useful for the auto-band switching feature.
        """
        if self._mock_mode:
            return {'2.4GHz': True, '5GHz': True, '6GHz': True}
        
        capabilities = {'2.4GHz': False, '5GHz': False, '6GHz': False}
        
        try:
            result = subprocess.run(
                ["iw", "phy"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                output = result.stdout
                if '2412' in output or '2437' in output:
                    capabilities['2.4GHz'] = True
                if '5180' in output or '5745' in output:
                    capabilities['5GHz'] = True
                if '5955' in output or '6115' in output:
                    capabilities['6GHz'] = True
                    
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
        
        return capabilities

"""
Configuration Module for Hampter Link.
Stores defaults and runtime state.
"""
import socket
import os

class Config:
    # Network Defaults
    DEFAULT_PORT = 5567  # QUIC Port
    DISCOVERY_PORT = 5566  # UDP Beacon Port
    BEACON_INTERVAL = 2  # Seconds
    BEACON_MAGIC = b'HAMPTER:'

    # Paths
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    CERT_DIR = os.path.join(BASE_DIR, 'src', 'certs')
    CERT_PATH = os.path.join(CERT_DIR, 'cert.pem')
    KEY_PATH = os.path.join(CERT_DIR, 'key.pem')

    # UI Theme
    THEME = {
        'accent': 'magenta',
        'status_ok': 'green',
        'status_error': 'red',
        'border': 'cyan'
    }

    # Runtime State (Set during init)
    interface = None
    ip_address = None

    @staticmethod
    def get_hostname():
        return socket.gethostname()

cfg = Config()

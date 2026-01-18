"""
QUIC Server Module.
Handles incoming QUIC connections and streams.
"""
import asyncio
import logging
from typing import Dict, Callable, Optional
from aioquic.asyncio import QuicConnectionProtocol
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import StreamDataReceived, HandshakeCompleted, ConnectionTerminated

logger = logging.getLogger("QuicServer")

class HampterProtocol(QuicConnectionProtocol):
    _on_message_callback: Optional[Callable] = None
    _on_connect_callback: Optional[Callable] = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def quic_event_received(self, event):
        if isinstance(event, HandshakeCompleted):
            logger.info("SRV: Handshake Completed")
            if HampterProtocol._on_connect_callback:
                # Try multiple ways to get peer info
                peer = self._transport.get_extra_info('peername')
                if not peer:
                    # Some versions/platforms might use 'addr'
                    peer = self._transport.get_extra_info('addr')
                
                HampterProtocol._on_connect_callback(peer or ("Unknown", 0))
                
        elif isinstance(event, StreamDataReceived):
            try:
                data = event.data.decode('utf-8')
                stream_id = event.stream_id
                
                if stream_id == 0:
                    # Heartbeat
                    pass
                elif stream_id == 4:
                    if HampterProtocol._on_message_callback:
                        HampterProtocol._on_message_callback(data, self._transport.get_extra_info('peername'))
            except Exception as e:
                logger.error(f"SRV Decode error: {e}")
                
        elif isinstance(event, ConnectionTerminated):
            logger.info("SRV: Connection Terminated")

def build_quic_config(cert_path, key_path):
    configuration = QuicConfiguration(is_client=False)
    configuration.load_cert_chain(cert_path, key_path)
    return configuration

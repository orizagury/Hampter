"""
QUIC Server Module.
Handles incoming QUIC connections and streams.
"""
import asyncio
import logging
from typing import Dict, Callable, Optional
from aioquic.asyncio import QuicConnectionProtocol
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import StreamDataReceived, HandshakeCompleted

logger = logging.getLogger("QuicServer")

class HampterProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._on_message_callback: Optional[Callable] = None

    def connection_made(self, transport):
        super().connection_made(transport)
        logger.info("QUIC Connection Made")

    def quic_event_received(self, event):
        if isinstance(event, StreamDataReceived):
            data = event.data.decode('utf-8')
            stream_id = event.stream_id
            
            if stream_id == 0:
                # Heartbeat (Ping/Pong) - Client Stream 0
                pass
            elif stream_id == 4:
                # Chat Data - Client Stream 4
                if self._on_message_callback:
                    self._on_message_callback(data, self._transport.get_extra_info('peername'))
            else:
                 # Handle generic streams if any
                 pass
        
        elif isinstance(event, HandshakeCompleted):
            logger.info("QUIC Handshake Completed")

def build_quic_config(cert_path, key_path):
    configuration = QuicConfiguration(is_client=False)
    configuration.load_cert_chain(cert_path, key_path)
    return configuration

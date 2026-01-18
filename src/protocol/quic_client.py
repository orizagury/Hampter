"""
QUIC Client Module.
Handles outgoing connections to peers.
"""
import asyncio
import logging
from aioquic.asyncio import connect
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import StreamDataReceived, HandshakeCompleted
from aioquic.asyncio.protocol import QuicConnectionProtocol

logger = logging.getLogger("QuicClient")

class HampterClientProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._on_message_callback = None
        self._on_connect_callback = None

    def quic_event_received(self, event):
        if isinstance(event, HandshakeCompleted):
            logger.info("QUIC Handshake Completed!")
            if self._on_connect_callback:
                self._on_connect_callback()
        elif isinstance(event, StreamDataReceived):
            data = event.data.decode('utf-8')
            if self._on_message_callback:
                self._on_message_callback(data, None)

class QuicClient:
    def __init__(self, cert_path, dashboard=None):
        self.config = QuicConfiguration(is_client=True)
        # For self-signed, we disable strict verification for MVP
        self.config.verify_mode = False 
        self.protocol = None
        self.connected = False
        self.chat_stream_id = 4
        self.heartbeat_stream_id = 0
        self.dashboard = dashboard
    
    async def connect_to(self, ip, port, message_callback, connect_callback):
        if self.dashboard:
            self.dashboard.add_debug(f"QUIC: Connecting to {ip}:{port}")
        try:
            async with connect(
                ip, port, 
                configuration=self.config,
                create_protocol=HampterClientProtocol
            ) as protocol:
                self.protocol = protocol
                protocol._on_message_callback = message_callback
                
                # Set up on-connect callback to fire immediately on handshake
                def on_handshake_done():
                    self.connected = True
                    if self.dashboard:
                        self.dashboard.add_debug("QUIC: Handshake OK!")
                    connect_callback()
                    
                protocol._on_connect_callback = on_handshake_done
                
                # Keep connection alive with heartbeats
                while True:
                    await asyncio.sleep(1)
                    if self.connected:
                        protocol._quic.send_stream_data(self.heartbeat_stream_id, b'PING', end_stream=False)
                        protocol.transmit()
                    
        except Exception as e:
            if self.dashboard:
                self.dashboard.add_debug(f"QUIC Fail: {e}")
            self.connected = False

    def send_message(self, message: str):
        if self.connected and self.protocol:
            self.protocol._quic.send_stream_data(self.chat_stream_id, message.encode('utf-8'), end_stream=False)
            self.protocol.transmit()

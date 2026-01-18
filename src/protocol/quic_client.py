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

    def quic_event_received(self, event):
        if isinstance(event, StreamDataReceived):
            data = event.data.decode('utf-8')
            if self._on_message_callback:
                self._on_message_callback(data, None)

class QuicClient:
    def __init__(self, cert_path):
        self.config = QuicConfiguration(is_client=True)
        # For self-signed, we disable strict verification for MVP
        self.config.verify_mode = False 
        self.protocol = None
        self.connected = False
        self.chat_stream_id = None
        self.heartbeat_stream_id = None
    
    async def connect_to(self, ip, port, message_callback):
        logger.info(f"Connecting to {ip}:{port}...")
        try:
            async with connect(
                ip, port, 
                configuration=self.config,
                create_protocol=HampterClientProtocol
            ) as protocol:
                self.protocol = protocol
                protocol._on_message_callback = message_callback
                self.connected = True
                logger.info("Connected to Peer!")
                
                # Initialize Streams (Client Initiated Bidirectional)
                # Stream 0: Heartbeat
                # Stream 4: Chat
                self.heartbeat_stream_id = 0 
                self.chat_stream_id = 4
                
                # Keep connection alive
                while True:
                    await asyncio.sleep(1)
                    # Send Heartbeat on Stream 0
                    protocol._quic.send_stream_data(self.heartbeat_stream_id, b'PING', end_stream=False)
                    protocol.transmit()
                    
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self.connected = False

    def send_message(self, message: str):
        if self.connected and self.protocol and self.chat_stream_id is not None:
            # Send on Stream 4 (Chat)
            self.protocol._quic.send_stream_data(self.chat_stream_id, message.encode('utf-8'), end_stream=False)
            self.protocol.transmit()

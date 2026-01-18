"""
QUIC Client Module.
Handles outgoing connections to peers.
"""
import asyncio
import logging
import ssl
from aioquic.asyncio import connect
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import StreamDataReceived, HandshakeCompleted, ConnectionTerminated
from aioquic.asyncio.protocol import QuicConnectionProtocol

logger = logging.getLogger("QuicClient")

class HampterClientProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._on_message_callback = None
        self._on_connect_callback = None
        self._on_disconnect_callback = None

    def quic_event_received(self, event):
        if isinstance(event, HandshakeCompleted):
            logger.info("QUIC Handshake Completed!")
            if self._on_connect_callback:
                self._on_connect_callback()
        elif isinstance(event, StreamDataReceived):
            try:
                data = event.data.decode('utf-8')
                if self._on_message_callback:
                    self._on_message_callback(data, None)
            except Exception as e:
                logger.error(f"Decode error: {e}")
        elif isinstance(event, ConnectionTerminated):
            logger.warning("QUIC Connection Terminated")
            if self._on_disconnect_callback:
                self._on_disconnect_callback()

class QuicClient:
    def __init__(self, cert_path, dashboard=None):
        self.config = QuicConfiguration(is_client=True)
        # Force aioquic to ignore self-signed cert issues
        self.config.verify_mode = ssl.CERT_NONE
        
        self.protocol = None
        self.connected = False
        self.connecting = False
        self.target_ip = None
        self.chat_stream_id = 4
        self.heartbeat_stream_id = 0
        self.dashboard = dashboard
    
    async def connect_to(self, ip, port, message_callback, connect_callback):
        if self.dashboard:
            self.dashboard.add_debug(f"CLI: Connecting to {ip}:{port}")
        
        self.connecting = True
        self.target_ip = ip
        try:
            # We use a short timeout for the connection attempt
            async with connect(
                ip, port, 
                configuration=self.config,
                create_protocol=HampterClientProtocol,
                wait_connected=True # Wait for handshake
            ) as protocol:
                self.protocol = protocol
                protocol._on_message_callback = message_callback
                
                def on_handshake_done():
                    if not self.connected:
                        self.connected = True
                        if self.dashboard:
                            self.dashboard.add_debug("CLI: Handshake OK!")
                        connect_callback()
                    
                protocol._on_connect_callback = on_handshake_done
                
                # wait_connected=True returns AFTER handshake. If event happened during wait, 
                # we might have missed the trigger. We manually sync state here.
                if not self.connected:
                    on_handshake_done()
                
                # Proactively "Touch" the chat stream to open it for the server
                try:
                    protocol._quic.send_stream_data(self.chat_stream_id, b"", end_stream=False)
                    protocol.transmit()
                except Exception as e:
                    logger.warning(f"Initial stream touch failed: {e}")
                
                # Keep connection alive
                while True:
                    await asyncio.sleep(2)
                    if self.connected:
                        try:
                            protocol._quic.send_stream_data(self.heartbeat_stream_id, b'PING', end_stream=False)
                            protocol.transmit()
                        except Exception as e:
                            logger.error(f"Heartbeat fail: {e}")
                            break
                            
        except asyncio.TimeoutError:
            if self.dashboard: self.dashboard.add_debug("CLI Error: Timeout")
        except Exception as e:
            if self.dashboard:
                self.dashboard.add_debug(f"CLI Fail: {type(e).__name__}")
                logger.error(f"QUIC Connection Fail: {e}")
        finally:
            self.connected = False
            self.connecting = False

    def send_message(self, message: str):
        if self.connected and self.protocol:
            self.protocol._quic.send_stream_data(self.chat_stream_id, message.encode('utf-8'), end_stream=False)
            self.protocol.transmit()

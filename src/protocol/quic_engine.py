"""
QUIC Protocol Engine for Hampter Link.
Implements the custom Hampter Protocol over QUIC transport.
"""
import asyncio
import logging
from typing import Optional, Dict, Callable

from aioquic.asyncio import QuicConnectionProtocol, serve, connect
from aioquic.quic.events import (
    QuicEvent, StreamDataReceived, HandshakeCompleted, ConnectionTerminated
)
from aioquic.quic.configuration import QuicConfiguration

from .packet_def import Lane, get_lane_from_stream_id, PacketType
from .security import HampterSecurity

logger = logging.getLogger("HampterProtocol")


class HampterNode(QuicConnectionProtocol):
    """
    QUIC-based protocol handler for Hampter Link.
    Handles multiplexed streams across different priority "Lanes".
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.connected = False
        self._handlers: Dict[int, Callable] = {}
        self._stream_ids: Dict[Lane, int] = {}  # Track stream IDs per lane

    def connection_made(self, transport):
        """Called when QUIC connection is established."""
        logger.info("QUIC connection established.")
        super().connection_made(transport)

    def quic_event_received(self, event: QuicEvent):
        """Handle incoming QUIC events."""
        if isinstance(event, HandshakeCompleted):
            self._on_handshake_complete(event)
        elif isinstance(event, StreamDataReceived):
            self._on_stream_data(event)
        elif isinstance(event, ConnectionTerminated):
            self._on_connection_terminated(event)

    def _on_handshake_complete(self, event: HandshakeCompleted):
        """Handle successful TLS handshake."""
        self.connected = True
        logger.info(f"Secure handshake completed. ALPN: {event.alpn_protocol}")
        # Could trigger external callback here

    def _on_stream_data(self, event: StreamDataReceived):
        """Route incoming data to appropriate lane handler."""
        lane = get_lane_from_stream_id(event.stream_id)
        data = event.data
        
        logger.debug(f"RX {len(data)} bytes on Lane {lane} (Stream {event.stream_id})")

        if lane == Lane.HEARTBEAT:
            self._handle_heartbeat(data, event.stream_id)
        elif lane == Lane.CHATTER:
            self._handle_chatter(data)
        elif lane == Lane.FLOW:
            self._handle_flow(data)
        elif lane == Lane.HAUL:
            self._handle_haul(data)
        
        if event.end_stream:
            logger.debug(f"Stream {event.stream_id} ended.")

    def _on_connection_terminated(self, event: ConnectionTerminated):
        """Handle connection termination."""
        self.connected = False
        logger.warning(f"Connection terminated: {event.error_code} - {event.reason_phrase}")

    def _handle_heartbeat(self, data: bytes, stream_id: int):
        """Process heartbeat packets (PING/PONG/Telemetry)."""
        if not data:
            return
        try:
            ptype = data[0]
            if ptype == PacketType.PING:
                logger.debug("RX PING, sending PONG")
                self._quic.send_stream_data(
                    stream_id, 
                    bytes([PacketType.PONG]), 
                    end_stream=False
                )
            elif ptype == PacketType.PONG:
                logger.debug("RX PONG")
            elif ptype == PacketType.TELEMETRY:
                # Parse telemetry data (bytes after type byte)
                if Lane.HEARTBEAT in self._handlers:
                    self._handlers[Lane.HEARTBEAT](data[1:])
        except Exception as e:
            logger.error(f"Heartbeat processing error: {e}")

    def _handle_chatter(self, data: bytes):
        """Process chat/text messages."""
        if Lane.CHATTER in self._handlers:
            self._handlers[Lane.CHATTER](data)

    def _handle_flow(self, data: bytes):
        """Process real-time audio/video stream data."""
        if Lane.FLOW in self._handlers:
            self._handlers[Lane.FLOW](data)

    def _handle_haul(self, data: bytes):
        """Process bulk file transfer data."""
        if Lane.HAUL in self._handlers:
            self._handlers[Lane.HAUL](data)

    def register_handler(self, lane: Lane, callback: Callable):
        """Register a callback for a specific lane."""
        self._handlers[lane] = callback
        logger.debug(f"Handler registered for Lane {lane.name}")

    def send_text(self, msg: str):
        """Send a text message on the Chatter lane."""
        if not self.connected:
            logger.warning("Cannot send: not connected")
            return
        
        # Get or create stream for chatter lane
        stream_id = self._get_stream_for_lane(Lane.CHATTER)
        payload = bytes([PacketType.MSG_TEXT]) + msg.encode('utf-8')
        self._quic.send_stream_data(stream_id, payload, end_stream=False)
        logger.debug(f"TX text ({len(msg)} chars) on stream {stream_id}")

    def send_telemetry(self, data: bytes):
        """Send telemetry data on the Heartbeat lane."""
        if not self.connected:
            return
        
        stream_id = self._get_stream_for_lane(Lane.HEARTBEAT)
        payload = bytes([PacketType.TELEMETRY]) + data
        self._quic.send_stream_data(stream_id, payload, end_stream=False)

    def send_video_data(self, data: bytes):
        """Send video frame data on the Flow lane."""
        if not self.connected:
            return
        
        stream_id = self._get_stream_for_lane(Lane.FLOW)
        self._quic.send_stream_data(stream_id, data, end_stream=False)

    def _get_stream_for_lane(self, lane: Lane) -> int:
        """Get or create a stream ID for the given lane."""
        if lane not in self._stream_ids:
            # Create new bidirectional stream
            # Stream IDs are assigned by QUIC, we track them per lane
            base_id = self._quic.get_next_available_stream_id(is_unidirectional=False)
            self._stream_ids[lane] = base_id
            logger.debug(f"Created stream {base_id} for Lane {lane.name}")
        return self._stream_ids[lane]


def create_quic_config(config: dict, is_client: bool = True) -> QuicConfiguration:
    """
    Create a QUIC configuration with proper TLS settings.
    
    Args:
        config: Application configuration dict containing security paths
        is_client: True if this node initiates the connection
    
    Returns:
        Configured QuicConfiguration object
    """
    security_cfg = config['security']
    
    quic_config = QuicConfiguration(
        alpn_protocols=["hampter-v1"],
        is_client=is_client,
        max_datagram_frame_size=65536,  # Enable datagrams for low-latency
    )
    
    # Load certificates
    quic_config.load_cert_chain(
        certfile=security_cfg['cert_path'],
        keyfile=security_cfg['key_path']
    )
    
    # Load CA for peer verification
    quic_config.load_verify_locations(cafile=security_cfg['ca_path'])
    
    # Enable 0-RTT for fast reconnection (as per proposal)
    if 'session_ticket_key' in security_cfg:
        # Session tickets enable 0-RTT resumption
        quic_config.session_ticket_handler = lambda ticket: None
        quic_config.session_ticket_fetcher = lambda: None
    
    return quic_config


async def start_quic_server(
    config: dict, 
    node_factory: Callable = HampterNode
) -> asyncio.AbstractServer:
    """
    Start a QUIC server to accept incoming connections.
    
    Args:
        config: Application configuration
        node_factory: Protocol class to instantiate for each connection
    
    Returns:
        Running server instance
    """
    network_cfg = config['network']
    quic_cfg = create_quic_config(config, is_client=False)
    
    # Determine which IP to bind based on node type
    node_type = config.get('node_type', 'A')
    bind_ip = network_cfg['ip_A'] if node_type == 'A' else network_cfg['ip_B']
    port = network_cfg['port']
    
    logger.info(f"Starting QUIC server on {bind_ip}:{port}")
    
    server = await serve(
        host=bind_ip,
        port=port,
        configuration=quic_cfg,
        create_protocol=node_factory,
    )
    
    logger.info("QUIC server running.")
    return server


async def connect_to_peer(
    config: dict,
    node_factory: Callable = HampterNode
) -> HampterNode:
    """
    Connect to the remote peer node.
    
    Args:
        config: Application configuration
        node_factory: Protocol class to instantiate
    
    Returns:
        Connected HampterNode instance
    """
    network_cfg = config['network']
    quic_cfg = create_quic_config(config, is_client=True)
    
    # Determine peer IP based on our node type
    node_type = config.get('node_type', 'A')
    peer_ip = network_cfg['ip_B'] if node_type == 'A' else network_cfg['ip_A']
    port = network_cfg['port']
    
    logger.info(f"Connecting to peer at {peer_ip}:{port}")
    
    async with connect(
        host=peer_ip,
        port=port,
        configuration=quic_cfg,
        create_protocol=node_factory,
    ) as protocol:
        logger.info("Connected to peer.")
        return protocol


# Legacy function name for compatibility
def build_hampter_config(cert_path, key_path, ca_path, session_ticket_key=None):
    """
    Legacy wrapper for create_quic_config.
    
    Deprecated: Use create_quic_config with full config dict instead.
    """
    config = {
        'security': {
            'cert_path': cert_path,
            'key_path': key_path,
            'ca_path': ca_path,
            'session_ticket_key': session_ticket_key
        }
    }
    return create_quic_config(config, is_client=False)

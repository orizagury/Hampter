from enum import IntEnum

class Lane(IntEnum):
    HEARTBEAT = 0
    CHATTER = 1
    FLOW = 2
    HAUL = 3

class PacketType(IntEnum):
    # HEARTBEAT Lane (0)
    PING = 0x01
    PONG = 0x02
    TELEMETRY = 0x03 # CPU, Fan, Batt
    
    # CHATTER Lane (1)
    MSG_TEXT = 0x10
    MSG_ACK = 0x11
    
    # FLOW Lane (2)
    AV_DATA = 0x20
    
    # HAUL Lane (3)
    FILE_START = 0x30
    FILE_DATA = 0x31
    FILE_END = 0x32

def get_lane_from_stream_id(stream_id: int) -> int:
    """
    Returns the logical Lane ID based on the QUIC Stream ID.
    Formula: Stream ID % 4
    """
    return stream_id % 4

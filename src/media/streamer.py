"""
Media Streamer for Hampter Link.
Handles real-time video streaming using GStreamer.
"""
import logging

logger = logging.getLogger("MediaStreamer")

# Try to import GStreamer
try:
    import gi
    gi.require_version('Gst', '1.0')
    from gi.repository import Gst, GLib
    Gst.init(None)
    MOCK_GST = False
except (ImportError, ValueError) as e:
    logger.warning(f"GStreamer not available: {e}. Using mock streamer.")
    MOCK_GST = True
    
    # Mock Gst classes for development
    class Gst:
        class State:
            PLAYING = 1
            PAUSED = 2
            NULL = 0
        
        class FlowReturn:
            OK = 0


class Streamer:
    """
    GStreamer-based media streamer for receiving and displaying video.
    
    Receives H.264 encoded video data from the QUIC protocol and
    displays it in a PyQt widget.
    
    Attributes:
        xid: Window ID for video output (from PyQt widget)
    """
    
    def __init__(self, xid=None):
        self.pipeline_recv = None
        self.appsrc = None
        self.xid = xid
        self._is_playing = False

    def start_receiver_display(self):
        """
        Start the video receiver pipeline.
        
        Creates a GStreamer pipeline that accepts H.264 data via appsrc,
        decodes it, and displays in the configured window.
        """
        if MOCK_GST:
            logger.info("Mock receiver started.")
            self._is_playing = True
            return

        if self._is_playing:
            logger.warning("Receiver already running.")
            return

        # Pipeline: AppSrc -> Parse -> Decode -> Convert -> Display
        pipeline_str = (
            "appsrc name=src format=time is-live=True do-timestamp=True "
            "caps=video/x-h264,stream-format=byte-stream ! "
            "h264parse ! avdec_h264 ! videoconvert ! "
            "autovideosink sync=False"
        )
        
        try:
            self.pipeline_recv = Gst.parse_launch(pipeline_str)
            self.appsrc = self.pipeline_recv.get_by_name("src")
            
            # Set up window embedding if we have an XID
            if self.xid:
                bus = self.pipeline_recv.get_bus()
                bus.enable_sync_message_emission()
                bus.connect("sync-message::element", self._on_sync_message)
            
            # Start the pipeline
            self.pipeline_recv.set_state(Gst.State.PLAYING)
            self._is_playing = True
            
            logger.info("GStreamer receiver pipeline started.")
            
        except Exception as e:
            logger.error(f"Failed to start receiver: {e}")
            self._is_playing = False

    def push_data(self, data: bytes):
        """
        Push video data into the pipeline.
        
        Called by the QUIC engine when video packets arrive.
        
        Args:
            data: H.264 encoded video data
        """
        if MOCK_GST or not self.appsrc:
            return

        try:
            buf = Gst.Buffer.new_wrapped(data)
            result = self.appsrc.emit("push-buffer", buf)
            
            if result != Gst.FlowReturn.OK:
                logger.warning(f"Push buffer failed: {result}")
                
        except Exception as e:
            logger.error(f"Error pushing video data: {e}")

    def _on_sync_message(self, bus, msg):
        """Handle GStreamer bus messages for window embedding."""
        try:
            struct = msg.get_structure()
            if struct and struct.get_name() == "prepare-window-handle":
                sink = msg.src
                sink.set_window_handle(self.xid)
                logger.debug("Video sink embedded in window.")
        except Exception as e:
            logger.error(f"Sync message error: {e}")

    def stop(self):
        """Stop the video pipeline."""
        if MOCK_GST:
            self._is_playing = False
            logger.info("Mock receiver stopped.")
            return

        if self.pipeline_recv:
            try:
                self.pipeline_recv.set_state(Gst.State.NULL)
                logger.info("GStreamer receiver pipeline stopped.")
            except Exception as e:
                logger.error(f"Error stopping pipeline: {e}")
        
        self.pipeline_recv = None
        self.appsrc = None
        self._is_playing = False

    @property
    def is_playing(self) -> bool:
        """Check if the streamer is currently active."""
        return self._is_playing

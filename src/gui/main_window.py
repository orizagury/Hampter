"""
Main Window for Hampter Link GUI.
Implements the "HampterOS Dashboard" interface.
"""
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QGroupBox, QLabel, QPushButton, QLineEdit, QTextEdit, 
    QSlider, QProgressBar, QFrame
)
from PyQt6.QtCore import Qt, pyqtSlot, pyqtSignal
from PyQt6.QtGui import QFont
import logging

from .styles import DARK_THEME

logger = logging.getLogger("MainWindow")


class MainWindow(QMainWindow):
    """Main application window for Hampter Link."""
    
    send_message_signal = pyqtSignal(str)  # Signal to send text to Protocol

    def __init__(self, node_context=None):
        super().__init__()
        self.node = node_context
        
        self.setWindowTitle("Hampter Link Terminal")
        self.resize(1100, 700)
        self.setStyleSheet(DARK_THEME)

        # Central Widget & Main Layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # Main Layout: 2 Columns (Content + Sidebar)
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(15, 15, 15, 15)
        self.main_layout.setSpacing(20)

        # Left Column: Video & Header
        self.left_col = QVBoxLayout()
        self.main_layout.addLayout(self.left_col, stretch=3)
        
        # Right Column: Controls & Chat
        self.right_col = QVBoxLayout()
        self.main_layout.addLayout(self.right_col, stretch=1)

        self._setup_header()
        self._setup_video_area()
        self._setup_controls_area()
        self._setup_chat_area()
        
        # Status Bar
        self.status_label = QLabel("Initializing...")
        self.status_label.setStyleSheet("color: #a6adc8; padding-left: 5px;")
        self.statusBar().addWidget(self.status_label)
        
    def _setup_header(self):
        """Create top header bar with connection stats."""
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 10)
        
        # Logo / Title
        title = QLabel("HAMPTER LINK // COMMAND")
        title.setStyleSheet(
            "font-size: 18px; font-weight: bold; "
            "color: #89b4fa; letter-spacing: 2px;"
        )
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        # Connection Status Indicators
        self.lbl_band = QLabel("BAND: --")
        self.lbl_band.setStyleSheet(
            "background-color: #313244; padding: 5px 10px; border-radius: 4px;"
        )
        
        self.lbl_rssi = QLabel("RSSI: -- dBm")
        self.lbl_rssi.setStyleSheet(
            "background-color: #313244; padding: 5px 10px; border-radius: 4px;"
        )
        
        self.lbl_link_quality = QLabel("LINK: 0%")
        self.lbl_link_quality.setStyleSheet(
            "background-color: #313244; padding: 5px 10px; border-radius: 4px;"
        )

        header_layout.addWidget(self.lbl_band)
        header_layout.addWidget(self.lbl_rssi)
        header_layout.addWidget(self.lbl_link_quality)
        
        self.left_col.addWidget(header_widget)

    def _setup_video_area(self):
        """Create video display area with controls."""
        video_group = QGroupBox("VISUAL UPLINK")
        l_video = QVBoxLayout(video_group)
        l_video.setContentsMargins(2, 10, 2, 2)
        
        # Video container for GStreamer
        self.video_container = QWidget()
        self.video_container.setStyleSheet(
            "background-color: black; border-radius: 4px;"
        )
        self.video_container.setMinimumHeight(450)
        
        l_video.addWidget(self.video_container)
        
        # Control Buttons
        controls = QHBoxLayout()
        controls.setContentsMargins(0, 10, 0, 0)
        
        self.btn_play = QPushButton("ESTABLISH LINK")
        self.btn_play.setStyleSheet("""
            QPushButton { background-color: #a6e3a1; color: #1e1e2e; }
            QPushButton:hover { background-color: #94e2d5; }
        """)
        self.btn_play.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self.btn_stop = QPushButton("TERMINATE")
        self.btn_stop.setStyleSheet("""
            QPushButton { background-color: #f38ba8; color: #1e1e2e; }
            QPushButton:hover { background-color: #eba0ac; }
        """)
        self.btn_stop.setCursor(Qt.CursorShape.PointingHandCursor)

        controls.addWidget(self.btn_play)
        controls.addWidget(self.btn_stop)
        
        l_video.addLayout(controls)
        
        self.left_col.addWidget(video_group)

    def _setup_controls_area(self):
        """Create hardware control panel."""
        grp_hw = QGroupBox("SYSTEM CONTROL")
        l_hw = QVBoxLayout(grp_hw)
        l_hw.setSpacing(12)
        
        # CPU Temperature
        temp_box = QVBoxLayout()
        temp_header = QHBoxLayout()
        temp_header.addWidget(QLabel("CPU TEMP"))
        self.lbl_temp_val = QLabel("-- °C")
        self.lbl_temp_val.setAlignment(Qt.AlignmentFlag.AlignRight)
        temp_header.addWidget(self.lbl_temp_val)
        
        self.bar_temp = QProgressBar()
        self.bar_temp.setRange(0, 100)
        self.bar_temp.setValue(0)
        self.bar_temp.setTextVisible(False)
        self.bar_temp.setFixedHeight(8)
        
        temp_box.addLayout(temp_header)
        temp_box.addWidget(self.bar_temp)
        l_hw.addLayout(temp_box)
        
        self._add_separator(l_hw)
        
        # Fan Control
        fan_box = QVBoxLayout()
        fan_header = QHBoxLayout()
        fan_header.addWidget(QLabel("FAN SPEED"))
        self.lbl_fan_val = QLabel("0%")
        self.lbl_fan_val.setAlignment(Qt.AlignmentFlag.AlignRight)
        fan_header.addWidget(self.lbl_fan_val)
        
        self.slider_fan = QSlider(Qt.Orientation.Horizontal)
        self.slider_fan.setRange(0, 100)
        self.slider_fan.valueChanged.connect(
            lambda v: self.lbl_fan_val.setText(f"{v}%")
        )
        
        fan_box.addLayout(fan_header)
        fan_box.addWidget(self.slider_fan)
        l_hw.addLayout(fan_box)
        
        self._add_separator(l_hw)

        # Battery
        batt_box = QVBoxLayout()
        batt_header = QHBoxLayout()
        batt_header.addWidget(QLabel("REMOTE POWER"))
        self.lbl_batt_val = QLabel("-- %")
        self.lbl_batt_val.setAlignment(Qt.AlignmentFlag.AlignRight)
        batt_header.addWidget(self.lbl_batt_val)
        
        self.bar_batt = QProgressBar()
        self.bar_batt.setValue(0)
        self.bar_batt.setTextVisible(False)
        
        batt_box.addLayout(batt_header)
        batt_box.addWidget(self.bar_batt)
        l_hw.addLayout(batt_box)
        
        l_hw.addStretch()
        self.right_col.addWidget(grp_hw)

    def _add_separator(self, layout: QVBoxLayout):
        """Add a horizontal separator line to layout."""
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: #45475a;")
        layout.addWidget(line)

    def _setup_chat_area(self):
        """Create chat/messaging area."""
        grp_chat = QGroupBox("CHATTER LANE")
        l_chat = QVBoxLayout(grp_chat)
        
        self.txt_chat_log = QTextEdit()
        self.txt_chat_log.setReadOnly(True)
        self.txt_chat_log.setPlaceholderText("No messages yet...")
        
        input_row = QHBoxLayout()
        self.inp_msg = QLineEdit()
        self.inp_msg.setPlaceholderText("Transmit message...")
        self.inp_msg.returnPressed.connect(self._on_send_msg)
        
        self.btn_send = QPushButton("TX")
        self.btn_send.setFixedWidth(50)
        self.btn_send.clicked.connect(self._on_send_msg)
        self.btn_send.setCursor(Qt.CursorShape.PointingHandCursor)
        
        input_row.addWidget(self.inp_msg)
        input_row.addWidget(self.btn_send)
        
        l_chat.addWidget(self.txt_chat_log)
        l_chat.addLayout(input_row)
        
        self.right_col.addWidget(grp_chat)

    @pyqtSlot()
    def _on_send_msg(self):
        """Handle send message button/enter press."""
        msg = self.inp_msg.text().strip()
        if not msg:
            return
        
        self.append_chat("Me", msg)
        self.send_message_signal.emit(msg)
        self.inp_msg.clear()

    def append_chat(self, sender: str, msg: str):
        """Add a message to the chat log."""
        color = "#89b4fa" if sender == "Me" else "#a6e3a1"
        self.txt_chat_log.append(
            f"<span style='color:{color}; font-weight:bold;'>[{sender}]</span> {msg}"
        )
    
    def update_telemetry(self, stats: dict):
        """
        Update all telemetry displays with new stats.
        
        Args:
            stats: Dict containing cpu_percent, battery, temp, rssi, 
                   link_quality, band, connected
        """
        # CPU Temperature
        temp = stats.get('temp', 0)
        self.lbl_temp_val.setText(f"{temp:.1f} °C")
        # Color temperature bar based on value
        temp_pct = min(int(temp), 100)
        self.bar_temp.setValue(temp_pct)
        if temp > 70:
            self.bar_temp.setStyleSheet(
                "QProgressBar::chunk { background-color: #f38ba8; }"
            )
        elif temp > 55:
            self.bar_temp.setStyleSheet(
                "QProgressBar::chunk { background-color: #fab387; }"
            )
        else:
            self.bar_temp.setStyleSheet(
                "QProgressBar::chunk { background-color: #a6e3a1; }"
            )
        
        # Battery
        battery = stats.get('battery', 0)
        self.lbl_batt_val.setText(f"{battery:.0f}%")
        self.bar_batt.setValue(int(battery))
        
        # WiFi Stats
        rssi = stats.get('rssi', -100)
        self.lbl_rssi.setText(f"RSSI: {rssi} dBm")
        
        link_quality = stats.get('link_quality', 0)
        self.lbl_link_quality.setText(f"LINK: {link_quality}%")
        
        band = stats.get('band', '--')
        self.lbl_band.setText(f"BAND: {band}")
        
        # Update status bar
        connected = stats.get('connected', False)
        if connected:
            self.status_label.setText("Link Active")
            self.status_label.setStyleSheet("color: #a6e3a1; padding-left: 5px;")
        else:
            self.status_label.setText("Searching for peer...")
            self.status_label.setStyleSheet("color: #fab387; padding-left: 5px;")
    
    def get_video_handle(self):
        """Return window ID for GStreamer video sink."""
        return self.video_container.winId()

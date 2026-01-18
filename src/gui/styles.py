
# HSL Colors for reference:
# Background: #1e1e2e (Dark Blue-Grey)
# Surface: #313244 (Lighter Blue-Grey)
# Accent: #89b4fa (Blue)
# Text: #cdd6f4 (White-ish)
# Success: #a6e3a1 (Green)
# Error: #f38ba8 (Red)

DARK_THEME = """
QMainWindow {
    background-color: #1e1e2e;
    color: #cdd6f4;
}

QWidget {
    font-family: 'Segoe UI', 'Roboto', 'Helvetica Neue', sans-serif;
    font-size: 14px;
    color: #cdd6f4;
}

/* Group Box */
QGroupBox {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 8px;
    margin-top: 1.5em; /* Leave space for the title */
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top center;
    padding: 0 10px;
    background-color: #1e1e2e; /* Matches window bg to look floating */
    color: #89b4fa;
    border-radius: 4px;
}

/* Push Button */
QPushButton {
    background-color: #45475a;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    color: #cdd6f4;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #585b70;
}
QPushButton:pressed {
    background-color: #89b4fa;
    color: #1e1e2e;
}

/* Line Edit & Text Edit */
QLineEdit, QTextEdit {
    background-color: #181825;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 6px;
    selection-background-color: #585b70;
    color: #cdd6f4;
}
QLineEdit:focus, QTextEdit:focus {
    border: 1px solid #89b4fa;
}

/* Progress Bar */
QProgressBar {
    background-color: #181825;
    border: 1px solid #45475a;
    border-radius: 6px;
    text-align: center;
    color: #cdd6f4;
}
QProgressBar::chunk {
    background-color: #89b4fa;
    border-radius: 5px;
}

/* Sliders */
QSlider::groove:horizontal {
    border: 1px solid #45475a;
    height: 6px;
    background: #181825;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #89b4fa;
    border: 1px solid #89b4fa;
    width: 14px;
    margin: -5px 0;
    border-radius: 7px;
}
QSlider::handle:horizontal:hover {
    background: #b4befe;
}

/* Labels */
QLabel {
    color: #cdd6f4;
}

/* Scroll Bar */
QScrollBar:vertical {
    border: none;
    background: #181825;
    width: 10px;
    margin: 0px 0px 0px 0px;
}
QScrollBar::handle:vertical {
    background: #45475a;
    min-height: 20px;
    border-radius: 5px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* Status Bar */
QStatusBar {
    background-color: #11111b;
    color: #a6adc8;
}
"""

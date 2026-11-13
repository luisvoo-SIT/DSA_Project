#!/usr/bin/env python3
"""
Market Expand - PySide6 Desktop Application
Viewing monthly outlet inventory, inspecting batch expiry, predicting demand,
and allocating a shared restocking budget.
"""
import sys
import os

# Ensure current directory is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from ui.main_window import MainWindow


def main():
    # Enable High DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Market Expand")
    app.setOrganizationName("Retail Intelligence")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

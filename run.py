#!/usr/bin/env python3
"""
Utilities Tracker - Launcher
Run this script to start the application.
"""

import sys
import os
from pathlib import Path


def get_app_dir():
    """Get the application directory (works for both script and frozen exe)."""
    if getattr(sys, 'frozen', False):
        # Running as compiled EXE - use the temp extraction folder
        return Path(sys._MEIPASS)
    else:
        # Running as script
        return Path(__file__).parent


def get_data_dir():
    """Get the data directory (next to EXE or in project folder)."""
    if getattr(sys, 'frozen', False):
        # Running as EXE - data folder next to the executable
        return Path(sys.executable).parent / "data"
    else:
        # Running as script
        return Path(__file__).parent / "data"


def main():
    # Set up paths
    app_dir = get_app_dir()
    src_dir = app_dir / "src"
    data_dir = get_data_dir()
    
    # Ensure data directory exists
    data_dir.mkdir(exist_ok=True)
    
    # Add src to path
    sys.path.insert(0, str(src_dir))
    sys.path.insert(0, str(app_dir))
    
    # Database path
    db_path = data_dir / "utilities.db"
    
    # Import and run
    from main import MainWindow
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QIcon
    
    # Windows taskbar icon fix - must be set before QApplication
    if sys.platform == 'win32':
        import ctypes
        # Set app user model ID so Windows shows our icon in taskbar
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('utilityhq.app.1.0')
    
    app = QApplication(sys.argv)
    app.setApplicationName("UtilityHQ")
    app.setOrganizationName("Home Energy")
    
    # Set application-wide icon
    icon_path = app_dir / "resources" / "icon.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    
    window = MainWindow(str(db_path))
    window.show()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()

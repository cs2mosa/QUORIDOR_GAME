"""
main.py
=======
Application entry point for the Quoridor game.

Bootstrap sequence
------------------
1. Create QApplication and apply the master stylesheet + Manrope font.
2. Instantiate the QMainWindow with a fixed dark background.
3. Create GameController (owns GameState).
4. Create NavigationController (owns QStackedWidget + all 6 screens).
5. Inject BoardScreen reference into GameController for display updates.
6. Show the main window on the MainMenu screen.

Run
---
    python main.py
"""

from __future__ import annotations

import sys

from PySide6.QtCore    import Qt, QSize
from PySide6.QtGui     import QColor, QPalette
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QStackedWidget,
)

from views.styles       import STYLESHEET, COLORS
from controllers        import GameController, NavigationController


# ──────────────────────────────────────────────────────────────────────────────
# Application palette — force dark mode palette before any widget is created
# ──────────────────────────────────────────────────────────────────────────────

def _build_palette() -> QPalette:
    """
    Return a QPalette that matches the design-token dark theme.

    This prevents any un-styled widget (e.g. native dialogs) from flashing
    a light background.

    Returns
    -------
    QPalette
        Dark Material-inspired palette.
    """
    pal = QPalette()
    bg  = QColor(COLORS["background"])
    fg  = QColor(COLORS["on-surface"])
    mid = QColor(COLORS["surface-container"])

    pal.setColor(QPalette.ColorRole.Window,          bg)
    pal.setColor(QPalette.ColorRole.WindowText,      fg)
    pal.setColor(QPalette.ColorRole.Base,            QColor(COLORS["surface"]))
    pal.setColor(QPalette.ColorRole.AlternateBase,   mid)
    pal.setColor(QPalette.ColorRole.ToolTipBase,     mid)
    pal.setColor(QPalette.ColorRole.ToolTipText,     fg)
    pal.setColor(QPalette.ColorRole.Text,            fg)
    pal.setColor(QPalette.ColorRole.Button,          mid)
    pal.setColor(QPalette.ColorRole.ButtonText,      fg)
    pal.setColor(QPalette.ColorRole.BrightText,      QColor(COLORS["primary"]))
    pal.setColor(QPalette.ColorRole.Highlight,       QColor(COLORS["surface-variant"]))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(COLORS["primary"]))
    return pal


# ──────────────────────────────────────────────────────────────────────────────
# Main Window
# ──────────────────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    """
    Root application window.

    Contains a single QStackedWidget as its central widget.  All screen
    transitions are managed by the NavigationController, which holds a
    reference to this stack.

    Fixed minimum size: 1024 × 768 px.
    """

    MIN_WIDTH  = 1024
    MIN_HEIGHT = 768

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("QUORIDOR — Architectural Strategy")
        self.setMinimumSize(QSize(self.MIN_WIDTH, self.MIN_HEIGHT))
        self.resize(1280, 800)

        # Central stack
        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        # ── Controller bootstrap ─────────────────────────────────────────
        self._game_ctrl = GameController(parent=self)
        self._nav_ctrl  = NavigationController(
            stack     = self._stack,
            game_ctrl = self._game_ctrl,
        )

        # Inject the board screen reference so the game controller can
        # push display updates directly.
        self._game_ctrl.set_board_screen(self._nav_ctrl.board)

        # Start on the Main Menu
        self._nav_ctrl.go_to(0)


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    """Create the QApplication, apply styling, and run the event loop."""
    app = QApplication(sys.argv)

    # ── Dark palette ─────────────────────────────────────────────────────
    app.setPalette(_build_palette())

    # ── Stylesheet ────────────────────────────────────────────────────────
    app.setStyleSheet(STYLESHEET)

    # ── High-DPI policy (PySide6 ≥ 6.4) ─────────────────────────────────
    app.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # ── Application metadata ─────────────────────────────────────────────
    app.setApplicationName("Quoridor")
    app.setApplicationDisplayName("QUORIDOR — Architectural Strategy")
    app.setOrganizationName("AI Course Staff / ASUENG")

    # ── Main window ──────────────────────────────────────────────────────
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

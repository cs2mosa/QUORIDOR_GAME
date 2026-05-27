"""
views/screens/victory_screen.py
================================
Screen 5 — Victory Result

Displayed immediately after a game ends.  Shows:
  • Trophy icon + "VICTORY" headline + winner's name
  • Two stat tiles: Turns Taken · Walls Placed
  • "Return to Menu" outline button

Emits
-----
menu_requested  : Signal()   — Return to Menu button
rules_requested : Signal()   — TopBar RULES link
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QSizePolicy,
)

from views.components.top_bar import TopBar
from views.styles import COLORS, font


class _StatTile(QFrame):
    """Single stat display tile (label + big number)."""

    def __init__(self, caption: str, value: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("StatTile")
        self.setMinimumHeight(140)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(f"""
            QFrame#StatTile {{
                background-color: {COLORS['surface-container']};
                border: 1px solid {COLORS['outline']};
                border-radius: 8px;
            }}
            QFrame#StatTile:hover {{
                background-color: {COLORS['surface-container-high']};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(10)
        layout.setContentsMargins(24, 24, 24, 24)

        cap_lbl = QLabel(caption)
        cap_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cap_lbl.setFont(font("label-caps"))
        cap_lbl.setStyleSheet(
            f"color: {COLORS['on-surface-variant']}; background: transparent;"
        )
        layout.addWidget(cap_lbl)

        self._val_lbl = QLabel(value)
        self._val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        val_font = font("display-lg")
        self._val_lbl.setFont(val_font)
        self._val_lbl.setStyleSheet(
            f"color: {COLORS['primary']}; background: transparent;"
        )
        layout.addWidget(self._val_lbl)

    def set_value(self, value: str) -> None:
        """Update the displayed numeric value."""
        self._val_lbl.setText(value)


class VictoryScreen(QWidget):
    """
    Post-game victory screen.

    Call :meth:`show_result` before making the screen visible to populate
    the winner name and stats.
    """

    menu_requested  : Signal = Signal()
    rules_requested : Signal = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        top_bar = TopBar()
        top_bar.rules_requested.connect(self.rules_requested)
        root.addWidget(top_bar)

        # Centre canvas
        canvas = QWidget()
        canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        cl = QVBoxLayout(canvas)
        cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.setContentsMargins(48, 48, 48, 48)
        cl.setSpacing(0)

        # ── Trophy icon ─────────────────────────────────────────────────
        trophy_box = QLabel("🏆")
        trophy_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        trophy_box.setFixedSize(88, 88)
        trophy_box.setStyleSheet(f"""
            QLabel {{
                font-size: 42px;
                background-color: {COLORS['surface-container-high']};
                border: 1px solid {COLORS['outline']};
                border-radius: 12px;
            }}
        """)
        cl.addWidget(trophy_box, 0, Qt.AlignmentFlag.AlignHCenter)
        cl.addSpacing(24)

        # ── VICTORY headline ─────────────────────────────────────────────
        title = QLabel("VICTORY")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = font("display-lg")
        title_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 4)
        title.setFont(title_font)
        title.setStyleSheet(f"color: {COLORS['primary']}; background: transparent;")
        cl.addWidget(title)
        cl.addSpacing(8)

        self._winner_name_lbl = QLabel("")
        self._winner_name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        win_font = font("headline-md")
        win_font.setPointSize(22)
        self._winner_name_lbl.setFont(win_font)
        self._winner_name_lbl.setStyleSheet(
            f"color: {COLORS['tertiary-fixed']}; background: transparent;"
        )
        cl.addWidget(self._winner_name_lbl)
        cl.addSpacing(4)

        # ── Winner name sub-label ────────────────────────────────────────
        self._winner_lbl = QLabel("is our winner.")
        self._winner_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._winner_lbl.setFont(font("body-base"))
        self._winner_lbl.setStyleSheet(
            f"color: {COLORS['on-surface-variant']}; background: transparent;"
        )
        cl.addWidget(self._winner_lbl)
        cl.addSpacing(48)

        # ── Stat tiles ───────────────────────────────────────────────────
        tiles_row = QHBoxLayout()
        tiles_row.setSpacing(16)

        self._turns_tile = _StatTile("Turns Taken", "0")
        self._walls_tile = _StatTile("Walls Placed", "0")

        tiles_row.addWidget(self._turns_tile)
        tiles_row.addWidget(self._walls_tile)

        # Constrain width of the stat section
        stat_wrapper = QWidget()
        stat_wrapper.setMaximumWidth(640)
        stat_wrapper.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        stat_wrapper.setLayout(tiles_row)
        cl.addWidget(stat_wrapper, 0, Qt.AlignmentFlag.AlignHCenter)
        cl.addSpacing(40)

        # ── Return to Menu button ────────────────────────────────────────
        menu_btn = QPushButton("☰  Return to Menu")
        menu_btn.setObjectName("BtnOutline")
        menu_btn.setFont(font("headline-md"))
        menu_btn.setFixedHeight(56)
        menu_btn.setMinimumWidth(220)
        menu_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        menu_btn.clicked.connect(self.menu_requested)
        cl.addWidget(menu_btn, 0, Qt.AlignmentFlag.AlignHCenter)

        root.addWidget(canvas, stretch=1)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show_result(
        self,
        winner_name  : str,
        turns_taken  : int,
        walls_placed : int,
    ) -> None:
        """
        Populate the screen with the game's final statistics.

        Parameters
        ----------
        winner_name : str
            Display name of the winning player.
        turns_taken : int
            Total moves made across both players.
        walls_placed : int
            Number of walls placed by the winner.
        """
        (self._winner_name_lbl.setText(winner_name))
        self._winner_lbl.setText(f"{winner_name} is our winner.")
        self._turns_tile.set_value(str(turns_taken))
        self._walls_tile.set_value(str(walls_placed))
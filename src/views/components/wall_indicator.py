"""
views/components/wall_indicator.py
====================================
Visual wall-count indicator used on the Board screen.

The indicator mirrors the design from Image 4: a row of thin vertical bars
where filled bars = walls remaining and dim bars = walls used.

Each player sees their own WallIndicator below / above the board.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import QWidget, QSizePolicy

from views.styles import COLORS


class WallIndicator(QWidget):
    """
    Draws a row of 10 small vertical bars representing a player's wall
    inventory.  Filled bars are white; depleted bars are very dim.

    Parameters
    ----------
    player_idx : int
        0 → Player 1 colour scheme (primary white).
        1 → Player 2 colour scheme (coral secondary).
    parent : QWidget | None
        Optional parent widget.
    """

    # Visual constants ───────────────────────────────────────────────────
    BAR_WIDTH   = 7
    BAR_HEIGHT  = 22
    BAR_SPACING = 4
    BAR_RADIUS  = 2

    TOTAL_WALLS = 10

    def __init__(self, player_idx: int = 0, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._player_idx      = player_idx
        self._walls_remaining = self.TOTAL_WALLS
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFixedSize(
            self.TOTAL_WALLS * (self.BAR_WIDTH + self.BAR_SPACING) - self.BAR_SPACING,
            self.BAR_HEIGHT,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_walls(self, remaining: int) -> None:
        """
        Update the displayed wall count.

        Parameters
        ----------
        remaining : int
            How many walls the player has left (0–10).
        """
        self._walls_remaining = max(0, min(self.TOTAL_WALLS, remaining))
        self.update()   # trigger repaint

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paintEvent(self, _event) -> None:
        """Render the bar indicators."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Colour tokens
        active_hex = (
            COLORS["primary-fixed-dim"] if self._player_idx == 0
            else COLORS["secondary"]
        )
        dim_hex = COLORS["surface-variant"]

        for i in range(self.TOTAL_WALLS):
            x = i * (self.BAR_WIDTH + self.BAR_SPACING)
            rect = QRectF(x, 0, self.BAR_WIDTH, self.BAR_HEIGHT)

            # Filled (remaining) vs. depleted
            if i < self._walls_remaining:
                painter.setBrush(QColor(active_hex))
            else:
                painter.setBrush(QColor(dim_hex))

            painter.setPen(Qt.PenStyle.NoPen)

            path = QPainterPath()
            path.addRoundedRect(rect, self.BAR_RADIUS, self.BAR_RADIUS)
            painter.drawPath(path)

        painter.end()

"""
views/components/top_bar.py
============================
Reusable top navigation bar widget, identical to the bar that appears in
all six screen designs.

Emits
-----
rules_requested : Signal()
    Fired when the user clicks the "RULES" link in the top-right corner.
    The NavigationController connects this to the Rules screen push.
"""

from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton
from PySide6.QtGui import QFont

from views.styles import COLORS, font


class TopBar(QWidget):
    """
    Full-width top application bar rendered as a semi-transparent dark strip.

    The bar shows the game logo ("QUORIDOR") on the left and a RULES
    navigation button on the right.

    Attributes
    ----------
    rules_requested : Signal
        Emitted when the RULES button is clicked.
    """

    rules_requested: Signal = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("TopBar")
        self.setFixedHeight(64)
        self._build_ui()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Lay out the logo label and the Rules button."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(48, 0, 48, 0)
        layout.setSpacing(0)

        # ── Logo ────────────────────────────────────────────────────────
        logo = QLabel("QUORIDOR")
        logo_font = font("label-caps")
        logo_font.setPointSize(14)
        logo_font.setWeight(QFont.Weight.ExtraBold)
        logo_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 4)
        logo.setFont(logo_font)
        logo.setStyleSheet(f"color: {COLORS['primary']}; background: transparent;")

        layout.addWidget(logo)
        layout.addStretch()

        # ── Rules button ────────────────────────────────────────────────
        rules_btn = QPushButton("RULES")
        rules_btn.setFont(font("label-caps"))
        rules_btn.setStyleSheet(f"""
            QPushButton {{
                color: {COLORS['on-surface-variant']};
                background: transparent;
                border: none;
                font-size: 11px;
                letter-spacing: 1.5px;
                padding: 6px 0px;
            }}
            QPushButton:hover {{
                color: {COLORS['primary']};
            }}
        """)
        rules_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        rules_btn.clicked.connect(self.rules_requested)

        layout.addWidget(rules_btn)

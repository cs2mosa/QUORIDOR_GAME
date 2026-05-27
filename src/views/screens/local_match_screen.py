"""
views/screens/local_match_screen.py
=====================================
Screen 2 — Local Match Setup.

Two player name inputs arranged symmetrically with a "VS" divider.
Buttons: "Return to Menu" and "Begin Match".

Emits
-----
back_requested  : Signal()   — Return to Menu button
begin_requested : Signal(str, str)  — Begin Match; carries (p1_name, p2_name)
rules_requested : Signal()   — forwarded from TopBar
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFrame, QSizePolicy,
)

from views.components.top_bar import TopBar
from views.styles import COLORS, font


class LocalMatchScreen(QWidget):
    """Setup screen for a two-player local (human vs. human) game session."""

    back_requested  : Signal = Signal()
    begin_requested : Signal = Signal(str, str)
    rules_requested : Signal = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Build the full screen layout."""
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Top bar
        top_bar = TopBar()
        top_bar.rules_requested.connect(self.rules_requested)
        root.addWidget(top_bar)

        # Centre canvas
        canvas = QWidget()
        canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        canvas_layout = QVBoxLayout(canvas)
        canvas_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Setup card
        card = self._build_card()
        canvas_layout.addWidget(card, 0, Qt.AlignmentFlag.AlignCenter)

        root.addWidget(canvas, stretch=1)

    def _build_card(self) -> QFrame:
        """Construct the centred setup card."""
        card = QFrame()
        card.setObjectName("Card")
        card.setFixedWidth(640)
        card.setStyleSheet(f"""
            QFrame#Card {{
                background: rgba(23, 31, 51, 0.85);
                border: 1px solid {COLORS['outline-variant']};
                border-radius: 12px;
            }}
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(64, 56, 64, 56)
        layout.setSpacing(0)

        # ── Header ──────────────────────────────────────────────────────
        title = QLabel("LOCAL MATCH")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = font("display-lg")
        title_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 6)
        title.setFont(title_font)
        title.setStyleSheet(f"color: {COLORS['primary']}; background: transparent;")
        layout.addWidget(title)
        layout.addSpacing(8)

        sub = QLabel("Configure players to begin the session.")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setFont(font("body-base"))
        sub.setStyleSheet(
            f"color: {COLORS['on-surface-variant']}; background: transparent;"
        )
        layout.addWidget(sub)
        layout.addSpacing(48)

        # ── Player inputs row ────────────────────────────────────────────
        inputs_row = QHBoxLayout()
        inputs_row.setSpacing(0)

        # Player 1
        p1_col = self._player_column(
            player_num=1, input_attr="_p1_input",
            icon_char="♟",
            border_color=COLORS["primary-fixed"],
        )
        inputs_row.addLayout(p1_col, stretch=1)

        # VS divider
        vs_lbl = QLabel("VS")
        vs_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vs_lbl.setFont(font("label-caps", italic=True))
        vs_lbl.setFixedWidth(64)
        vs_lbl.setStyleSheet(
            f"color: rgba(200,199,190,0.4); background: transparent;"
        )
        inputs_row.addWidget(vs_lbl)

        # Player 2
        p2_col = self._player_column(
            player_num=2, input_attr="_p2_input",
            icon_char="♟",
            border_color=COLORS["secondary-fixed"],
        )
        inputs_row.addLayout(p2_col, stretch=1)

        layout.addLayout(inputs_row)
        layout.addSpacing(48)

        # ── Action buttons ───────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        back_btn = QPushButton("← Return to Menu")
        back_btn.setObjectName("BtnOutline")
        back_btn.setFont(font("label-caps"))
        back_btn.setFixedHeight(50)
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.clicked.connect(self.back_requested)

        begin_btn = QPushButton("Begin Match →")
        begin_btn.setObjectName("BtnPrimary")
        begin_btn.setFont(font("label-caps"))
        begin_btn.setFixedHeight(50)
        begin_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        begin_btn.clicked.connect(self._on_begin)

        btn_row.addWidget(back_btn,  stretch=1)
        btn_row.addWidget(begin_btn, stretch=1)
        layout.addLayout(btn_row)

        return card

    def _player_column(
        self,
        player_num: int,
        input_attr: str,
        icon_char: str,
        border_color: str,
    ) -> QVBoxLayout:
        """
        Build a vertical column for one player: avatar + label + text input.

        Parameters
        ----------
        player_num : int
            1 or 2 (for the label).
        input_attr : str
            Name of the instance attribute to store the QLineEdit reference.
        icon_char : str
            Unicode character to display as the pawn avatar.
        border_color : str
            Hex colour for the avatar circle border.

        Returns
        -------
        QVBoxLayout
            The assembled column layout.
        """
        col = QVBoxLayout()
        col.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        col.setSpacing(12)

        # Avatar circle
        avatar = QLabel(icon_char)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setFixedSize(80, 80)
        avatar.setStyleSheet(f"""
            QLabel {{
                font-size: 32px;
                background-color: {COLORS['surface-container-high']};
                border: 2px solid {border_color};
                border-radius: 40px;
                color: {border_color};
            }}
        """)
        col.addWidget(avatar, 0, Qt.AlignmentFlag.AlignHCenter)

        # Label
        lbl = QLabel(f"Player {player_num}")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setFont(font("label-caps"))
        lbl.setStyleSheet(
            f"color: {COLORS['on-surface-variant']}; background: transparent;"
        )
        col.addWidget(lbl)

        # Text input
        inp = QLineEdit()
        inp.setPlaceholderText("Enter Handler")
        inp.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inp.setFont(font("body-base"))
        inp.setStyleSheet(f"""
            QLineEdit {{
                background-color: {COLORS['surface']};
                color: {COLORS['primary']};
                border: 1px solid {COLORS['outline-variant']};
                border-radius: 2px;
                padding: 10px 16px;
            }}
            QLineEdit:focus {{
                border-color: {border_color};
            }}
        """)
        setattr(self, input_attr, inp)
        col.addWidget(inp)

        return col

    def _normal_input_style(self) -> str:
        return f"""
            QLineEdit {{
                background-color: {COLORS['surface']};
                color: {COLORS['primary']};
                border: 1px solid {COLORS['outline-variant']};
                border-radius: 2px;
                padding: 10px 16px;
            }}
            QLineEdit:focus {{
                border-color: {COLORS['primary-fixed']};
            }}
        """

    def _error_input_style(self) -> str:
        return f"""
            QLineEdit {{
                background-color: {COLORS['surface']};
                color: {COLORS['primary']};
                border: 1px solid {COLORS['error']};
                border-radius: 2px;
                padding: 10px 16px;
            }}
        """

    def _clear_errors(self, player_idx: int) -> None:
        if(player_idx == 0):
            self._p1_input.setStyleSheet(self._normal_input_style())
        if(player_idx == 1):
            self._p2_input.setStyleSheet(self._normal_input_style())

    # ------------------------------------------------------------------
    # Slot handlers
    # ------------------------------------------------------------------

    def _on_begin(self) -> None:
        """
        Validate that both players have entered names, then emit
        ``begin_requested`` with (player1_name, player2_name).
        """
        p1 = self._p1_input.text().strip()
        p2 = self._p2_input.text().strip()
        valid = True
        if not p1:
            self._p1_input.setStyleSheet(self._error_input_style())
            valid = False
        else:
            self._clear_errors(0)
            valid = True
        if not p2:
            self._p2_input.setStyleSheet(self._error_input_style())
            valid = True
        else:
            self._clear_errors(1)
        if not valid:
            return
        self.begin_requested.emit(p1 or "Player1", p2 or "Player2")

    # ------------------------------------------------------------------
    # Public reset
    # ------------------------------------------------------------------

    def reset_fields(self) -> None:
        """Clear both name inputs (called when returning from a game)."""
        self._p1_input.clear()
        self._p2_input.clear()
        self._clear_errors(0)
        self._clear_errors(1)

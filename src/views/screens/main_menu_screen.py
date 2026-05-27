"""
views/screens/main_menu_screen.py
===================================
Screen 1 — Main Menu

6Layout
------
• TopBar (fixed 64 px)
• Hero section:
    – Left half: title, description, CTA buttons + Load button
    – Right half: 3-D pawn image placeholder (gradient box)
• Footer

Emits
-----
local_match_requested : Signal()
ai_match_requested    : Signal()
load_game_requested   : Signal()   # CHANGE: new signal for loading saves
rules_requested       : Signal()
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QFrame,
)

from views.components.top_bar import TopBar
from views.styles import COLORS, font


class MainMenuScreen(QWidget):
    """
    Landing-page screen shown when the application first opens.

    Signals
    -------
    local_match_requested : Signal
        Emitted when the user clicks "Local Multiplayer".
    ai_match_requested : Signal
        Emitted when the user clicks "Play vs AI".
    load_game_requested : Signal
        CHANGE: Emitted when the user clicks "Load Game" on the main menu.
        This replaces the File→Load menu to ensure load only happens from
        the correct context (main menu) and prevents loading during a game.
    rules_requested : Signal
        Forwarded from the TopBar's RULES button.
    """

    local_match_requested : Signal = Signal()
    ai_match_requested    : Signal = Signal()
    load_game_requested   : Signal = Signal()   # CHANGE: new signal
    rules_requested       : Signal = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Assemble the full screen layout."""
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Top bar ─────────────────────────────────────────────────────
        top_bar = TopBar()
        top_bar.rules_requested.connect(self.rules_requested)
        root.addWidget(top_bar)

        # ── Hero section ─────────────────────────────────────────────────
        hero = QWidget()
        hero.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(72, 60, 72, 60)
        hero_layout.setSpacing(64)

        # Left: text + buttons
        left = self._build_left_panel()
        hero_layout.addWidget(left, stretch=1)

        # Right: visual placeholder (matches the 3D-pawn image region)
        right = self._build_right_panel()
        hero_layout.addWidget(right, stretch=1)

        root.addWidget(hero, stretch=1)

        # ── Footer ───────────────────────────────────────────────────────
        footer = self._build_footer()
        root.addWidget(footer)

    def _build_left_panel(self) -> QWidget:
        """Build the left half: headline, description, CTA buttons."""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Headline
        title = QLabel("ARCHITECTURE\nSTRATEGY")
        title.setFont(font("display-lg"))
        title.setStyleSheet(f"color: {COLORS['primary']}; background: transparent;")
        title.setWordWrap(False)
        layout.addWidget(title)
        layout.addSpacing(20)

        # Description
        desc = QLabel(
            "Navigate the complex geometry of the board. Place walls to hinder "
            "your opponent and master the art of spatial dominance in this "
            "high-stakes tactical experience."
        )
        desc.setFont(font("body-base"))
        desc.setStyleSheet(
            f"color: {COLORS['on-surface-variant']}; background: transparent;"
        )
        desc.setWordWrap(True)
        desc.setMaximumWidth(420)
        layout.addWidget(desc)
        layout.addSpacing(48)

        # Mode buttons row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(16)

        local_btn = self._make_mode_button(
            icon_text="👥",
            title="Local Multiplayer",
            subtitle="PASS & PLAY",
        )
        local_btn.clicked.connect(self.local_match_requested)

        ai_btn = self._make_mode_button(
            icon_text="🤖",
            title="Play vs AI",
            subtitle="SINGLE PLAYER",
        )
        ai_btn.clicked.connect(self.ai_match_requested)

        btn_row.addWidget(local_btn, stretch=1)
        btn_row.addWidget(ai_btn,    stretch=1)
        layout.addLayout(btn_row)

        # CHANGE: Added Load Game button below mode buttons.
        # This replaces the File→Load menu to ensure load only happens
        # from the main menu context, preventing accidental loading during
        # an active game.  Styled as an outline button for visual hierarchy.
        layout.addSpacing(16)
        load_btn = QPushButton("📂  Load Saved Game")
        load_btn.setObjectName("BtnOutline")
        load_btn.setFont(font("label-caps"))
        load_btn.setFixedHeight(48)
        load_btn.setMinimumWidth(220)
        load_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        load_btn.clicked.connect(self.load_game_requested)
        layout.addWidget(load_btn, 0, Qt.AlignmentFlag.AlignLeft)

        layout.addStretch()
        return w

    def _make_mode_button(
        self, icon_text: str, title: str, subtitle: str
    ) -> QPushButton:
        """
        Create a large mode-selection card button.

        Parameters
        ----------
        icon_text : str
            Emoji / unicode for the mode icon.
        title : str
            Primary label (e.g. "Local Multiplayer").
        subtitle : str
            Secondary label (e.g. "PASS & PLAY").

        Returns
        -------
        QPushButton
            Styled flat card button.
        """
        btn = QPushButton()
        btn.setObjectName("ModeBtn")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setMinimumHeight(88)

        # Inner layout: icon box + text column
        inner = QHBoxLayout(btn)
        inner.setContentsMargins(20, 18, 20, 18)
        inner.setSpacing(16)

        icon_box = QLabel(icon_text)
        icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_box.setFixedSize(48, 48)
        icon_box.setStyleSheet(
            f"background: {COLORS['surface-container']}; "
            f"border: 1px solid {COLORS['outline-variant']}; "
            f"border-radius: 24px; font-size: 22px;"
        )

        text_col = QVBoxLayout()
        text_col.setSpacing(4)

        title_lbl = QLabel(title)
        title_lbl.setFont(font("headline-md"))
        title_lbl.setStyleSheet(
            f"color: {COLORS['primary']}; background: transparent; border: none;"
        )

        sub_lbl = QLabel(subtitle)
        sub_lbl.setFont(font("label-caps"))
        sub_lbl.setStyleSheet(
            f"color: {COLORS['on-surface-variant']}; "
            f"background: transparent; border: none; letter-spacing: 2px;"
        )

        text_col.addWidget(title_lbl)
        text_col.addWidget(sub_lbl)

        inner.addWidget(icon_box)
        inner.addLayout(text_col)
        inner.addStretch()

        btn.setStyleSheet(f"""
            QPushButton#ModeBtn {{
                background-color: {COLORS['surface-container-high']};
                border: 1px solid {COLORS['outline-variant']};
                border-radius: 8px;
                text-align: left;
            }}
            QPushButton#ModeBtn:hover {{
                background-color: {COLORS['surface-bright']};
                border-color: {COLORS['outline']};
            }}
            QPushButton#ModeBtn:pressed {{
                background-color: {COLORS['surface-container']};
            }}
        """)
        return btn

    def _build_right_panel(self) -> QWidget:
        """
        Build the right visual region — a styled gradient box that stands in
        for the 3-D pawn render.
        """
        frame = QFrame()
        frame.setFixedHeight(440)
        frame.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 {COLORS['surface-container-high']},
                    stop:1 {COLORS['surface-container-lowest']}
                );
                border: 1px solid {COLORS['outline-variant']};
                border-radius: 12px;
            }}
        """)

        layout = QVBoxLayout(frame)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Decorative chess-pawn SVG placeholder label
        icon = QLabel("♟")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(
            f"font-size: 120px; color: {COLORS['primary-fixed-dim']}; "
            f"background: transparent; border: none;"
        )
        layout.addWidget(icon)

        sub = QLabel("QUORIDOR")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setFont(font("label-caps"))
        sub.setStyleSheet(
            f"color: {COLORS['outline']}; background: transparent; "
            f"border: none; letter-spacing: 6px;"
        )
        layout.addWidget(sub)

        return frame

    def _build_footer(self) -> QWidget:
        """Build the minimal dark footer bar."""
        footer = QFrame()
        footer.setFixedHeight(60)
        footer.setStyleSheet(
            f"background: {COLORS['surface-container-lowest']}; "
            f"border-top: 1px solid rgba(255,255,255,0.05);"
        )
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(48, 0, 48, 0)

        copy_lbl = QLabel("© 2026 QUORIDOR ARCHITECTURAL STRATEGY. ALL RIGHTS RESERVED.")
        copy_lbl.setFont(font("label-caps"))
        copy_lbl.setStyleSheet(
            f"color: {COLORS['outline']}; background: transparent; font-size: 9px;"
        )
        layout.addWidget(copy_lbl)
        layout.addStretch()

        return footer
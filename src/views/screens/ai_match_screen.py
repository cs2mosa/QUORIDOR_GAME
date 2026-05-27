"""
views/screens/ai_match_screen.py
==================================
Screen 3 — AI Match Setup

Player enters their handler name, selects one of three AI difficulty tiers
via radio-style card selectors, then starts the match or returns to menu.

Difficulty tiers
----------------
  Novice   (easy)   — predictable logic
  Adept    (medium) — adaptive strategy   ← default selection
  Architect (hard)  — flawless execution

Emits
-----
back_requested  : Signal()
begin_requested : Signal(str, str)  → (player_name, difficulty)
                  difficulty ∈ {"easy", "medium", "hard"}
rules_requested : Signal()
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFrame, QSizePolicy,
)

from views.components.top_bar import TopBar
from views.styles import COLORS, font


# Tier definitions: (value, display_name, subtitle, icon_unicode)
_TIERS: list[tuple[str, str, str, str]] = [
    ("easy",   "Novice",    "Predictable logic",   "☺"),
    ("medium", "Adept",     "Adaptive strategy",   "⚙"),
    ("hard",   "Architect", "Flawless execution",  "⬡"),
]


class _DiffCard(QFrame):
    """
    Clickable card representing one AI difficulty tier.

    Attributes
    ----------
    clicked : Signal()
        Emitted when this card is pressed.
    value : str
        The machine-readable difficulty value ("easy" / "medium" / "hard").
    """

    clicked: Signal = Signal()

    def __init__(
        self,
        value: str,
        title: str,
        subtitle: str,
        icon: str,
        is_hard: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.value    = value
        self._is_hard = is_hard
        self._selected = False

        self.setObjectName("DiffCard" if not is_hard else "DiffCardHard")
        self.setFixedHeight(140)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._build_ui(title, subtitle, icon)
        self._apply_style(selected=False)

    # ------------------------------------------------------------------

    def _build_ui(self, title: str, subtitle: str, icon: str) -> None:
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(6)
        layout.setContentsMargins(12, 18, 12, 18)

        icon_lbl = QLabel(icon)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet("font-size: 28px; background: transparent; border: none;")
        layout.addWidget(icon_lbl)

        title_lbl = QLabel(title)
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_lbl.setFont(font("headline-md"))
        title_lbl.setStyleSheet(
            f"color: {COLORS['on-surface']}; background: transparent; border: none;"
        )
        layout.addWidget(title_lbl)

        sub_lbl = QLabel(subtitle)
        sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub_lbl.setFont(font("label-caps"))
        sub_lbl.setStyleSheet(
            f"color: {COLORS['on-surface-variant']}; background: transparent; border: none;"
        )
        layout.addWidget(sub_lbl)

    def _apply_style(self, selected: bool) -> None:
        if selected:
            accent = COLORS["secondary"] if self._is_hard else COLORS["primary"]
            bg     = (
                f"rgba(125, 48, 41, 0.20)" if self._is_hard
                else COLORS["surface-container-high"]
            )
        else:
            accent = COLORS["outline-variant"]
            bg     = COLORS["surface-container-highest"]

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg};
                border: 1px solid {accent};
                border-radius: 8px;
            }}
            QFrame:hover {{
                border-color: rgba(255,255,255,0.3);
            }}
        """)

    def set_selected(self, state: bool) -> None:
        """Toggle the visual selection state."""
        self._selected = state
        self._apply_style(state)

    def mousePressEvent(self, event) -> None:
        self.clicked.emit()
        super().mousePressEvent(event)


class AiMatchScreen(QWidget):
    """Setup screen for a Human vs. AI game session."""

    back_requested  : Signal = Signal()
    begin_requested : Signal = Signal(str, str)   # (name, difficulty)
    rules_requested : Signal = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._selected_difficulty: str  = "medium"
        self._diff_cards: list[_DiffCard] = []
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        top_bar = TopBar()
        top_bar.rules_requested.connect(self.rules_requested)
        root.addWidget(top_bar)

        canvas = QWidget()
        canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        canvas_layout = QVBoxLayout(canvas)
        canvas_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        canvas_layout.addWidget(self._build_card(), 0, Qt.AlignmentFlag.AlignCenter)

        root.addWidget(canvas, stretch=1)

    def _build_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        card.setFixedWidth(660)
        card.setStyleSheet(f"""
            QFrame#Card {{
                background: rgba(23, 31, 51, 0.88);
                border: 1px solid {COLORS['surface-variant']};
                border-radius: 12px;
            }}
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(64, 52, 64, 52)
        layout.setSpacing(0)

        # ── Header ──────────────────────────────────────────────────────
        title = QLabel("Configure Match")
        title_font = font("display-lg")
        title_font.setPointSize(32)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color: {COLORS['primary']}; background: transparent;")
        layout.addWidget(title)
        layout.addSpacing(6)

        sub = QLabel("Player vs Artificial Intelligence")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setFont(font("body-base"))
        sub.setStyleSheet(
            f"color: {COLORS['on-surface-variant']}; background: transparent;"
        )
        layout.addWidget(sub)
        layout.addSpacing(40)

        # ── Player Handler ───────────────────────────────────────────────
        hdl_row = QHBoxLayout()
        hdl_row.setSpacing(8)
        p_icon = QLabel("♟")
        p_icon.setStyleSheet(f"color: {COLORS['on-surface-variant']}; font-size:14px; background:transparent;")
        hdl_lbl = QLabel("PLAYER HANDLER")
        hdl_lbl.setFont(font("label-caps"))
        hdl_lbl.setStyleSheet(f"color: {COLORS['on-surface-variant']}; background: transparent;")
        hdl_row.addWidget(p_icon)
        hdl_row.addWidget(hdl_lbl)
        hdl_row.addStretch()
        layout.addLayout(hdl_row)
        layout.addSpacing(8)

        self._name_input = QLineEdit(" ")
        self._name_input.setPlaceholderText("Enter Handler")
        self._name_input.setFont(font("headline-md"))
        self._name_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {COLORS['surface-container-highest']};
                color: {COLORS['primary']};
                border: 1px solid {COLORS['outline-variant']};
                border-radius: 2px;
                padding: 14px 16px;
                font-size: 18px;
            }}
            QLineEdit:focus {{
                border-color: {COLORS['primary']};
            }}
        """)
        self._name_input.textChanged.connect(self._clear_error)
        layout.addWidget(self._name_input)
        layout.addSpacing(24)

        # Separator
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: rgba(71,71,65,0.3); border:none;")
        layout.addWidget(sep)
        layout.addSpacing(24)

        # ── Difficulty selector ──────────────────────────────────────────
        diff_hdr_row = QHBoxLayout()
        diff_hdr_row.setSpacing(8)
        ai_icon = QLabel("⚙")
        ai_icon.setStyleSheet(f"color: {COLORS['on-surface-variant']}; font-size:14px; background:transparent;")
        diff_lbl = QLabel("AI DIFFICULTY")
        diff_lbl.setFont(font("label-caps"))
        diff_lbl.setStyleSheet(f"color: {COLORS['on-surface-variant']}; background: transparent;")
        diff_hdr_row.addWidget(ai_icon)
        diff_hdr_row.addWidget(diff_lbl)
        diff_hdr_row.addStretch()
        layout.addLayout(diff_hdr_row)
        layout.addSpacing(12)

        cards_row = QHBoxLayout()
        cards_row.setSpacing(16)

        for value, display, subtitle, icon in _TIERS:
            is_hard = (value == "hard")
            card_w  = _DiffCard(value, display, subtitle, icon, is_hard=is_hard)
            card_w.set_selected(value == self._selected_difficulty)
            card_w.clicked.connect(self._make_selector(value))
            self._diff_cards.append(card_w)
            cards_row.addWidget(card_w, stretch=1)

        layout.addLayout(cards_row)
        layout.addSpacing(40)

        # ── Action buttons ───────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(16)
        btn_row.addStretch()

        back_btn = QPushButton("← Return to Menu")
        back_btn.setObjectName("BtnOutline")
        back_btn.setFont(font("label-caps"))
        back_btn.setFixedHeight(50)
        back_btn.setMinimumWidth(180)
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.clicked.connect(self.back_requested)

        begin_btn = QPushButton("Initialize Match ▶")
        begin_btn.setObjectName("BtnPrimary")
        begin_btn.setFont(font("label-caps"))
        begin_btn.setFixedHeight(50)
        begin_btn.setMinimumWidth(200)
        begin_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        begin_btn.clicked.connect(self._on_begin)

        btn_row.addWidget(back_btn)
        btn_row.addWidget(begin_btn)
        layout.addLayout(btn_row)

        return card

    def _clear_error(self) -> None:
        self._name_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {COLORS['surface-container-highest']};
                color: {COLORS['primary']};
                border: 1px solid {COLORS['outline-variant']};
                border-radius: 2px;
                padding: 14px 16px;
                font-size: 18px;
            }}
            QLineEdit:focus {{
                border-color: {COLORS['primary']};
            }}
        """)

    def _make_error(self) -> None:
        self._name_input.setStyleSheet(f"""
                    QLineEdit {{
                        background-color: {COLORS['surface-container-highest']};
                        color: {COLORS['primary']};
                        border: 1px solid {COLORS['error']};
                        border-radius: 2px;
                        padding: 14px 16px;
                        font-size: 18px;
                    }}
                """)
    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _make_selector(self, value: str):
        """Return a closure that selects the given difficulty card."""
        def _select():
            self._selected_difficulty = value
            for card in self._diff_cards:
                card.set_selected(card.value == value)
        return _select

    def _on_begin(self) -> None:
        name = self._name_input.text().strip()
        if not name:
            self._make_error()
            return
        self.begin_requested.emit(name, self._selected_difficulty)

    def reset_fields(self) -> None:
        """Reset inputs when returning from a finished game."""
        self._clear_error()
        self._name_input.setText(" ")
        self._make_selector("medium")()
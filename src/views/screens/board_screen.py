"""
views/screens/board_screen.py
==============================
Screen 4 — Gameplay Board

This screen is the central game arena. It wraps:
  • TopBar (QUORIDOR logo + RULES)
  • Opponent HUD (top): player card left, wall indicator right
  • Central BoardWidget (square, vertically centred, responsive, max 520 px)
  • Active-player HUD (bottom): wall indicator left, player card right
  • Mode toggle + turn label
  • Bottom toolbar: Exit | Undo | Redo | Save | ─ | Reset

The screen owns NO game logic. It only:
  1. Exposes ``refresh()`` for the GameController to push new state.
  2. Forwards all user interactions upward via Signals.

Signals emitted (consumed by GameController)
--------------------------------------------
cell_clicked(row, col)
wall_clicked(r, c, orientation)
undo_requested()
redo_requested()
reset_requested()
exit_requested()
rules_requested()
save_requested()
wall_mode_toggled(bool)
"""

from __future__ import annotations
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QSizePolicy,
)

from models.wall import WallOrientation
from views.components.top_bar import TopBar
from views.components.board_widget import BoardWidget
from views.components.wall_indicator import WallIndicator
from views.styles import COLORS, font


class _PlayerHUD(QWidget):
    """
    Compact player card + wall indicator row.

    Parameters
    ----------
    player_idx : int
        0 → primary colour (white); 1 → secondary colour (coral).
    flipped : bool
        True for the opponent (top), False for the active player (bottom).
        Flipping reverses the horizontal order so the card always faces
        towards the board.
    """

    def __init__(
        self,
        player_idx : int = 0,
        flipped    : bool = False,
        parent     : QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._player_idx = player_idx
        self._flipped    = flipped
        self._active     = False
        self._build_ui()

    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Player card ──────────────────────────────────────────────────
        card = QFrame()
        card.setObjectName("PlayerCard")
        card.setFixedWidth(180)
        card.setFixedHeight(60)
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(12, 8, 12, 8)
        card_layout.setSpacing(12)

        pawn_color = (
            COLORS["primary"]    if self._player_idx == 0
            else COLORS["secondary"]
        )

        pawn_lbl = QLabel("♟")
        pawn_lbl.setFixedSize(38, 38)
        pawn_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pawn_lbl.setStyleSheet(f"""
            QLabel {{
                font-size: 18px;
                background: {COLORS['surface']};
                color: {pawn_color};
                border: 1px solid rgba(255,255,255,0.15);
                border-radius: 19px;
            }}
        """)

        self._name_lbl = QLabel("Player")
        self._name_lbl.setFont(font("label-caps"))
        self._name_lbl.setStyleSheet(
            f"color: {COLORS['on-surface']}; background: transparent;"
        )
        self._name_lbl.setMaximumWidth(90)

        if self._flipped:
            # Opponent: name first, then pawn icon
            card_layout.addWidget(pawn_lbl)
            card_layout.addWidget(self._name_lbl)
        else:
            # Active: pawn icon right side, name left (mirrored)
            card_layout.addStretch()
            card_layout.addWidget(self._name_lbl)
            card_layout.addWidget(pawn_lbl)

        # Active-turn pulsing dot (only visible for active player)
        self._pulse_dot = QLabel("● ", card)
        self._pulse_dot.setFixedSize(14, 14)
        self._pulse_dot.setStyleSheet(
            f"color: {COLORS['primary']}; font-size: 12px; "
            f"background: transparent;"
        )
        self._pulse_dot.setVisible(False)

        # ── Wall indicator ────────────────────────────────────────────────
        wall_col = QVBoxLayout()
        wall_col.setSpacing(4)
        wall_lbl = QLabel("Walls")
        wall_lbl.setFont(font("label-caps"))
        wall_lbl.setStyleSheet(
            f"color: {COLORS['on-surface-variant']}; background: transparent;"
        )
        self._wall_bar = WallIndicator(player_idx=self._player_idx)

        if self._flipped:
            wall_col.setAlignment(Qt.AlignmentFlag.AlignRight)
            wall_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        else:
            wall_col.setAlignment(Qt.AlignmentFlag.AlignLeft)
            wall_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)

        wall_col.addWidget(wall_lbl)
        wall_col.addWidget(self._wall_bar)

        if self._flipped:
           card_layout.addWidget(self._pulse_dot)
        else:
            card_layout.insertWidget(0, self._pulse_dot)

        if self._flipped:
            layout.addWidget(card)
            layout.addStretch()
            layout.addLayout(wall_col)
        else:
            layout.addLayout(wall_col)
            layout.addStretch()
            layout.addWidget(card)

    # ------------------------------------------------------------------
    # Public update API
    # ------------------------------------------------------------------

    def set_name(self, name: str) -> None:
        """Update the displayed player name."""
        # Truncate long names
        self._name_lbl.setText(name[:10] if len(name) > 10 else name)

    def set_walls(self, remaining: int) -> None:
        """Update the wall inventory bar."""
        self._wall_bar.set_walls(remaining)

    def set_active(self, active: bool) -> None:
        """Highlight this HUD as the active (current-turn) player."""
        self._active = active
        border = (
            f"border: 2px solid rgba(255,255,255,0.35);"
            if active else
            f"border: 1px solid {COLORS['outline-variant']};"
        )
        self.findChild(QFrame, "PlayerCard").setStyleSheet(f"""
            QFrame#PlayerCard {{
                background-color: {COLORS['surface-container-high']};
                {border}
                border-radius: 8px;
            }}
        """)
        self._pulse_dot.setVisible(active)


class BoardScreen(QWidget):
    """Gameplay screen — wraps the BoardWidget and both player HUDs."""

    # ── User-interaction signals ─────────────────────────────────────────
    cell_clicked  : Signal = Signal(int, int)
    wall_clicked  : Signal = Signal(int, int, WallOrientation)
    undo_requested: Signal = Signal()
    redo_requested: Signal = Signal()
    reset_requested: Signal = Signal()
    exit_requested : Signal = Signal()
    save_requested : Signal = Signal()
    rules_requested: Signal = Signal()
    wall_mode_toggled: Signal = Signal(bool)

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

        # ── Top bar ──────────────────────────────────────────────────────
        top_bar = TopBar()
        top_bar.rules_requested.connect(self.rules_requested)
        root.addWidget(top_bar)

        # ── Main canvas ──────────────────────────────────────────────────
        # A plain QWidget with a vertical layout that centres everything.
        # The BoardWidget handles its own responsive scaling via resizeEvent().
        canvas = QWidget()
        canvas.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        canvas.setStyleSheet("background: transparent;")
        canvas_layout = QVBoxLayout(canvas)
        canvas_layout.setContentsMargins(20, 16, 20, 16)
        canvas_layout.setSpacing(12)

        # -- Opponent HUD (top) --
        self._opp_hud = _PlayerHUD(player_idx=1, flipped=True)
        canvas_layout.addWidget(self._opp_hud)
        canvas_layout.addSpacing(20)

        # -- Board widget (expanding, square) --
        self._board = BoardWidget()
        self._board.cell_clicked.connect(self.cell_clicked)
        self._board.wall_clicked.connect(self.wall_clicked)
        # stretch to fills available vertical space, maintaining square aspect.
        canvas_layout.addWidget(self._board, stretch=1)
        canvas_layout.addSpacing(20)

        # -- Active player HUD (bottom) --
        self._me_hud = _PlayerHUD(player_idx=0, flipped=False)
        canvas_layout.addWidget(self._me_hud)

        # -- Mode toggle + turn label row --
        info_row = QHBoxLayout()
        info_row.setSpacing(16)
        info_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Mode button toggles between pawn & walls states
        # at each player's turn visually
        self._mode_btn = QPushButton("♟ Pawn Mode")
        self._mode_btn.setCheckable(True)
        self._mode_btn.setChecked(False)
        self._mode_btn.setObjectName("BtnOutline")
        self._mode_btn.setFont(font("label-caps"))
        self._mode_btn.setFixedHeight(55)
        self._mode_btn.setMinimumWidth(140)
        self._mode_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        # Receive the new checked state directly, avoiding the stale-state bug.
        self._mode_btn.toggled.connect(self._on_mode_toggled)

        # -- Turn status label --
        self._turn_lbl = QLabel("YOUR TURN")
        self._turn_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._turn_lbl.setFont(font("label-caps"))
        self._turn_lbl.setStyleSheet(
            f"color: {COLORS['on-surface-variant']}; background: transparent; "
            f"letter-spacing: 2px;"
        )

        info_row.addWidget(self._mode_btn)
        info_row.addWidget(self._turn_lbl)
        canvas_layout.addLayout(info_row)

        # -- Bottom control toolbar --
        toolbar = self._build_toolbar()
        canvas_layout.addWidget(toolbar, 0, Qt.AlignmentFlag.AlignHCenter)

        root.addWidget(canvas, stretch=1)

    def _build_toolbar(self) -> QFrame:
        """Build the 5-button bottom control bar: Exit | Undo | Redo | Save | Reset."""
        bar = QFrame()
        bar.setFixedHeight(68)
        bar.setStyleSheet(f"""
            QFrame {{
                background: rgba(6, 14, 32, 0.80);
                border: 1px solid rgba(255,255,255,0.05);
                border-radius: 16px;
            }}
        """)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(24, 0, 24, 0)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        def _round_btn(icon: str, label: str, danger: bool = False) -> QPushButton:
            btn = QPushButton(icon)
            btn.setToolTip(label)
            btn.setFixedSize(48, 48)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            normal_border = (
                f"rgba(255,180,170,0.35)" if danger else COLORS["outline-variant"]
            )
            normal_color  = COLORS["error"] if danger else COLORS["on-surface-variant"]
            hover_border  = COLORS["error"] if danger else COLORS["primary"]
            hover_color   = COLORS["error"] if danger else COLORS["primary"]
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {COLORS['surface-container']};
                    color: {normal_color};
                    border: 1px solid {normal_border};
                    border-radius: 24px;
                    font-size: 20px;
                }}
                QPushButton:hover {{
                    background: {"rgba(255,180,170,0.10)" if danger else COLORS['surface-container-high']};
                    border-color: {hover_border};
                    color: {hover_color};
                }}
                QPushButton:pressed {{
                    background: {COLORS['surface-container-lowest']};
                }}
                QPushButton:disabled {{
                    color: {COLORS['outline-variant']};
                    border-color: {COLORS['surface-container-high']};
                }}
            """)
            return btn

        # Exit button
        self._exit_btn = _round_btn("⎋", "Exit Game")
        self._exit_btn.clicked.connect(self.exit_requested)
        self._exit_btn.setShortcut(QKeySequence("Escape"))

        # Undo
        self._undo_btn = _round_btn("↩", "Undo Move")
        self._undo_btn.clicked.connect(self.undo_requested)
        self._undo_btn.setShortcut(QKeySequence("Ctrl+Z"))

        # Redo
        self._redo_btn = _round_btn("↪", "Redo Move")
        self._redo_btn.clicked.connect(self.redo_requested)
        self._redo_btn.setShortcut(QKeySequence("Ctrl+Y"))

        # CHANGE: Added Save button to toolbar (replaces File menu)
        self._save_btn = _round_btn("💾", "Save Game", True)
        self._save_btn.clicked.connect(self.save_requested)
        self._save_btn.setShortcut(QKeySequence("Ctrl+S"))

        # Vertical separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedHeight(32)
        sep.setFixedWidth(1)
        sep.setStyleSheet(f"background: rgba(71,71,65,0.5); border: none;")

        # Reset (danger colour)
        self._reset_btn = _round_btn("↺", "Reset Match", danger=True)
        self._reset_btn.clicked.connect(self.reset_requested)
        self._reset_btn.setShortcut(QKeySequence("Ctrl+R"))

        layout.addWidget(self._exit_btn)
        layout.addWidget(self._undo_btn)
        layout.addWidget(self._redo_btn)
        layout.addWidget(self._save_btn)
        layout.addWidget(sep)
        layout.addWidget(self._reset_btn)

        return bar

    def _on_mode_toggled(self, checked: bool) -> None:
        """Update button text and emit the new wall-mode state."""
        self._mode_btn.setText("⊞ Wall Mode" if checked else "♟ Pawn Mode")
        self.wall_mode_toggled.emit(checked)

    # ------------------------------------------------------------------
    # Public refresh API (called by GameController)
    # ------------------------------------------------------------------

    def refresh(
        self,
        *,
        player0_name        : str,
        player1_name        : str,
        player0_walls       : int,
        player1_walls       : int,
        pawn_positions      : list[tuple[int, int]],
        h_walls             : set[tuple[int, int]],
        v_walls             : set[tuple[int, int]],
        h_wall_owners       : dict[tuple[int, int], int] | None = None,
        v_wall_owners       : dict[tuple[int, int], int] | None = None,
        valid_moves         : list[tuple[int, int]],
        selected_pawn       : Optional[int],
        current_player      : int,
        can_undo            : bool,
        can_redo            : bool,
        turn_message        : str = "",
        wall_mode           : bool = False,
    ) -> None:
        """
        Push the full display state to all sub-widgets in one call.

        Called after every game action so the view always reflects the model.

        Parameters
        ----------
        player0_name, player1_name : str
            Display names for each player.
        player0_walls, player1_walls : int
            Remaining wall counts (0–10).
        pawn_positions : list[tuple[int, int]]
            [(p0_row, p0_col), (p1_row, p1_col)].
        h_walls, v_walls : set[tuple[int,int]]
            Placed wall sets.
        valid_moves : list[tuple[int, int]]
            Highlighted move targets.
        selected_pawn : int | None
            Currently selected pawn index.
        current_player : int
            Whose turn it is (0 or 1).
        can_undo, can_redo : bool
            Toolbar button enabled states.
        turn_message : str
            Short text for the turn label.
        """
        # Update HUDs
        self._me_hud.set_name(player0_name)
        self._me_hud.set_walls(player0_walls)
        self._me_hud.set_active(current_player == 0)

        self._opp_hud.set_name(player1_name)
        self._opp_hud.set_walls(player1_walls)
        self._opp_hud.set_active(current_player == 1)

        # Turn label
        if turn_message:
            self._turn_lbl.setText(turn_message.upper())
        else:
            active_name = player0_name if current_player == 0 else player1_name
            self._turn_lbl.setText(f"{active_name.upper()}'S TURN")

        # Mode toggle
        self._mode_btn.setChecked(wall_mode)
        self._mode_btn.setText("⊞ Wall Mode" if wall_mode else "♟ Pawn Mode")

        # Board
        self._board.refresh(
            pawn_positions = pawn_positions,
            h_walls        = h_walls,
            v_walls        = v_walls,
            valid_moves    = valid_moves,
            selected_pawn  = selected_pawn,
            h_wall_owners  = h_wall_owners,
            v_wall_owners  = v_wall_owners,
        )

        # Toolbar states
        self._undo_btn.setEnabled(can_undo)
        self._redo_btn.setEnabled(can_redo)

    def set_wall_mode_active(self, active: bool) -> None:
        """
        Toggle a visual cue telling the player they are in wall-placement mode.

        Parameters
        ----------
        active : bool
            True while the player is about to place a wall.
        """
        color = COLORS["secondary"] if active else COLORS["on-surface-variant"]
        self._turn_lbl.setStyleSheet(
            f"color: {color}; background: transparent; letter-spacing: 2px;"
        )
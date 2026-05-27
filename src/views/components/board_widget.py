"""
views/components/board_widget.py
=================================
Custom-painted 9×9 Quoridor board widget.

Responsibilities
----------------
• Draws the grid of cells, gap strips (wall slots), and board border.
• Renders placed horizontal and vertical walls with player colors.
• Renders both player pawns as filled circles with smooth animations.
• Highlights valid pawn move targets on hover / after pawn selection.
• Shows a pulsing translucent wall preview while hovering over a wall slot.
• Translates mouse events into semantic game signals consumed by the
  GameController.

Coordinate helpers (scale-aware)
--------------------------------
All geometry is multiplied by self._scale which is computed in resizeEvent()
so the board remains square and centred at any window size.

Signals emitted
---------------
cell_clicked(row, col)       — user clicked on an empty cell
wall_clicked(r, c, orientation) — user clicked on a wall slot
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

from PySide6.QtCore import Qt, QPoint, QPointF, QRectF, Signal, QTimer, QSize
from PySide6.QtGui import (
     QColor, QPainter, QPen, QBrush, QRadialGradient,
     QMouseEvent,
)
from PySide6.QtWidgets import QWidget, QSizePolicy

from models.wall import WallOrientation
from views.styles import COLORS, font


# ──────────────────────────────────────────────────────────────────────────────
# Internal element types returned by hit-testing
# ──────────────────────────────────────────────────────────────────────────────

class _ElemKind(Enum):
    CELL          = auto()
    H_WALL_SLOT   = auto()
    V_WALL_SLOT   = auto()
    INTERSECTION  = auto()
    OUTSIDE       = auto()


@dataclass
class _BoardElem:
    kind   : _ElemKind
    row    : int = -1
    col    : int = -1
    wall_r : int = -1   # wall-grid row (0-7)
    wall_c : int = -1   # wall-grid col (0-7)
    orientation: Optional[WallOrientation] = None


# ──────────────────────────────────────────────────────────────────────────────
# BoardWidget
# ──────────────────────────────────────────────────────────────────────────────

class BoardWidget(QWidget):
    """
    Responsive, animated, owner-aware Quoridor board rendered via QPainter.
    Widget computes a scale factor in resizeEvent() so the board fills
    available space while remaining square.
    All painting and hit-testing use this scale.

    Signals
    -------
    cell_clicked(row, col)
        Emitted when the user left-clicks a board cell.
    wall_clicked(r, c, orientation)
        Emitted when the user left-clicks a valid wall slot.
    """

    # ── Qt Signals ──────────────────────────────────────────────────────────
    cell_clicked  : Signal = Signal(int, int)
    wall_clicked  : Signal = Signal(int, int, WallOrientation)

    # ── Visual constants (base size before scaling) ───────────────────────────
    CELL_SIZE  : int = 52    # pixel width/height of one grid cell at 1×
    WALL_GAP   : int = 7     # pixel width of wall-slot strip at 1×
    PADDING    : int = 14    # board outer padding at 1×
    PAWN_RATIO : float = 0.50   # pawn radius as fraction of CELL_SIZE/2

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # ── State exposed to the controller ─────────────────────────────────
        # These are set externally (by GameController) before each repaint.
        self.pawn_positions   : list[tuple[int, int]] = [(8, 4), (0, 4)]
        self.h_walls          : set[tuple[int, int]]  = set()
        self.v_walls          : set[tuple[int, int]]  = set()
        self.h_wall_owners    : dict[tuple[int, int], int] = {}
        self.v_wall_owners    : dict[tuple[int, int], int] = {}
        self.valid_moves      : list[tuple[int, int]] = []
        self.selected_pawn    : Optional[int]          = None   # 0 or 1

        # ── Hover / preview state ────────────────────────────────────────────
        self._hover_elem      : Optional[_BoardElem] = None
        self._wall_preview    : Optional[_BoardElem] = None   # filled when hovering slot

        # ── Responsive scale ───────────────────────────────────────────────
        # The widget now expands to fill its container while maintaining
        # a square aspect ratio via sizeHint() and resizeEvent().
        self._scale = 1.0
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.setMinimumSize(300, 300)

        # ── Pawn animation ───────────────────────────────────────────────────
        # _display_positions stores float (row, col) for sub-cell interpolation
        self._display_positions: list[tuple[float, float]] = [(8.0, 4.0), (0.0, 4.0)]
        self._target_positions : list[tuple[int, int]]      = [(8, 4), (0, 4)]
        self._anim_step        : int = 0
        self._anim_timer       = QTimer(self)
        self._anim_timer.timeout.connect(self._on_anim_tick)
        self._ANIM_STEPS       = 10

        # ── Wall preview pulse ───────────────────────────────────────────────
        self._preview_alpha : int = 100
        self._preview_dir   : int = 1
        self._preview_timer = QTimer(self)
        self._preview_timer.timeout.connect(self._on_preview_pulse)
        self._preview_timer.start(120)

        self.setMouseTracking(True)

    # ------------------------------------------------------------------
    # Animation
    # ------------------------------------------------------------------

    def _on_anim_tick(self) -> None:
        """Advance pawn tweening by one frame."""
        self._anim_step += 1
        t = self._anim_step / self._ANIM_STEPS
        if t >= 1.0:
            self._display_positions = [
                (float(r), float(c)) for r, c in self._target_positions
            ]
            self._anim_timer.stop()
        else:
            # ease-out cubic
            ease = 1 - (1 - t) ** 3
            new_pos: list[tuple[float, float]] = []
            for i in range(2):
                sr, sc = self._display_positions[i]
                tr, tc = self._target_positions[i]
                new_pos.append((sr + (tr - sr) * ease, sc + (tc - sc) * ease))
            self._display_positions = new_pos
        self.update()

    def _on_preview_pulse(self) -> None:
        """Oscillate wall-preview alpha for a shimmer effect."""
        self._preview_alpha += self._preview_dir * 15
        if self._preview_alpha >= 140:
            self._preview_alpha = 140
            self._preview_dir = -1
        elif self._preview_alpha <= 60:
            self._preview_alpha = 60
            self._preview_dir = 1
        self.update()

    # ------------------------------------------------------------------
    # Public update API (called by GameController / BoardScreen)
    # ------------------------------------------------------------------

    def refresh(
        self,
        pawn_positions : list[tuple[int, int]],
        h_walls        : set[tuple[int, int]],
        v_walls        : set[tuple[int, int]],
        valid_moves    : list[tuple[int, int]],
        selected_pawn  : Optional[int],
        h_wall_owners  : dict[tuple[int, int], int] | None = None,
        v_wall_owners  : dict[tuple[int, int], int] | None = None,
    ) -> None:
        """
        Update all display state at once and trigger a repaint.
        If pawn positions changed, starts a smooth tween animation.

        Parameters
        ----------
        pawn_positions : list[tuple[int, int]]
            [(p0_row, p0_col), (p1_row, p1_col)].
        h_walls : set[tuple[int, int]]
            All placed horizontal walls as (r, c).
        v_walls : set[tuple[int, int]]
            All placed vertical walls as (r, c).
        valid_moves : list[tuple[int, int]]
            Squares highlighted as valid move targets for the active player.
        selected_pawn : int | None
            Index of the pawn currently selected (shows move highlights).
        h_wall_owners, v_wall_owners : dict | None
            Maps wall coordinate → player index for colour rendering.
        """
        self.pawn_positions = pawn_positions
        self.h_walls        = h_walls
        self.v_walls        = v_walls
        self.valid_moves    = valid_moves
        self.selected_pawn  = selected_pawn
        if h_wall_owners is not None:
            self.h_wall_owners = h_wall_owners
        if v_wall_owners is not None:
            self.v_wall_owners = v_wall_owners

        # Start animation if pawns moved
        if list(pawn_positions) != self._target_positions:
            self._target_positions = list(pawn_positions)
            self._anim_step = 0
            self._anim_timer.start(20)

        self.update()

    # ------------------------------------------------------------------
    # Size policy — keeps the widget square
    # ------------------------------------------------------------------

    # Forces Qt's layout engine to square the widget.
    # prevents the board from being squashed into a rectangle by parent layout.
    def sizeHint(self) -> QSize:
        return QSize(600, 600)

    def minimumSizeHint(self) -> QSize:
        return QSize(300, 300)

    # ------------------------------------------------------------------
    # Coordinate helpers
    # ------------------------------------------------------------------

    def _unit(self) -> float:
        """Return the size of one cell+gap unit at current scale."""
        return (self.CELL_SIZE + self.WALL_GAP) * self._scale

    def _cell_rect(self, row: int, col: int) -> QRectF:
        """Return the pixel rectangle for grid cell (row, col)."""
        unit = self._unit()
        # CHANGE: Centre the board inside the widget by computing an offset
        board_px = 2 * self.PADDING * self._scale + 9 * self.CELL_SIZE * self._scale + 8 * self.WALL_GAP * self._scale
        offset_x = max(0, (self.width() - board_px) / 2)
        offset_y = max(0, (self.height() - board_px) / 2)
        x = offset_x + self.PADDING * self._scale + col * unit
        y = offset_y + self.PADDING * self._scale + row * unit
        return QRectF(x, y, self.CELL_SIZE * self._scale, self.CELL_SIZE * self._scale)

    def _h_wall_rect(self, r: int, c: int) -> QRectF:
        """Return the pixel rect for the horizontal wall slot at (r, c)."""
        unit = self._unit()
        board_px = 2 * self.PADDING * self._scale + 9 * self.CELL_SIZE * self._scale + 8 * self.WALL_GAP * self._scale
        offset_x = max(0, (self.width() - board_px) / 2)
        offset_y = max(0, (self.height() - board_px) / 2)
        x = offset_x + self.PADDING * self._scale + c * unit
        y = offset_y + self.PADDING * self._scale + r * unit + self.CELL_SIZE * self._scale
        w = 2 * self.CELL_SIZE * self._scale + self.WALL_GAP * self._scale
        return QRectF(x, y, w, self.WALL_GAP * self._scale)

    def _v_wall_rect(self, r: int, c: int) -> QRectF:
        """Return the pixel rect for the vertical wall slot at (r, c)."""
        unit = self._unit()
        board_px = 2 * self.PADDING * self._scale + 9 * self.CELL_SIZE * self._scale + 8 * self.WALL_GAP * self._scale
        offset_x = max(0, (self.width() - board_px) / 2)
        offset_y = max(0, (self.height() - board_px) / 2)
        x = offset_x + self.PADDING * self._scale + c * unit + self.CELL_SIZE * self._scale
        y = offset_y + self.PADDING * self._scale + r * unit
        h = 2 * self.CELL_SIZE * self._scale + self.WALL_GAP * self._scale
        return QRectF(x, y, self.WALL_GAP * self._scale, h)

    def _pawn_center(self, row_f: float, col_f: float) -> tuple[float, float]:
        """Return the pixel centre-point for a pawn at float (row, col)."""
        r = self._cell_rect(int(row_f), int(col_f))
        row_frac = row_f - int(row_f)
        col_frac = col_f - int(col_f)
        cx = r.x() + r.width() / 2 + col_frac * self._unit()
        cy = r.y() + r.height() / 2 + row_frac * self._unit()
        return (cx, cy)

    # ------------------------------------------------------------------
    # Hit testing
    # ------------------------------------------------------------------

    def _hit_test(self, pos: QPoint) -> _BoardElem:
        """
        Determine which board element (cell, wall slot, etc.) is under the
        given pixel position supporting center offset.

        Parameters
        ----------
        pos : QPoint
            Mouse position in widget-local coordinates.

        Returns
        -------
        _BoardElem
            Describes what is at that position.
        """
        unit = self._unit()
        board_px = 2 * self.PADDING * self._scale + 9 * self.CELL_SIZE * self._scale + 8 * self.WALL_GAP * self._scale
        offset_x = max(0, (self.width() - board_px) / 2)
        offset_y = max(0, (self.height() - board_px) / 2)

        px = pos.x() - offset_x - self.PADDING * self._scale
        py = pos.y() - offset_y - self.PADDING * self._scale

        if px < 0 or py < 0:
            return _BoardElem(_ElemKind.OUTSIDE)

        col_unit  = int(px // unit)
        row_unit  = int(py // unit)
        col_frac  = px % unit   # offset within the column unit
        row_frac  = py % unit   # offset within the row unit

        in_cell_col = col_frac < self.CELL_SIZE * self._scale
        in_cell_row = row_frac < self.CELL_SIZE * self._scale

        # Guard maximum bounds
        col_unit = min(col_unit, 8)
        row_unit = min(row_unit, 8)

        if in_cell_row and in_cell_col:
            # Plain cell
            if 0 <= row_unit <= 8 and 0 <= col_unit <= 8:
                return _BoardElem(_ElemKind.CELL, row=row_unit, col=col_unit)

        elif not in_cell_row and in_cell_col:
            # Horizontal wall gap — between rows row_unit and row_unit+1
            # at cell column col_unit
            wr = row_unit   # wall r ∈ [0,7]
            wc = col_unit   # start column for the wall
            if 0 <= wr <= 7 and 0 <= wc <= 7:
                return _BoardElem(
                    _ElemKind.H_WALL_SLOT,
                    wall_r=wr, wall_c=wc,
                    orientation=WallOrientation.HORIZONTAL,
                )

        elif in_cell_row and not in_cell_col:
            # Vertical wall gap — between cols col_unit and col_unit+1
            # at cell row row_unit
            wr = row_unit
            wc = col_unit
            if 0 <= wr <= 7 and 0 <= wc <= 7:
                return _BoardElem(
                    _ElemKind.V_WALL_SLOT,
                    wall_r=wr, wall_c=wc,
                    orientation=WallOrientation.VERTICAL,
                )

        return _BoardElem(_ElemKind.OUTSIDE)

    # ------------------------------------------------------------------
    # Mouse event handlers
    # ------------------------------------------------------------------

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Update hover / wall-preview state on mouse movement."""
        elem = self._hit_test(event.position().toPoint())
        self._hover_elem = elem

        if elem.kind in (_ElemKind.H_WALL_SLOT, _ElemKind.V_WALL_SLOT):
            self._wall_preview = elem
            if elem.orientation is WallOrientation.HORIZONTAL:
                self.setToolTip("Place horizontal wall here")
            else:
                self.setToolTip("Place vertical wall here")
        else:
            self._wall_preview = None
            if elem.kind is _ElemKind.CELL:
                self.setToolTip(f"Cell ({elem.row}, {elem.col})")
            else:
                self.setToolTip("")

        self.update()

    def leaveEvent(self, event) -> None:
        """Clear hover state when the mouse leaves the widget."""
        self._hover_elem   = None
        self._wall_preview = None
        self.setToolTip("")
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """
        Dispatch left-click events to the appropriate signal:
          • Cell   → cell_clicked(row, col)
          • Wall slot → wall_clicked(r, c, orientation)
        """
        if event.button() != Qt.MouseButton.LeftButton:
            return

        elem = self._hit_test(event.position().toPoint())

        if elem.kind == _ElemKind.CELL:
            self.cell_clicked.emit(elem.row, elem.col)

        elif elem.kind in (_ElemKind.H_WALL_SLOT, _ElemKind.V_WALL_SLOT):
            self.wall_clicked.emit(
                elem.wall_r, elem.wall_c, elem.orientation
            )

    # ------------------------------------------------------------------
    # Responsive scaling
    # ------------------------------------------------------------------

    def resizeEvent(self, event) -> None:
        """Recalculate scaling factor based on the smallest widget dimension."""
        base_size = 2 * self.PADDING + 9 * self.CELL_SIZE + 8 * self.WALL_GAP
        side = min(self.width(), self.height())
        self._scale = max(0.1, side / base_size)
        super().resizeEvent(event)

  # ------------------------------------------------------------------
  # Painting
  # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:
        """Render cells, wall slots, placed walls, active highlights, and animated pawns."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw outer board container background
        board_px = 2 * self.PADDING * self._scale + 9 * self.CELL_SIZE * self._scale + 8 * self.WALL_GAP * self._scale
        offset_x = max(0, (self.width() - board_px) / 2)
        offset_y = max(0, (self.height() - board_px) / 2)

        board_rect = QRectF(offset_x, offset_y, board_px, board_px)
        painter.setPen(QPen(QColor(COLORS["outline-variant"]), 1))
        painter.setBrush(QBrush(QColor(COLORS["surface-container-lowest"])))
        painter.drawRoundedRect(board_rect, 12 * self._scale, 12 * self._scale)

        # Draw 9x9 grid of cells
        for r in range(9):
            for c in range(9):
                rect = self._cell_rect(r, c)
                is_valid = (r, c) in self.valid_moves


                if is_valid:
                    painter.setBrush(QBrush(QColor(COLORS["primary-fixed-dim"])))
                    painter.setPen(QPen(QColor(COLORS["primary"]), 1.5))
                else:
                    painter.setBrush(QBrush(QColor(COLORS["surface-container-low"])))
                    painter.setPen(QPen(QColor(COLORS["outline-variant"]), 1))

                painter.drawRoundedRect(rect, 4 * self._scale, 4 * self._scale)

            # Draw placed horizontal walls
        for (r, c) in self.h_walls:
            rect = self._h_wall_rect(r, c)
            owner = self.h_wall_owners.get((r, c), 0)
            color_hex = COLORS["primary-fixed"] if owner == 0 else COLORS["secondary"]
            painter.setBrush(QBrush(QColor(color_hex)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect, 2 * self._scale, 2 * self._scale)

        # Draw placed vertical walls
        for (r, c) in self.v_walls:
            rect = self._v_wall_rect(r, c)
            owner = self.v_wall_owners.get((r, c), 0)
            color_hex = COLORS["primary-fixed"] if owner == 0 else COLORS["secondary"]
            painter.setBrush(QBrush(QColor(color_hex)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect, 2 * self._scale, 2 * self._scale)

        # Draw pulsing wall preview under hover
        if self._wall_preview is not None:
            r, c = self._wall_preview.wall_r, self._wall_preview.wall_c
            orient = self._wall_preview.orientation
            rect = self._h_wall_rect(r, c) if orient == WallOrientation.HORIZONTAL else self._v_wall_rect(r, c)

            preview_color = QColor(COLORS["secondary"])
            preview_color.setAlpha(self._preview_alpha)
            painter.setBrush(QBrush(preview_color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect, 2 * self._scale, 2 * self._scale)

        # Draw pawns using interpolated animated coordinates
        for idx, pos in enumerate(self._display_positions):
            cx, cy = self._pawn_center(pos[0], pos[1])
            rad = (self.CELL_SIZE * self._scale / 2) * self.PAWN_RATIO
            pawn_color = COLORS["primary"] if idx == 0 else COLORS["secondary"]

            # Radial glow around the active/selected pawn
            if self.selected_pawn == idx:
                glow_grad = QRadialGradient(cx, cy, rad * 2)
                glow_color = QColor(pawn_color)
                glow_color.setAlpha(80)
                glow_grad.setColorAt(0, glow_color)
                glow_grad.setColorAt(1, Qt.GlobalColor.transparent)
                painter.setBrush(QBrush(glow_grad))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QPointF(cx, cy), rad * 2, rad * 2)

            painter.setBrush(QBrush(QColor(pawn_color)))
            painter.setPen(QPen(QColor(COLORS["background"]), 1.5))
            painter.drawEllipse(QPointF(cx, cy), rad, rad)

            # Draw ♟ icon inside the circular pawn token
            painter.setPen(QPen(QColor(COLORS["background"]) if idx == 0 else QColor(COLORS["on-secondary"])))
            pawn_font = font("headline-md")
            pawn_font.setPointSize(int(14 * self._scale))
            painter.setFont(pawn_font)
            painter.drawText(
                    QRectF(cx - rad, cy - rad, rad * 2, rad * 2),
                    Qt.AlignmentFlag.AlignCenter,
                    "♟"
            )

        painter.end()

"""
models/wall.py
==============
Wall data model for the Quoridor game.

A wall in Quoridor spans exactly TWO cell-widths along one axis and sits in
the gap between two adjacent rows (horizontal) or two adjacent columns
(vertical). The position (r, c) always refers to the *start* (top-left) of
the wall's extent.

Coordinate conventions:
  • Horizontal wall at (r, c): occupies the horizontal gap below row r,
    spanning cell-columns c and c+1.  Blocks south movement at cols c & c+1.
    Valid range:  r ∈ [0, 7],  c ∈ [0, 7].

  • Vertical wall at (r, c): occupies the vertical gap to the right of col c,
    spanning cell-rows r and r+1.  Blocks east movement at rows r & r+1.
    Valid range:  r ∈ [0, 7],  c ∈ [0, 7].
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class WallOrientation(Enum):
    """Direction a wall is oriented on the board."""
    HORIZONTAL = auto()   # blocks north-south passage
    VERTICAL   = auto()   # blocks east-west passage


@dataclass(frozen=True)
class Wall:
    """
    Immutable record of a single wall placement.

    Attributes
    ----------
    row : int
        Zero-based row index of the wall's start position.
    col : int
        Zero-based column index of the wall's start position.
    orientation : WallOrientation
        Whether the wall is horizontal (blocks vertical movement) or
        vertical (blocks horizontal movement).
    owner : int
        Index of the player (0 or 1) who placed the wall.
    """

    row         : int
    col         : int
    orientation : WallOrientation
    owner       : int

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def is_horizontal(self) -> bool:
        """Return True if this wall is oriented horizontally."""
        return self.orientation is WallOrientation.HORIZONTAL

    def is_vertical(self) -> bool:
        """Return True if this wall is oriented vertically."""
        return self.orientation is WallOrientation.VERTICAL

    def cells_blocked_south(self) -> list[tuple[int, int]]:
        """
        Return the (row, col) pairs whose southward passage this wall blocks.

        Only meaningful for HORIZONTAL walls.

        Returns
        -------
        list[tuple[int, int]]
            Two cell positions: (self.row, self.col) and (self.row, self.col+1).
        """
        if not self.is_horizontal():
            return []
        return [(self.row, self.col), (self.row, self.col + 1)]

    def cells_blocked_east(self) -> list[tuple[int, int]]:
        """
        Return the (row, col) pairs whose eastward passage this wall blocks.

        Only meaningful for VERTICAL walls.

        Returns
        -------
        list[tuple[int, int]]
            Two cell positions: (self.row, self.col) and (self.row+1, self.col).
        """
        if not self.is_vertical():
            return []
        return [(self.row, self.col), (self.row + 1, self.col)]

    def __repr__(self) -> str:
        tag = "H" if self.is_horizontal() else "V"
        return f"Wall({tag}, r={self.row}, c={self.col}, owner={self.owner})"
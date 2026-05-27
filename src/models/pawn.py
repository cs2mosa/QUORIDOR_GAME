"""
models/pawn.py
==============
Pawn data model for the Quoridor game.

Each player owns exactly one pawn.  The pawn's position is expressed in
zero-based (row, col) coordinates on the 9×9 board.

Player goal rows:
  • Player 0 starts at (8, 4) and must reach row 0.
  • Player 1 starts at (0, 4) and must reach row 8.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# Goal rows indexed by player index
PLAYER_START_ROWS : dict[int, int] = {0: 8, 1: 0}
PLAYER_GOAL_ROWS  : dict[int, int] = {0: 0, 1: 8}
PLAYER_START_COLS : dict[int, int] = {0: 4, 1: 4}


@dataclass
class Pawn:
    """
    Mutable record representing one player's pawn on the board.

    Attributes
    ----------
    player_index : int
        0 for Player 1, 1 for Player 2.
    row : int
        Current zero-based row on the 9×9 board.
    col : int
        Current zero-based column on the 9×9 board.
    """

    player_index : int
    row          : int = field(init=False)
    col          : int = field(init=False)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def __post_init__(self) -> None:
        """Set pawn to its canonical starting position."""
        self.reset()

    def reset(self) -> None:
        """
        Return the pawn to its starting square for the current player.

        Player 0 → bottom-centre (row 8, col 4).
        Player 1 → top-centre    (row 0, col 4).
        """
        self.row = PLAYER_START_ROWS[self.player_index]
        self.col = PLAYER_START_COLS[self.player_index]

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def position(self) -> tuple[int, int]:
        """Return current (row, col) position as a tuple."""
        return (self.row, self.col)

    @property
    def goal_row(self) -> int:
        """Return the target row this pawn must reach to win."""
        return PLAYER_GOAL_ROWS[self.player_index]

    def has_reached_goal(self) -> bool:
        """Return True if the pawn is on its goal row."""
        return self.row == self.goal_row

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def move_to(self, row: int, col: int) -> None:
        """
        Teleport the pawn to the given square.

        Parameters
        ----------
        row : int
            Destination row (0-8).
        col : int
            Destination column (0-8).

        Raises
        ------
        ValueError
            If the destination is outside the 9×9 grid.
        """
        if not (0 <= row <= 8 and 0 <= col <= 8):
            raise ValueError(f"Position ({row}, {col}) is outside the 9×9 board.")
        self.row = row
        self.col = col

    def __repr__(self) -> str:
        return f"Pawn(player={self.player_index}, pos=({self.row},{self.col}))"
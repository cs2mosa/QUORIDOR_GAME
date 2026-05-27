"""
models/board.py
===============
Core 9×9 Board model: owns the canonical wall state and exposes methods for:
  • querying passage between adjacent cells (wall awareness)
  • validating and committing wall placements
  • enumerating legal pawn moves (including over-jumps and diagonal sidesteps)

All coordinate pairs use zero-based (row, col) on a 9×9 grid.

Wall storage
------------
Walls are stored in two flat Python sets for O(1) lookup:
  • ``h_walls``: set of (r, c) pairs where a horizontal wall starts.
  • ``v_walls``: set of (r, c) pairs where a vertical wall starts.

See models/wall.py for the full coordinate convention.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from models.wall import Wall, WallOrientation
from models.pathfinder import Pathfinder

if TYPE_CHECKING:
    from models.pawn import Pawn


# Compass delta helpers ─────────────────────────────────────────────────────
_DELTA: dict[str, tuple[int, int]] = {
    "N": (-1,  0),
    "S": ( 1,  0),
    "E": ( 0,  1),
    "W": ( 0, -1),
}


class Board:
    """
    Encapsulates all state related to the physical board surface:
    placed walls and the grid itself.

    The Board does NOT own pawn positions directly; those live in
    :class:`~models.game_state.GameState`.  Pawn positions are passed in
    by reference wherever needed (e.g., wall-validity checks).

    Attributes
    ----------
    h_walls : set[tuple[int, int]]
        Set of (r, c) positions of placed horizontal walls.
    v_walls : set[tuple[int, int]]
        Set of (r, c) positions of placed vertical walls.
    """

    BOARD_SIZE: int = 9
    MAX_WALL_COORD: int = 7   # walls only span 0-7 (they cover 2 cells)

    # ------------------------------------------------------------------
    # Construction / Reset
    # ------------------------------------------------------------------

    def __init__(self) -> None:
        """Create a fresh, empty board (no walls placed)."""
        self.h_walls: set[tuple[int, int]] = set()
        self.v_walls: set[tuple[int, int]] = set()
        self.h_walls_owners: dict[tuple[int, int], int] = {}
        self.v_walls_owners: dict[tuple[int, int], int] = {}

    def reset(self) -> None:
        """Clear all walls from the board."""
        self.h_walls.clear()
        self.v_walls.clear()
        self.h_walls_owners.clear()
        self.v_walls_owners.clear()

    def clone(self) -> "Board":
        """Return a deep copy of this board (used by AI lookahead)."""
        new = Board()
        new.h_walls = self.h_walls.copy()
        new.v_walls = self.v_walls.copy()
        new.h_walls_owners = self.h_walls_owners.copy()
        new.v_walls_owners = self.v_walls_owners.copy()
        return new

    # ------------------------------------------------------------------
    # Wall-passage queries
    # ------------------------------------------------------------------

    def can_move_between(self, r1: int, c1: int, r2: int, c2: int) -> bool:
        """
        Return True if a pawn at (r1, c1) can step directly to (r2, c2)
        — i.e., the passage is not blocked by any wall.

        Requires that (r1,c1) and (r2,c2) are orthogonally adjacent.

        Parameters
        ----------
        r1, c1 : int
            Source cell.
        r2, c2 : int
            Destination cell (must be one step away).

        Returns
        -------
        bool
            False if a wall occupies the edge between the two cells.

        Raises
        ------
        ValueError
            If the cells are not orthogonally adjacent.
        """
        dr, dc = r2 - r1, c2 - c1

        if (abs(dr) + abs(dc)) != 1:
            raise ValueError(f"Cells ({r1},{c1}) and ({r2},{c2}) are not adjacent.")

        # Moving South (dr=+1): blocked by h_wall at (r1, c1) or (r1, c1-1)
        if dr == 1:
            return not (
                (r1, c1) in self.h_walls or
                (c1 > 0 and (r1, c1 - 1) in self.h_walls)
            )

        # Moving North (dr=-1): same wall set as South (wall blocks both ways)
        if dr == -1:
            return not (
                (r2, c2) in self.h_walls or
                (c2 > 0 and (r2, c2 - 1) in self.h_walls)
            )

        # Moving East (dc=+1): blocked by v_wall at (r1, c1) or (r1-1, c1)
        if dc == 1:
            return not (
                (r1, c1) in self.v_walls or
                (r1 > 0 and (r1 - 1, c1) in self.v_walls)
            )

        # Moving West (dc=-1): blocked by v_wall at (r1, c2) or (r1-1, c2)
        if dc == -1:
            return not (
                (r1, c2) in self.v_walls or
                (r1 > 0 and (r1 - 1, c2) in self.v_walls)
            )

        return True  # unreachable but satisfies type-checkers

    # ------------------------------------------------------------------
    # Legal pawn moves
    # ------------------------------------------------------------------

    def legal_pawn_moves(
        self,
        row: int,
        col: int,
        opponent_row: int,
        opponent_col: int,
    ) -> list[tuple[int, int]]:
        """
        Return all legally reachable squares for a pawn at (row, col),
        given the opponent pawn is at (opponent_row, opponent_col).

        Implements the full Quoridor movement ruleset:
          1. Normal orthogonal step (one square, not into a wall).
          2. Jump over adjacent opponent (if no wall behind opponent).
          3. Diagonal sidestep (if jump is blocked by a wall or board edge).

        Parameters
        ----------
        row, col : int
            Current pawn position.
        opponent_row, opponent_col : int
            Opponent pawn position.

        Returns
        -------
        list[tuple[int, int]]
            Sorted list of valid (row, col) destination squares.
        """
        moves: list[tuple[int, int]] = []

        # The four cardinal directions
        for dname, (dr, dc) in _DELTA.items():
            nr, nc = row + dr, col + dc

            # Out of bounds → skip
            if not (0 <= nr <= 8 and 0 <= nc <= 8):
                continue

            # Wall in the way → skip normal step
            if not self.can_move_between(row, col, nr, nc):
                continue

            # Opponent occupies the adjacent square
            if (nr, nc) == (opponent_row, opponent_col):
                jr, jc = nr + dr, nc + dc  # straight jump target

                # Straight jump: destination in-bounds and not wall-blocked
                if (
                    0 <= jr <= 8 and 0 <= jc <= 8 and
                    self.can_move_between(nr, nc, jr, jc)
                ):
                    moves.append((jr, jc))
                else:
                    # Diagonal sidestep: try perpendicular squares
                    for sdr, sdc in self._perpendicular(dr, dc):
                        sr, sc = nr + sdr, nc + sdc
                        if (
                            0 <= sr <= 8 and 0 <= sc <= 8 and
                            self.can_move_between(nr, nc, sr, sc)
                        ):
                            moves.append((sr, sc))
            else:
                # Normal step
                moves.append((nr, nc))

        return sorted(set(moves))

    # ------------------------------------------------------------------
    # Wall validation and placement
    # ------------------------------------------------------------------

    def is_wall_placement_valid(
        self,
        r: int,
        c: int,
        orientation: WallOrientation,
        pawns: list["Pawn"],
    ) -> bool:
        """
        Return True if placing a wall at (r, c) with the given orientation
        is legal given current board state and both pawn positions.

        Checks:
          1. Position in-bounds (0-7 on both axes).
          2. No duplicate or directly overlapping wall.
          3. No crossing wall at the same grid intersection.
          4. After placement both pawns still have a path to their goal row.

        Parameters
        ----------
        r, c : int
            Wall start position.
        orientation : WallOrientation
            HORIZONTAL or VERTICAL.
        pawns : list[Pawn]
            Both player pawns (order: player-0, player-1).

        Returns
        -------
        bool
            True only if all validity conditions are met.
        """
        # --- Range check ---
        if not (0 <= r <= self.MAX_WALL_COORD and 0 <= c <= self.MAX_WALL_COORD):
            return False

        if orientation is WallOrientation.HORIZONTAL:
            return self._is_h_wall_valid(r, c, pawns)
        else:
            return self._is_v_wall_valid(r, c, pawns)

    def place_wall(
        self, r: int, c: int, orientation: WallOrientation, owner: int
    ) -> Wall:
        """
        Commit a wall to the board and return the created Wall object.

        Callers MUST call ``is_wall_placement_valid`` first; this method
        performs no additional validation.

        Parameters
        ----------
        r, c : int
            Wall start position.
        orientation : WallOrientation
            HORIZONTAL or VERTICAL.
        owner : int
            Index of the player placing the wall.

        Returns
        -------
        Wall
            The newly created wall record.
        """
        wall = Wall(row=r, col=c, orientation=orientation, owner=owner)
        if orientation is WallOrientation.HORIZONTAL:
            self.h_walls.add((r, c))
            self.h_walls_owners[(r, c)] = owner
        else:
            self.v_walls.add((r, c))
            self.v_walls_owners[(r, c)] = owner
        return wall

    def remove_wall(self, r: int, c: int, orientation: WallOrientation) -> None:
        """
        Remove a previously placed wall (used by the Undo command).

        Parameters
        ----------
        r, c : int
            Wall start position.
        orientation : WallOrientation
            HORIZONTAL or VERTICAL.
        """
        if orientation is WallOrientation.HORIZONTAL:
            self.h_walls.discard((r, c))
            self.h_walls_owners.pop((r, c), None)
        else:
            self.v_walls.discard((r, c))
            self.v_walls_owners.pop((r, c), None)

    # ------------------------------------------------------------------
    # Internal validation helpers
    # ------------------------------------------------------------------

    def _is_h_wall_valid(
        self, r: int, c: int, pawns: list["Pawn"]
    ) -> bool:
        """Validate horizontal wall at (r, c) for conflicts and path integrity."""
        # Duplicate
        if (r, c) in self.h_walls:
            return False
        # Overlap with neighbour walls on the same row
        if (c > 0 and (r, c - 1) in self.h_walls) or \
           (c < self.MAX_WALL_COORD and (r, c + 1) in self.h_walls):
            return False
        # Crossing vertical wall at the same intersection
        if (r, c) in self.v_walls:
            return False

        # Tentatively place and check path integrity
        self.h_walls.add((r, c))
        paths_ok = all(
            Pathfinder.has_path(self, p.row, p.col, p.goal_row) for p in pawns
        )
        self.h_walls.discard((r, c))
        return paths_ok

    def _is_v_wall_valid(
        self, r: int, c: int, pawns: list["Pawn"]
    ) -> bool:
        """Validate vertical wall at (r, c) for conflicts and path integrity."""
        # Duplicate
        if (r, c) in self.v_walls:
            return False
        # Overlap with neighbour walls in the same column
        if (r > 0 and (r - 1, c) in self.v_walls) or \
           (r < self.MAX_WALL_COORD and (r + 1, c) in self.v_walls):
            return False
        # Crossing horizontal wall
        if (r, c) in self.h_walls:
            return False

        # Tentatively place and check path integrity
        self.v_walls.add((r, c))
        paths_ok = all(
            Pathfinder.has_path(self, p.row, p.col, p.goal_row) for p in pawns
        )
        self.v_walls.discard((r, c))
        return paths_ok

    @staticmethod
    def _perpendicular(dr: int, dc: int) -> list[tuple[int, int]]:
        """Return the two perpendicular direction deltas relative to (dr, dc)."""
        if dr != 0:
            return [(0, -1), (0, 1)]   # moving vertically → sidestep horizontally
        return [(-1, 0), (1, 0)]       # moving horizontally → sidestep vertically

    # ------------------------------------------------------------------
    # Serialisation (for save/load bonus feature)
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialise board state to a plain dict for JSON persistence."""
        return {
            "h_walls": list(self.h_walls),
            "v_walls": list(self.v_walls),
            "h_walls_owners": {f"{r}, {c}": o for (r, c), o in self.h_walls_owners.items()},
            "v_walls_owners": {f"{r}, {c}": o for (r, c), o in self.v_walls_owners.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Board":
        """Restore a Board from its serialised dict representation."""
        board = cls()
        board.h_walls = {
            tuple(p) for p in data.get("h_walls", [])
        }
        board.v_walls = {
            tuple(p) for p in data.get("v_walls", [])
        }
        board.h_walls_owners = {
            tuple(int (x) for x in k.split(",")): v
            for k, v in data.get("h_walls_owners", {}).items()
        }
        board.v_walls_owners = {
            tuple(int(x) for x in k.split(",")): v
            for k, v in data.get("v_walls_owners", {}).items()
        }
        return board
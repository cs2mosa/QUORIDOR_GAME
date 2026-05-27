"""
models/pathfinder.py
====================
BFS-based pathfinder used to:
  1. Validate that a proposed wall placement does NOT completely block any
     player's path to their goal row (Quoridor hard rule).
  2. Measure the shortest path length for each player (used by the AI
     heuristic function).
  3. Enumerate all reachable squares from a given position (used for move
     highlighting in the UI).

All graph operations operate on the abstract board state (wall sets) and do
**not** import any Qt types, keeping the model layer free of UI dependencies.
"""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Avoid circular import; Board is only used as a type hint here.
    from models.board import Board

# ── BFS cache ───────────────────────────────────────────────────────────────
_MAX_CACHE = 8192
_bfs_cache: dict[tuple, int] = {}


def _bfs_key(board: "Board", sr: int, sc: int, gr: int) -> tuple:
    return (frozenset(board.h_walls), frozenset(board.v_walls), sr, sc, gr)


def _bfs_get(board: "Board", sr: int, sc: int, gr: int) -> int | None:
    return _bfs_cache.get(_bfs_key(board, sr, sc, gr), None)


def _bfs_set(board: "Board", sr: int, sc: int, gr: int, val: int) -> None:
    key = _bfs_key(board, sr, sc, gr)
    if len(_bfs_cache) >= _MAX_CACHE:
        items = list(_bfs_cache.items())
        _bfs_cache.clear()
        for k, v in items[_MAX_CACHE // 2 :]:
            _bfs_cache[k] = v
    _bfs_cache[key] = val

class Pathfinder:
    """
    Stateless BFS utility operating on a :class:`~models.board.Board` snapshot.

    Methods are static so they can be called without instantiation, which
    keeps the API clean for one-off validation calls in the controller layer.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def has_path(board: "Board", start_row: int, start_col: int, goal_row: int) -> bool:
        """
        Return True if there exists at least one path from (start_row,
        start_col) to *any* cell on goal_row, respecting the current walls.

        Uses plain BFS on the 9×9 grid; complexity is O(81) in the worst case.

        Parameters
        ----------
        board : Board
            Current board state (provides wall-awareness via ``can_move``).
        start_row : int
            Starting row index (0-8).
        start_col : int
            Starting column index (0-8).
        goal_row : int
            The row the pawn needs to reach (0 or 8 for a 2-player game).

        Returns
        -------
        bool
            True if at least one route exists.
        """
        if start_row == goal_row:
            return True
        cached = _bfs_get(board, start_row, start_col, goal_row)
        if cached is not None:
            return cached != -1
        length = Pathfinder.shortest_path_length(board, start_row, start_col, goal_row)
        return length != -1

    @staticmethod
    def shortest_path_length(
        board: "Board", start_row: int, start_col: int, goal_row: int
    ) -> int:
        """
        Return the number of moves required to reach goal_row from
        (start_row, start_col), or -1 if no path exists.

        Used by the AI evaluation function to score board positions.

        Parameters
        ----------
        board : Board
            Current board state.
        start_row, start_col : int
            Starting position.
        goal_row : int
            Target row.

        Returns
        -------
        int
            Minimum BFS depth to reach goal_row, or -1 if unreachable.
        """
        if start_row == goal_row:
            return 0
        cached = _bfs_get(board, start_row, start_col, goal_row)
        if cached is not None:
            return cached

        visited: set[tuple[int, int]] = {(start_row, start_col)}
        # BFS queue stores (row, col, distance)
        queue: deque[tuple[int, int, int]] = deque([(start_row, start_col, 0)])

        while queue:
            row, col, dist = queue.popleft()

            for nrow, ncol in Pathfinder._orthogonal_neighbours(board, row, col):
                if (nrow, ncol) not in visited:
                    visited.add((nrow, ncol))
                    if nrow == goal_row:
                        _bfs_set(board, start_row, start_col, goal_row, dist + 1)
                        return dist + 1
                    queue.append((nrow, ncol, dist + 1))

        _bfs_set(board, start_row, start_col, goal_row, -1)
        return -1  # unreachable

    @staticmethod
    def reachable_squares(
        board: "Board", from_row: int, from_col: int, max_steps: int = 1
    ) -> list[tuple[int, int]]:
        """
        Return all squares reachable in exactly *max_steps* moves from the
        given position, respecting walls and jump rules.

        This method is used by the view layer to highlight valid move targets
        when the player selects their pawn.

        Parameters
        ----------
        board : Board
            Current board state.
        from_row, from_col : int
            Current pawn position.
        max_steps : int
            How many moves deep to search (typically 1 for normal moves,
            2 for jump scenarios; the board's ``legal_pawn_moves`` handles
            the exact jump logic so callers usually pass 1 here and let
            Board enumerate jumps separately).

        Returns
        -------
        list[tuple[int, int]]
            Sorted list of (row, col) tuples that are valid destinations.
        """
        visited: set[tuple[int, int]] = {(from_row, from_col)}
        frontier: set[tuple[int, int]] = {(from_row, from_col)}

        for _ in range(max_steps):
            next_frontier: set[tuple[int, int]] = set()
            for row, col in frontier:
                for nrow, ncol in Pathfinder._orthogonal_neighbours(board, row, col):
                    if (nrow, ncol) not in visited:
                        next_frontier.add((nrow, ncol))
            visited |= next_frontier
            frontier = next_frontier

        # Exclude the origin
        result = [(r, c) for r, c in visited if (r, c) != (from_row, from_col)]
        return sorted(result)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _orthogonal_neighbours(
        board: "Board", row: int, col: int
    ) -> list[tuple[int, int]]:
        """
        Return the set of (row, col) squares reachable in one orthogonal
        step from (row, col), applying wall-blocking logic from the board.

        Parameters
        ----------
        board : Board
            Current board (provides can_move_between).
        row, col : int
            Current position.

        Returns
        -------
        list[tuple[int, int]]
            Adjacent squares that are NOT wall-blocked.
        """
        neighbours: list[tuple[int, int]] = []
        # North, South, West, East
        candidates = [
            (row - 1, col),
            (row + 1, col),
            (row, col - 1),
            (row, col + 1),
        ]
        for nrow, ncol in candidates:
            if 0 <= nrow <= 8 and 0 <= ncol <= 8:
                if board.can_move_between(row, col, nrow, ncol):
                    neighbours.append((nrow, ncol))
        return neighbours
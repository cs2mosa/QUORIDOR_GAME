"""
services/ai_engine.py
======================
AI Engine — plug-in service that computes the best move for the AI player.

Three difficulty tiers
-----------------------
Novice   (easy)   — random legal move from a biased pool (mostly advance).
Adept    (medium) — greedy 1-ply: pick the move that minimises opponent
                    shortest-path while maximising own.
Architect (hard)  — Minimax with Alpha-Beta pruning (depth 3), using the
                    path-length differential heuristic.

Design contract
---------------
• The engine is STATELESS between calls — it receives a board snapshot and
  returns a move descriptor dict.
• It never mutates the real GameState; all lookahead uses Board.clone().
• A QThread worker wrapper (AIWorker) is provided so the UI thread never
  blocks while the Architect level thinks.

Move descriptor format
-----------------------
{
    "type": "pawn_move",
    "row": int, "col": int,
}
— or —
{
    "type": "wall",
    "row": int, "col": int,
    "orientation": WallOrientation,
}
"""

from __future__ import annotations

import random
import copy
import time
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal, QRunnable, Slot

from models.board import Board
from models.pawn import Pawn, PLAYER_GOAL_ROWS
from models.wall import WallOrientation
from models.pathfinder import Pathfinder

if TYPE_CHECKING:
    from models.game_state import GameState


# ──────────────────────────────────────────────────────────────────────────────
# Heuristic
# ──────────────────────────────────────────────────────────────────────────────

def _evaluate(
    board          : Board,
    ai_pawn        : Pawn,
    human_pawn     : Pawn,
    ai_player_idx  : int,
    ai_walls       : int = 0,
    human_walls       : int = 0,
) -> float:
    """
    Static evaluation function: higher score is better for the AI.

    Score = (opponent path length) − (AI path length) + gamma * (AI walls - Human walls)

    A larger positive score means the AI is closer to winning (short own
    path) while the opponent is farther (long opponent path).

    Parameters
    ----------
    board : Board
        Current board snapshot.
    ai_pawn, human_pawn : Pawn
        Pawn objects for the two players.
    ai_player_idx : int
        0 or 1 — used to look up goal rows.

    Returns
    -------
    float
        Heuristic score; +∞ for an AI win, −∞ for a human win.
    """

    ai_dist    = Pathfinder.shortest_path_length(
        board, ai_pawn.row, ai_pawn.col, PLAYER_GOAL_ROWS[ai_player_idx]
    )
    human_idx  = 1 - ai_player_idx
    human_dist = Pathfinder.shortest_path_length(
        board, human_pawn.row, human_pawn.col, PLAYER_GOAL_ROWS[human_idx]
    )

    # Unreachable paths (should not happen in valid states)
    if ai_dist == 0 or ai_pawn.row == PLAYER_GOAL_ROWS[ai_player_idx]:
        return float("inf")
    if human_dist == 0 or human_pawn.row == PLAYER_GOAL_ROWS[human_idx]:
        return float("-inf")
    if ai_dist == -1:
        return float("-inf")
    if human_dist == -1:
        return float("inf")

    score = float(human_dist - ai_dist)
    gamma = 0.5
    score += gamma * (ai_walls - human_walls)

    # Protect the goal line by rewarding branching center mobility
    neighbours = len(
        Pathfinder._orthogonal_neighbours(
        board,
        ai_pawn.row,
        ai_pawn.col
        )
    )
    score += 0.1 * neighbours

    return score

# ── Wall blocking score helper ─────────────────────────────────────────────

def _wall_blocking_score(
    board: Board,
    r: int,
    c: int,
    orientation: WallOrientation,
    pawn: Pawn,
    goal_row: int,
) -> int:
    """
    Return the increase in opponent shortest-path length caused by this wall.
    Higher = more blocking.
    """
    original = Pathfinder.shortest_path_length(board, pawn.row, pawn.col, goal_row)
    board.place_wall(r, c, orientation, 0)
    new_dist = Pathfinder.shortest_path_length(board, pawn.row, pawn.col, goal_row)
    board.remove_wall(r, c, orientation)
    if original == -1:
        return 0
    if new_dist == -1:
        return 1000
    return new_dist - original


# ──────────────────────────────────────────────────────────────────────────────
# Move generator (shared by all tiers)
# ──────────────────────────────────────────────────────────────────────────────

def _candidate_walls(
    board: Board, pawns: list[Pawn], walls_remaining: int
) -> list[tuple[int, int, WallOrientation]]:
    """
    Enumerate wall placements worth considering.

    Returns a pruned subset of all 128 possible placements, keeping only
    those that are valid AND meaningfully block a path (i.e., the human's
    BFS distance increases after placement).  Caps at 20 candidates for
    performance.

    Parameters
    ----------
    board : Board
        Current board snapshot.
    pawns : list[Pawn]
        [ai_pawn, human_pawn] in turn order.
    walls_remaining : int
        How many walls the AI still has.

    Returns
    -------
    list[tuple[int, int, WallOrientation]]
        (r, c, orientation) tuples of viable wall placements.
    """
    if walls_remaining <= 0:
        return []

    human_pawn = pawns[1]
    human_goal = PLAYER_GOAL_ROWS[1]

    candidates: list[tuple[int, int, WallOrientation]] = []

    for r in range(8):
        for c in range(8):
            for orient in WallOrientation:
                if board.is_wall_placement_valid(r, c, orient, pawns):
                    candidates.append((r, c, orient))

    # Smart Move Ordering: Sort descending by immediate blocking power
    def sort_key(item: tuple[int, int, WallOrientation]) -> int:
        return _wall_blocking_score(board, item[0], item[1], item[2], human_pawn, human_goal)
    candidates.sort(key=sort_key, reverse=True)
    return candidates[:20]


# ──────────────────────────────────────────────────────────────────────────────
# Tier implementations
# ──────────────────────────────────────────────────────────────────────────────

def _novice_move(state: "GameState", ai_idx: int) -> dict:
    """
    Novice AI: Sensible wanderer that uses pathfinder-based navigation.
    Parameters
    ----------
    state : GameState
        Current game snapshot.
    ai_idx : int
        Index of the AI player (0 or 1).

    Returns
    -------
    dict
        Move descriptor.
    """
    ai_pawn  = state.pawns[ai_idx]
    opp_pawn = state.pawns[1 - ai_idx]
    board = state.board
    goal = PLAYER_GOAL_ROWS[ai_idx]
    walls_left = state.players[ai_idx].walls_remaining

  # 20% chance to place a disruption wall from the sensible candidate pool

    if random.random() < 0.20 and walls_left > 0:
        walls = _candidate_walls(board, state.pawns, walls_left)
        if walls:
            wr, wc, orient = random.choice(walls)
            return {"type": "wall", "row": wr, "col": wc, "orientation": orient}

    moves = board.legal_pawn_moves(
        ai_pawn.row, ai_pawn.col, opp_pawn.row, opp_pawn.col
    )

    if not moves:
        return {"type": "pawn_move", "row": ai_pawn.row, "col": ai_pawn.col}

# Evaluate true pathfinding steps instead of absolute geometric coordinates
    def move_key(m: tuple[int, int]) -> int:
        val = Pathfinder.shortest_path_length(board, m[0], m[1], goal)
        return val if val != -1 else 999

    best = min(moves, key=move_key)
    return {"type": "pawn_move", "row": best[0], "col": best[1]}


def _adept_move(state: "GameState", ai_idx: int) -> dict:
    """
    Adept AI: Greedy 1-ply opportunistic agent with oscillation memory restrictions.
    Picks the single action that maximises _evaluate() immediately.

    Parameters
    ----------
    state : GameState
        Current game snapshot.
    ai_idx : int
        Index of the AI player.

    Returns
    -------
    dict
        Move descriptor.
    """

    ai_pawn  = state.pawns[ai_idx]
    opp_pawn = state.pawns[1 - ai_idx]
    human_idx = 1 - ai_idx
    walls_left = state.players[ai_idx].walls_remaining
    opp_walls = state.players[human_idx].walls_remaining

    best_score : float = float("-inf")
    best_move  : dict  = {"type": "pawn_move", "row": ai_pawn.row, "col": ai_pawn.col}

    board = state.board

    # Track last starting cell to eliminate endless back-and-forth loops
    recent_from = None
    for cmd in reversed(state._history):
        if cmd.get("player") == ai_idx and cmd.get("type") == "pawn_move":
            recent_from = (cmd["from_row"], cmd["from_col"])
            break

    # ── Evaluate pawn moves ──────────────────────────────────────────────
    for (r, c) in board.legal_pawn_moves(
        ai_pawn.row, ai_pawn.col, opp_pawn.row, opp_pawn.col
    ):
        # Clone pawn temporarily
        temp_pawn = Pawn(ai_idx)
        temp_pawn.move_to(r, c)
        score = _evaluate(board, temp_pawn, opp_pawn, ai_idx, ai_walls=walls_left, human_walls=opp_walls)

        if (r, c) == recent_from:
            score -= 10.0  # Heavy oscillation penalty

        if score > best_score:
            best_score = score
            best_move  = {"type": "pawn_move", "row": r, "col": c}

    # ── Evaluate wall placements ─────────────────────────────────────────
    for (wr, wc, orient) in _candidate_walls(board, state.pawns, walls_left):
        original_human_dist = Pathfinder.shortest_path_length(
            board, opp_pawn.row, opp_pawn.col, PLAYER_GOAL_ROWS[human_idx]
        )
        board.place_wall(wr, wc, orient, ai_idx)
        new_human_dist = Pathfinder.shortest_path_length(
            board, opp_pawn.row, opp_pawn.col, PLAYER_GOAL_ROWS[human_idx]
        )

        # Prevent panic wall-wasting: wall must delay human by at least 2 steps
        is_significant = (
                    new_human_dist != -1 and original_human_dist != -1 and (new_human_dist - original_human_dist >= 2)
        )


        if is_significant or new_human_dist == -1:
            score = _evaluate(board, ai_pawn, opp_pawn, ai_idx, ai_walls=walls_left - 1, human_walls=opp_walls)

            if score > best_score:
                best_score = score
                best_move = {"type": "wall", "row": wr, "col": wc, "orientation": orient}
        board.remove_wall(wr, wc, orient)

    return best_move


def _minimax(
    board          : Board,
    ai_pawn        : Pawn,
    human_pawn     : Pawn,
    ai_walls       : int,
    human_walls    : int,
    depth          : int,
    alpha          : float,
    beta           : float,
    maximising     : bool,
    ai_idx         : int,
) -> float:
    """
    Minimax with Alpha-Beta pruning supporting wall-counting states.

    Parameters
    ----------
    board : Board
        Cloned board snapshot (mutations are safe).
    ai_pawn, human_pawn : Pawn
        Cloned pawn objects for lookahead.
    ai_walls, human_walls : int
        Remaining walls for each player.
    depth : int
        Remaining search depth.
    alpha, beta : float
        Alpha-Beta bounds.
    maximising : bool
        True when it is the AI's turn.
    ai_idx : int
        The AI player index (0 or 1).

    Returns
    -------
    float
        Heuristic score at this node.
    """

    # Terminal / leaf
    if ai_pawn.has_reached_goal():
        return float("inf")
    if human_pawn.has_reached_goal():
        return float("-inf")
    if depth == 0:
        return _evaluate(board, ai_pawn, human_pawn, ai_idx, ai_walls, human_walls)

    if maximising:
        max_val = float("-inf")
        # Pawn moves
        opp = human_pawn
        for (r, c) in board.legal_pawn_moves(ai_pawn.row, ai_pawn.col, opp.row, opp.col):
            new_ai = Pawn(ai_idx)
            new_ai.move_to(r, c)
            val = _minimax(
                board, new_ai, human_pawn,
                ai_walls, human_walls,
                depth - 1, alpha, beta, False, ai_idx,
            )
            max_val = max(max_val, val)
            alpha   = max(alpha, val)
            if beta <= alpha:
                break
        # Wall placements (pruned to top 8 for speed)
        for (wr, wc, orient) in _candidate_walls(board, [ai_pawn, human_pawn], ai_walls)[:8]:
            board.place_wall(wr, wc, orient, ai_idx)
            val = _minimax(
                board, ai_pawn, human_pawn,
                ai_walls - 1, human_walls,
                depth - 1, alpha, beta, False, ai_idx,
            )
            board.remove_wall(wr, wc, orient)
            max_val = max(max_val, val)
            alpha   = max(alpha, val)
            if beta <= alpha:
                break
        return max_val

    else:
        min_val = float("inf")
        h_idx   = 1 - ai_idx
        for (r, c) in board.legal_pawn_moves(
            human_pawn.row, human_pawn.col, ai_pawn.row, ai_pawn.col
        ):
            new_human = Pawn(h_idx)
            new_human.move_to(r, c)
            val = _minimax(
                board, ai_pawn, new_human,
                ai_walls, human_walls,
                depth - 1, alpha, beta, True, ai_idx,
            )
            min_val = min(min_val, val)
            beta    = min(beta, val)
            if beta <= alpha:
                break
        # Human wall placements
        for (wr, wc, orient) in _candidate_walls(board, [human_pawn, ai_pawn], human_walls)[:6]:
            board.place_wall(wr, wc, orient, h_idx)
            val = _minimax(
                board, ai_pawn, human_pawn,
                ai_walls, human_walls - 1,
                depth - 1, alpha, beta, True, ai_idx,
            )
            board.remove_wall(wr, wc, orient)
            min_val = min(min_val, val)
            beta    = min(beta, val)
            if beta <= alpha:
                break
        return min_val


def _architect_move(state: "GameState", ai_idx: int) -> dict:
    """
    Architect AI: Dynamic-depth Minimax optimized with early alpha-beta branch ordering.

    Explores pawn moves and top wall candidates, choosing the action
    that maximises the heuristic at the root.

    Parameters
    ----------
    state : GameState
        Current game snapshot.
    ai_idx : int
        AI player index.

    Returns
    -------
    dict
        Move descriptor.
    """

    ai_pawn    = state.pawns[ai_idx]
    opp_pawn   = state.pawns[1 - ai_idx]
    ai_walls   = state.players[ai_idx].walls_remaining
    opp_walls  = state.players[1 - ai_idx].walls_remaining
    DEPTH      = None

    # Dynamic depth: shift minimax lookahead dynamically for endgames
    total_walls_left = ai_walls + opp_walls

    if total_walls_left <= 2:
        DEPTH = 6
    elif total_walls_left <= 4:
        DEPTH = 4
    else:
        DEPTH = 3

    best_score : float = float("-inf")
    best_move  : dict  = {"type": "pawn_move", "row": ai_pawn.row, "col": ai_pawn.col}

    board = state.board.clone()

    # Root pawn moves
    for (r, c) in board.legal_pawn_moves(
        ai_pawn.row, ai_pawn.col, opp_pawn.row, opp_pawn.col
    ):
        new_ai = Pawn(ai_idx)
        new_ai.move_to(r, c)
        val = _minimax(
            board, new_ai, _clone_pawn(opp_pawn),
            ai_walls, opp_walls,
            DEPTH - 1, float("-inf"), float("inf"), False, ai_idx,
        )
        if val > best_score:
            best_score = val
            best_move  = {"type": "pawn_move", "row": r, "col": c}

    # Root wall placements
    for (wr, wc, orient) in _candidate_walls(board, state.pawns, ai_walls)[:12]:
        board.place_wall(wr, wc, orient, ai_idx)
        val = _minimax(
            board, _clone_pawn(ai_pawn), _clone_pawn(opp_pawn),
            ai_walls - 1, opp_walls,
            DEPTH - 1, float("-inf"), float("inf"), False, ai_idx,
        )
        board.remove_wall(wr, wc, orient)
        if val > best_score:
            best_score = val
            best_move  = {"type": "wall", "row": wr, "col": wc, "orientation": orient}

    return best_move


def _clone_pawn(p: Pawn) -> Pawn:
    """Return a copy of the pawn at its current position."""
    new = Pawn(p.player_index)
    new.move_to(p.row, p.col)
    return new


# ──────────────────────────────────────────────────────────────────────────────
# Public facade
# ──────────────────────────────────────────────────────────────────────────────

def compute_move(state: "GameState", ai_idx: int, difficulty: str) -> dict:
    """
    Compute the AI's next move.

    Parameters
    ----------
    state : GameState
        Snapshot of the current game (will NOT be mutated).
    ai_idx : int
        Which player slot the AI occupies (0 or 1).
    difficulty : str
        One of ``"easy"``, ``"medium"``, ``"hard"``.

    Returns
    -------
    dict
        Move descriptor: ``{"type": "pawn_move", "row": r, "col": c}``
        or ``{"type": "wall", "row": r, "col": c, "orientation": WallOrientation}``.
    """
    if difficulty == "easy":
        return _novice_move(state, ai_idx)
    elif difficulty == "hard":
        return _architect_move(state, ai_idx)
    else:
        return _adept_move(state, ai_idx)


# ──────────────────────────────────────────────────────────────────────────────
# Async QRunnable wrapper (keeps UI thread responsive)
# ──────────────────────────────────────────────────────────────────────────────

class _AIWorkerSignals(QObject):
    """Carrier for the signal emitted when AI computation completes."""
    finished: Signal = Signal(dict)


class AIWorker(QRunnable):
    """
    Runs AI computation off the main thread via Qt's global thread pool.

    Usage
    -----
    ::

        worker = AIWorker(state, ai_idx=1, difficulty="hard")
        worker.signals.finished.connect(controller.on_ai_move_ready)
        QThreadPool.globalInstance().start(worker)
    """

    def __init__(
        self,
        state      : "GameState",
        ai_idx     : int,
        difficulty : str,
        min_think_ms: int = 400
    ) -> None:
        super().__init__()
        # Deep-copy the state so the background thread works on its own data
        self._state      = copy.deepcopy(state)
        self._ai_idx     = ai_idx
        self._difficulty = difficulty
        self.signals     = _AIWorkerSignals()
        self.min_think_ms = min_think_ms

    @Slot()
    def run(self) -> None:
        """Compute the move and emit the result."""
        t0 = time.perf_counter()
        move = compute_move(self._state, self._ai_idx, self._difficulty)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        remaining = self.min_think_ms - elapsed_ms
        if remaining > 0:
            time.sleep(remaining / 1000.0)
        self.signals.finished.emit(move)

"""
models/game_state.py
====================
GameState is the **aggregate root** of the Model layer.  It owns and
orchestrates:
  • The :class:`~models.board.Board` (wall state)
  • Both :class:`~models.pawn.Pawn` objects (positions)
  • Wall inventories (10 walls per player at game start)
  • Turn tracking (whose turn it is)
  • Game-over detection
  • Move history for Undo/Redo (Command pattern)

The GameState is the *only* object that the Controller layer should mutate
directly.  The View layer reads from it but never writes.

Design note — Command pattern
------------------------------
Each reversible action (pawn move, wall placement) is stored as a plain dict
in the ``_history`` stack.  Undoing pops the top command and inverts it.
Redoing replays the command from the ``_redo_stack``.  A new action clears
the redo stack (standard behaviour).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

from models.board import Board
from models.pawn import Pawn
from models.wall import Wall, WallOrientation


class GamePhase(Enum):
    """High-level phase the game is currently in."""
    SETUP    = auto()   # Players haven't started yet
    PLAYING  = auto()   # Active turn-by-turn play
    FINISHED = auto()   # A winner has been decided


@dataclass
class PlayerInfo:
    """
    Lightweight struct holding display-level information about a player.

    Attributes
    ----------
    name : str
        Display name / handler entered on the setup screen.
    is_ai : bool
        Whether this slot is controlled by the AI engine.
    walls_remaining : int
        How many walls this player may still place (starts at 10).
    walls_placed : int
        Count of walls placed so far (for the Victory stats screen).
    turns_taken : int
        Total turns this player has taken (for Victory stats).
    """
    name            : str
    is_ai           : bool = False
    walls_remaining : int  = 10
    walls_placed    : int  = 0
    turns_taken     : int  = 0


class GameState:
    """
    Central mutable state container for a single game session.

    Attributes
    ----------
    board : Board
        The board surface (wall positions).
    pawns : list[Pawn]
        [pawn_player0, pawn_player1].
    players : list[PlayerInfo]
        Display/meta information for each player.
    current_player : int
        Index (0 or 1) of the player whose turn it is.
    phase : GamePhase
        Current lifecycle phase.
    winner : Optional[int]
        Index of the winning player (set when phase == FINISHED), else None.
    total_turns : int
        Running total of all turns taken by both players.
    """

    def __init__(self) -> None:
        """Initialise a blank game state (no players configured)."""
        self.board           : Board               = Board()
        self.pawns           : list[Pawn]          = [Pawn(0), Pawn(1)]
        self.players         : list[PlayerInfo]    = [
            PlayerInfo(name="Player 1"),
            PlayerInfo(name="Player 2"),
        ]
        self.current_player  : int                 = 0
        self.phase           : GamePhase           = GamePhase.SETUP
        self.winner          : Optional[int]       = None
        self.total_turns     : int                 = 0

        # ── Command-pattern stacks ──────────────────────────────────────
        self._history   : list[dict] = []
        self._redo_stack: list[dict] = []

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def configure(
        self,
        player1_name: str,
        player2_name: str,
        player2_is_ai: bool = False,
    ) -> None:
        """
        Set player names and AI flag, then reset the board.

        Parameters
        ----------
        player1_name : str
            Display name for Player 1.
        player2_name : str
            Display name for Player 2 (can be "AI" for vs-computer mode).
        player2_is_ai : bool
            Whether Player 2 is controlled by the AI engine.
        """
        self.players[0] = PlayerInfo(name=player1_name, is_ai=False)
        self.players[1] = PlayerInfo(name=player2_name, is_ai=player2_is_ai)
        self.reset()

    def reset(self) -> None:
        """
        Fully reset the game to its starting configuration while preserving
        the current player names and AI flags.
        """
        self.board.reset()
        for pawn in self.pawns:
            pawn.reset()
        for info in self.players:
            info.walls_remaining = 10
            info.walls_placed    = 0
            info.turns_taken     = 0
        self.current_player = 0
        self.phase          = GamePhase.PLAYING
        self.winner         = None
        self.total_turns    = 0
        self._history.clear()
        self._redo_stack.clear()

    # ------------------------------------------------------------------
    # Queries (read-only helpers for controller and view)
    # ------------------------------------------------------------------

    @property
    def active_pawn(self) -> Pawn:
        """Return the pawn of the player whose turn it is."""
        return self.pawns[self.current_player]

    @property
    def opponent_pawn(self) -> Pawn:
        """Return the pawn of the player who is NOT currently moving."""
        return self.pawns[1 - self.current_player]

    @property
    def active_player_info(self) -> PlayerInfo:
        """Return the PlayerInfo of the active player."""
        return self.players[self.current_player]

    def legal_pawn_moves(self) -> list[tuple[int, int]]:
        """
        Return legal pawn destinations for the current active player.

        Delegates to :meth:`Board.legal_pawn_moves` with pawn positions
        filled in automatically.

        Returns
        -------
        list[tuple[int, int]]
            Sorted list of (row, col) valid destinations.
        """
        ap = self.active_pawn
        op = self.opponent_pawn
        return self.board.legal_pawn_moves(ap.row, ap.col, op.row, op.col)

    def can_place_wall(self, r: int, c: int, orientation: WallOrientation) -> bool:
        """
        Return True if the active player may place a wall at (r, c).

        Checks wall inventory and delegates geometric/path validation to Board.

        Parameters
        ----------
        r, c : int
            Wall start position.
        orientation : WallOrientation
            HORIZONTAL or VERTICAL.

        Returns
        -------
        bool
            True if all conditions (inventory > 0, no conflicts, no blockage)
            are satisfied.
        """
        if self.players[self.current_player].walls_remaining <= 0:
            return False
        return self.board.is_wall_placement_valid(r, c, orientation, self.pawns)

    def is_game_over(self) -> bool:
        """Return True if the game has concluded."""
        return self.phase is GamePhase.FINISHED

    def can_undo(self) -> bool:
        """Return True if there is at least one move to undo."""
        return len(self._history) > 0

    def can_redo(self) -> bool:
        """Return True if there is at least one move to redo."""
        return len(self._redo_stack) > 0

    # ------------------------------------------------------------------
    # Mutations (all route through the command stack)
    # ------------------------------------------------------------------

    def apply_pawn_move(self, dest_row: int, dest_col: int) -> None:
        """
        Move the active pawn to (dest_row, dest_col) and advance the turn.

        Records the move in history for Undo support.

        Parameters
        ----------
        dest_row, dest_col : int
            Validated destination (callers must check legality first).
        """
        ap = self.active_pawn
        command = {
            "type"        : "pawn_move",
            "player"      : self.current_player,
            "from_row"    : ap.row,
            "from_col"    : ap.col,
            "to_row"      : dest_row,
            "to_col"      : dest_col,
        }
        ap.move_to(dest_row, dest_col)
        self._after_action(command)

    def apply_wall_placement(
        self, r: int, c: int, orientation: WallOrientation
    ) -> Wall:
        """
        Place a wall at (r, c) for the active player and advance the turn.

        Records the placement in history for Undo support.

        Parameters
        ----------
        r, c : int
            Wall start position.
        orientation : WallOrientation
            HORIZONTAL or VERTICAL.

        Returns
        -------
        Wall
            The newly placed Wall object.
        """
        wall = self.board.place_wall(r, c, orientation, self.current_player)
        self.players[self.current_player].walls_remaining -= 1
        self.players[self.current_player].walls_placed    += 1

        command = {
            "type"       : "wall_place",
            "player"     : self.current_player,
            "row"        : r,
            "col"        : c,
            "orientation": orientation,
        }
        self._after_action(command)
        return wall

    def undo(self) -> bool:
        """
        Undo the last action and push it to the redo stack.

        Returns
        -------
        bool
            True if an action was successfully undone.
        """
        if not self._history:
            return False

        command = self._history.pop()
        self._redo_stack.append(command)
        self._invert_command(command)

        # Roll back turn and turn counter
        self.current_player = command["player"]
        self.total_turns   -= 1
        self.players[self.current_player].turns_taken -= 1
        self.phase  = GamePhase.PLAYING
        self.winner = None
        return True

    def redo(self) -> bool:
        """
        Re-apply the last undone action.

        Returns
        -------
        bool
            True if an action was successfully re-applied.
        """
        if not self._redo_stack:
            return False

        command = self._redo_stack.pop()
        self._replay_command(command)
        return True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _after_action(self, command: dict) -> None:
        """
        Perform bookkeeping common to all actions:
        push command to history, clear redo stack, advance turn counter,
        check for victory.

        Parameters
        ----------
        command : dict
            The command dict representing the completed action.
        """
        self._history.append(command)
        self._redo_stack.clear()

        self.players[self.current_player].turns_taken += 1
        self.total_turns += 1

        # Check if the active pawn has reached the goal
        if self.active_pawn.has_reached_goal():
            self.phase  = GamePhase.FINISHED
            self.winner = self.current_player
        else:
            # Advance turn
            self.current_player = 1 - self.current_player

    def _invert_command(self, command: dict) -> None:
        """
        Reverse a command's side-effects (used by Undo).

        Parameters
        ----------
        command : dict
            Command dict to reverse.
        """
        if command["type"] == "pawn_move":
            player_idx = command["player"]
            self.pawns[player_idx].move_to(command["from_row"], command["from_col"])

        elif command["type"] == "wall_place":
            player_idx  = command["player"]
            orientation = command["orientation"]
            self.board.remove_wall(command["row"], command["col"], orientation)
            self.players[player_idx].walls_remaining += 1
            self.players[player_idx].walls_placed    -= 1

    def _replay_command(self, command: dict) -> None:
        """
        Re-apply a command (used by Redo).

        Parameters
        ----------
        command : dict
            Command dict to replay.
        """
        if command["type"] == "pawn_move":
            self.current_player = command["player"]
            self.apply_pawn_move(command["to_row"], command["to_col"])

        elif command["type"] == "wall_place":
            self.current_player = command["player"]
            self.apply_wall_placement(
                command["row"], command["col"], command["orientation"]
            )

    # ------------------------------------------------------------------
    # Serialisation (bonus: save/load)
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialise the full game state to a plain dict."""
        def _serialize_cmd(cmd: dict) -> dict:
            d = dict(cmd)
            if "orientation" in d:
                d["orientation"] = d["orientation"].name
            return d

        return {
            "board"          : self.board.to_dict(),
            "pawns"          : [(p.row, p.col) for p in self.pawns],
            "current_player" : self.current_player,
            "total_turns"    : self.total_turns,
            "players"        : [
                {
                    "name"            : info.name,
                    "is_ai"           : info.is_ai,
                    "walls_remaining" : info.walls_remaining,
                    "walls_placed"    : info.walls_placed,
                    "turns_taken"     : info.turns_taken,
                }
                for info in self.players
            ],
            "history": [_serialize_cmd(c) for c in self._history],
            "redo_stack": [_serialize_cmd(c) for c in self._redo_stack],
        }

    @classmethod
    def from_dict(cls, data: dict)-> "GameState":
        gs = cls()
        gs.board = Board.from_dict(data["board"])
        for i, (r, c) in enumerate(data["pawns"]):
            gs.pawns[i].move_to(r, c)

        gs.current_player = data["current_player"]
        gs.total_turns = data["total_turns"]
        gs.phase = GamePhase[data.get("phase", "PLAYING")]
        gs.winner = data.get("winner")

        def _deserialize_cmd(cmd: dict) -> dict:
            d = dict(cmd)
            if "orientation" in d:
                d["orientation"] = WallOrientation[d["orientation"]]
            return d

        gs._history = [_deserialize_cmd(c) for c in data.get("history", [])]
        gs._redo_stack = [_deserialize_cmd(c) for c in data.get("redo_stack", [])]

        gs.players = [
            PlayerInfo(
                name=p["name"],
                is_ai=p["is_ai"],
                walls_remaining=p["walls_remaining"],
                walls_placed=p["walls_placed"],
                turns_taken=p["turns_taken"],
            )
            for p in data.get("players", [])
        ]
        return gs
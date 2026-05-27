"""
controllers/game_controller.py
================================
GameController — the central orchestrator between Model and View.

It is a QObject so it can:
  • Emit Signals consumed by the NavigationController.
  • Receive UI signals (cell clicks, toolbar actions) as Slots.
  • Schedule AI moves via QThreadPool without blocking the UI thread.

Turn lifecycle (Human vs. AI)
------------------------------
  1. ``start_ai_game()`` configures GameState and emits ``game_started``.
  2. BoardScreen calls ``on_cell_clicked / on_wall_clicked`` for human turns.
  3. After each human action the controller calls ``_after_action()``:
       a) Checks for game-over → emits ``game_over`` if true.
       b) If next turn is AI → schedules AIWorker on the thread pool.
  4. AIWorker emits ``finished`` → ``on_ai_move_ready`` applies the move.

Turn lifecycle (Local Human vs. Human)
---------------------------------------
Same as above but the AI scheduling step is skipped entirely.

Interaction state machine
--------------------------
The controller uses a simple two-state machine:
  • IDLE   — waiting for the player to select a pawn or hover over a wall slot.
  • PAWN_SELECTED — a pawn has been clicked; subsequent clicks on valid squares
                    move the pawn; a click elsewhere deselects it.
  • WALL_MODE — toggled by the mode button; wall slot clicks place walls.

Wall placement is only processed when _wall_mode is True.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QObject, Signal, Slot, QThreadPool

from models.game_state import GameState, GamePhase
from models.wall import WallOrientation
from services.ai_engine import AIWorker
from views.screens.board_screen import BoardScreen


class GameController(QObject):
    """
    Mediates all game logic between the Model (GameState) and the View.

    Signals
    -------
    game_started : Signal()
        Emitted after configure + reset so the NavigationController can
        switch to the Board screen.
    game_over : Signal(str, int, int)
        Emitted when a player reaches the goal row.
        Carries (winner_name, total_turns, winner_walls_placed).
    board_updated : Signal()
        Emitted after every state mutation so the BoardScreen can repaint.
    """

    game_started  : Signal = Signal()
    game_over     : Signal = Signal(str, int, int)   # name, turns, walls
    board_updated : Signal = Signal()

    # ------------------------------------------------------------------

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

        self._state            : GameState      = GameState()
        self._difficulty       : str            = "medium"
        self._ai_player_idx    : Optional[int]  = None    # None → local mode
        self._selected_pawn    : Optional[int]  = None    # 0 or 1 if pawn chosen
        self._valid_moves      : list[tuple[int,int]] = []
        self._ai_thinking      : bool           = False   # guard double-triggers
        self._board_screen     : Optional["BoardScreen"] = None  # set by NavCtrl

    # ------------------------------------------------------------------
    # Dependency injection (called by the app bootstrap)
    # ------------------------------------------------------------------

    def set_board_screen(self, screen: "BoardScreen") -> None:
        """
        Inject a reference to the BoardScreen so the controller can push
        display updates directly.

        Parameters
        ----------
        screen : BoardScreen
            The live board screen widget.
        """
        self._board_screen = screen

    # ------------------------------------------------------------------
    # Game session start
    # ------------------------------------------------------------------

    @Slot(str, str)
    def start_local_game(self, p1_name: str, p2_name: str) -> None:
        """
        Configure and start a Human vs. Human local game.

        Parameters
        ----------
        p1_name, p2_name : str
            Player display names from the setup screen.
        """
        self._ai_player_idx = None
        self._state.configure(p1_name, p2_name, player2_is_ai=False)
        self._wall_mode = False
        self._reset_interaction()
        self.game_started.emit()
        self._push_display()

    @Slot(str, str)
    def start_ai_game(self, player_name: str, difficulty: str) -> None:
        """
        Configure and start a Human vs. AI game.

        Parameters
        ----------
        player_name : str
            Human player's display name.
        difficulty : str
            AI difficulty tier: ``"easy" | "medium" | "hard"``.
        """
        self._difficulty    = difficulty
        self._ai_player_idx = 1    # AI always occupies player slot 1
        ai_label = {"easy": "Novice", "medium": "Adept", "hard": "Architect"}
        self._state.configure(
            player_name, ai_label.get(difficulty, "AI"), player2_is_ai=True
        )
        self._wall_mode = False
        self._reset_interaction()
        self.game_started.emit()
        self._push_display()

    @Slot(bool)
    def set_wall_mode(self, active: bool) -> None:
        """
        Toggle wall placement mode.

        CHANGE: When wall mode is activated, we deselect any selected pawn
        and clear valid moves so the user doesn't accidentally move while
        trying to place walls.
        """
        self._wall_mode = active
        if active:
            self._selected_pawn = None
            self._valid_moves = []
        self._push_display()

    # ------------------------------------------------------------------
    # User interaction slots (connected by NavigationController)
    # ------------------------------------------------------------------

    @Slot(int, int)
    def on_cell_clicked(self, row: int, col: int) -> None:
        """
        Handle a click on a board cell.

        Logic
        -----
        • If wall mode is active → ignore cell clicks (walls only).
        • If no pawn is selected and the clicked cell contains the active
          pawn → select it and highlight valid moves.
        • If a pawn IS selected and the clicked cell is a valid move → move.
        • Otherwise → deselect.

        Parameters
        ----------
        row, col : int
            Zero-based cell coordinates clicked by the user.
        """
        if self._state.is_game_over() or self._ai_thinking:
            return
        if self._is_ai_turn():
            return

        # block cells' calls in case in walls mode.
        if self._wall_mode:
            return

        ap = self._state.active_pawn

        if self._selected_pawn is None:
            # Attempt to select the active player's pawn
            if (row, col) == (ap.row, ap.col):
                self._selected_pawn = self._state.current_player
                self._valid_moves   = self._state.legal_pawn_moves()
                self._push_display()
        else:
            # Pawn is already selected
            if (row, col) in self._valid_moves:
                self._state.apply_pawn_move(row, col)
                self._reset_interaction()
                self._after_action()
            else:
                # Clicked elsewhere → deselect
                self._reset_interaction()
                self._push_display()

    @Slot(int, int, WallOrientation)
    def on_wall_clicked(self, r: int, c: int, orientation: WallOrientation) -> None:
        """
        Handle a click on a wall slot on the board.
        only processed when _wall_mode is True.
        Validates the placement via GameState and applies it if legal.

        Parameters
        ----------
        r, c : int
            Wall start position (0-7).
        orientation : WallOrientation
            HORIZONTAL or VERTICAL.
        """
        if self._state.is_game_over() or self._ai_thinking:
            return
        if self._is_ai_turn():
            return
        if not self._wall_mode:
            return

        if self._state.can_place_wall(r, c, orientation):
            self._state.apply_wall_placement(r, c, orientation)
            self._reset_interaction()
            self._after_action()

    @Slot()
    def on_undo(self) -> None:
        """
        Undo the last action.

        In AI mode two moves are undone (the human's move and the AI's
        response) so the human always gets the board back in a state where
        it is their turn.
        """
        if self._ai_thinking:
            return
        if self._state.undo():
            # In AI mode also undo the AI's preceding move
            if self._ai_player_idx is not None and self._state.can_undo():
                self._state.undo()
            self._reset_interaction()
            self._push_display()

    @Slot()
    def on_redo(self) -> None:
        """Re-apply the last undone action."""
        if self._ai_thinking:
            return
        if self._state.redo():
            self._reset_interaction()
            self._after_action()

    @Slot()
    def on_reset(self) -> None:
        """Reset the board to game-start while keeping the same player names."""
        self._ai_thinking = False
        self._state.reset()
        self._wall_mode = False
        self._reset_interaction()
        self._push_display()

    def cancel_game(self) -> None:
        """
        Abort the current session (called when the Exit button is pressed).
        Clears AI state so no pending worker callback can fire.
        """
        self._ai_thinking = False
        self._state.phase = GamePhase.SETUP

    # called by BoardScreen signals to save/load games.
    def save_to_file(self, path: str) -> None:
        """Serialize current game state to JSON."""
        import json
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._state.to_dict(), f, indent=2, default=str)

    def load_from_file(self, path: str) -> bool:
        """Restore game state from JSON."""
        import json
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._state = GameState.from_dict(data)
            p1 = self._state.players[1]
            self._ai_player_idx = 1 if p1.is_ai else None
            self._wall_mode = False
            self._ai_thinking = False
            self._reset_interaction()
            self._push_display()
            if not self._state.is_game_over() and self._is_ai_turn():
                self._schedule_ai_move()
            return True
        except Exception as exc:
            print(f"Failed to load game: {exc}")
            return False

    # ------------------------------------------------------------------
    # AI move handling
    # ------------------------------------------------------------------

    def _schedule_ai_move(self) -> None:
        """
        Spin up an AIWorker on the global thread pool to compute the AI's
        move without blocking the UI thread.

        Sets ``_ai_thinking = True`` so user interactions are ignored while
        the AI computes.
        """
        if self._ai_player_idx is None:
            return
        self._ai_thinking = True
        self._push_display()   # show "AI is thinking" state if desired

        worker = AIWorker(self._state, self._ai_player_idx, self._difficulty)
        worker.signals.finished.connect(self.on_ai_move_ready)
        QThreadPool.globalInstance().start(worker)

    @Slot(dict)
    def on_ai_move_ready(self, move: dict) -> None:
        """
        Apply the AI's computed move to the game state.

        Called on the main thread via the Qt signal queued connection
        (QThreadPool → Signal → Slot guarantees thread-safe delivery).

        Parameters
        ----------
        move : dict
            Move descriptor produced by :func:`~services.ai_engine.compute_move`.
        """
        self._ai_thinking = False

        # Guard: game may have been cancelled or reset while AI was thinking
        if self._state.is_game_over() or self._state.phase == GamePhase.SETUP:
            return

        if move["type"] == "pawn_move":
            self._state.apply_pawn_move(move["row"], move["col"])
        elif move["type"] == "wall":
            self._state.apply_wall_placement(
                move["row"], move["col"], move["orientation"]
            )

        self._reset_interaction()
        self._after_action()

    # ------------------------------------------------------------------
    # Post-action lifecycle
    # ------------------------------------------------------------------

    def _after_action(self) -> None:
        """
        Common bookkeeping run after EVERY applied game action:
          1. Check for game-over and emit the appropriate signal.
          2. Push display update to BoardScreen.
          3. Schedule AI move if it is now the AI's turn.
        """
        if self._state.is_game_over():
            winner_idx  = self._state.winner
            info        = self._state.players[winner_idx]
            self.game_over.emit(
                info.name,
                self._state.total_turns,
                info.walls_placed,
            )
            self._push_display()
            return

        self._push_display()

        if self._is_ai_turn():
            self._schedule_ai_move()

    # ------------------------------------------------------------------
    # Display push
    # ------------------------------------------------------------------

    def _push_display(self) -> None:
        """
        Push the complete current state to the BoardScreen in one call.

        This is the only place the controller writes to the View; all
        other methods only mutate the Model.
        """
        if self._board_screen is None:
            return

        s = self._state
        p0, p1 = s.players[0], s.players[1]

        self._board_screen.refresh(
            player0_name   = p0.name,
            player1_name   = p1.name,
            player0_walls  = p0.walls_remaining,
            player1_walls  = p1.walls_remaining,
            pawn_positions = [s.pawns[0].position, s.pawns[1].position],
            h_walls        = s.board.h_walls,
            v_walls        = s.board.v_walls,
            h_wall_owners  = s.board.h_walls_owners,
            v_wall_owners  = s.board.v_walls_owners,
            valid_moves    = self._valid_moves,
            selected_pawn  = self._selected_pawn,
            current_player = s.current_player,
            can_undo       = s.can_undo(),
            can_redo       = s.can_redo(),
            turn_message   = "AI Thinking…" if self._ai_thinking else "",
            wall_mode      = self._wall_mode,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_ai_turn(self) -> bool:
        """Return True if it is currently the AI player's turn."""
        return (
            self._ai_player_idx is not None and
            self._state.current_player == self._ai_player_idx
        )

    def _reset_interaction(self) -> None:
        """Clear pawn selection and move highlights."""
        self._selected_pawn = None
        self._valid_moves   = []
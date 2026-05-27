"""
controllers/navigation_controller.py
======================================
NavigationController — owns the QStackedWidget and routes the application
between the six screens.

It is the single point of truth for which screen is currently visible.
The GameController (which manages game logic) connects its lifecycle signals
here so screens swap automatically when a game starts or ends.

Screen index map (matches QStackedWidget insertion order)
----------------------------------------------------------
  0  MainMenuScreen
  1  LocalMatchScreen
  2  AiMatchScreen
  3  BoardScreen
  4  VictoryScreen
  5  RulesScreen

Responsibilities
----------------
• Build and own all screen instances (once).
• Connect every inter-screen navigation signal.
• Expose a single ``go_to(index)`` method so the GameController can trigger
  a board→victory transition without importing Qt stacking logic.
• Maintain a navigation stack so the Rules page knows which screen to return to.
"""

from __future__ import annotations

from PySide6.QtWidgets import QStackedWidget, QFileDialog
from PySide6.QtCore import QObject

from controllers import GameController
from screens.main_menu_screen import MainMenuScreen
from screens.local_match_screen import LocalMatchScreen
from screens.ai_match_screen import AiMatchScreen
from screens.victory_screen import VictoryScreen
from screens.board_screen import BoardScreen
from screens.rules_screen import RulesScreen

# Screen index constants — import these in GameController for readability
IDX_MAIN_MENU   = 0
IDX_LOCAL_MATCH = 1
IDX_AI_MATCH    = 2
IDX_BOARD       = 3
IDX_VICTORY     = 4
IDX_RULES       = 5


class NavigationController(QObject):
    """
    Manages the top-level QStackedWidget and wires navigation signals
    between all six screens.

    Parameters
    ----------
    stack : QStackedWidget
        The central widget of the main window.  All screen widgets are
        added to this stack on construction.
    game_ctrl : GameController
        Reference to the game controller; connected to game-start and
        game-end events.
    """

    def __init__(
        self,
        stack    : QStackedWidget,
        game_ctrl : "GameController",
    ) -> None:
        super().__init__()

        self._stack     = stack
        self._game_ctrl = game_ctrl
        self._prev_idx  = IDX_MAIN_MENU   # used to return from Rules

        # ── Instantiate all screens ──────────────────────────────────────
        self.main_menu    = MainMenuScreen()
        self.local_match  = LocalMatchScreen()
        self.ai_match     = AiMatchScreen()
        self.board        = BoardScreen()
        self.victory      = VictoryScreen()
        self.rules        = RulesScreen()

        # Insert in the fixed order
        for screen in [
            self.main_menu,   # 0
            self.local_match, # 1
            self.ai_match,    # 2
            self.board,       # 3
            self.victory,     # 4
            self.rules,       # 5
        ]:
            stack.addWidget(screen)

        self._wire_signals()

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _wire_signals(self) -> None:
        """
        Connect every navigation signal in the application.

        All connections are made here so the individual screen classes
        remain decoupled — they only emit signals, never import each other.
        """
        gc = self._game_ctrl

        # ── Main Menu ────────────────────────────────────────────────────
        self.main_menu.local_match_requested.connect(
            lambda: self.go_to(IDX_LOCAL_MATCH)
        )
        self.main_menu.ai_match_requested.connect(
            lambda: self.go_to(IDX_AI_MATCH)
        )

        if hasattr(self.main_menu, 'load_game_requested'):
            self.main_menu.load_game_requested.connect(self._on_load_game)

        self.main_menu.rules_requested.connect(self._push_rules)

        # ── Local Match Setup ────────────────────────────────────────────
        self.local_match.back_requested.connect(
            lambda: self.go_to(IDX_MAIN_MENU)
        )
        self.local_match.rules_requested.connect(self._push_rules)
        self.local_match.begin_requested.connect(gc.start_local_game)

        # ── AI Match Setup ───────────────────────────────────────────────
        self.ai_match.back_requested.connect(
            lambda: self.go_to(IDX_MAIN_MENU)
        )
        self.ai_match.rules_requested.connect(self._push_rules)
        self.ai_match.begin_requested.connect(gc.start_ai_game)

        # ── Board Screen ─────────────────────────────────────────────────
        self.board.exit_requested.connect(self._on_exit_game)
        self.board.rules_requested.connect(self._push_rules)
        self.board.cell_clicked.connect(gc.on_cell_clicked)
        self.board.wall_clicked.connect(gc.on_wall_clicked)
        self.board.undo_requested.connect(gc.on_undo)
        self.board.redo_requested.connect(gc.on_redo)
        self.board.reset_requested.connect(gc.on_reset)
        self.board.save_requested.connect(self._on_save_game)
        self.board.wall_mode_toggled.connect(gc.set_wall_mode)

        # ── Victory Screen ───────────────────────────────────────────────
        self.victory.menu_requested.connect(
            lambda: self.go_to(IDX_MAIN_MENU)
        )
        self.victory.rules_requested.connect(self._push_rules)

        # ── Rules Screen ─────────────────────────────────────────────────
        self.rules.back_requested.connect(self._pop_rules)

        # ── GameController → navigation events ──────────────────────────
        gc.game_started.connect(lambda: self.go_to(IDX_BOARD))
        gc.game_over.connect(self._on_game_over)

    # ------------------------------------------------------------------
    # Navigation helpers
    # ------------------------------------------------------------------

    def go_to(self, index: int) -> None:
        """
        Switch the visible screen to the given stack index.

        Parameters
        ----------
        index : int
            One of the IDX_* constants defined in this module.
        """
        self._stack.setCurrentIndex(index)

    def _push_rules(self) -> None:
        """Navigate to the Rules screen, remembering the origin screen."""
        self._prev_idx = self._stack.currentIndex()
        self.go_to(IDX_RULES)
        self.rules.reset_scroll()

    def _pop_rules(self) -> None:
        """Return from the Rules screen to wherever the user came from."""
        self.go_to(self._prev_idx)

    def _on_exit_game(self) -> None:
        """
        Handle the Exit button on the Board screen.

        Cancels the current game (via the GameController) and returns to
        the main menu.
        """
        self._game_ctrl.cancel_game()
        self.go_to(IDX_MAIN_MENU)

    def _on_game_over(self, winner_name: str, turns: int, walls_placed: int) -> None:
        """
        Populate the Victory screen and navigate to it.

        Parameters
        ----------
        winner_name : str
            Display name of the winning player.
        turns : int
            Total turns taken.
        walls_placed : int
            Walls placed by the winner.
        """
        self.victory.show_result(winner_name, turns, walls_placed)
        self.go_to(IDX_VICTORY)

    # Save/Load handlers
    def _on_save_game(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self._stack,
            "Save Game",
            "quoridor_save.json",
            "JSON (*.json)",
        )
        if path:
            self._game_ctrl.save_to_file(path)

    def _on_load_game(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self._stack,
            "Load Game",
            "",
            "JSON (*.json)",
        )
        if path:
            if self._game_ctrl.load_from_file(path):
                self.go_to(IDX_BOARD)
"""
tests/test_integration.py
=========================
Integration test suite running in headless offscreen mode.

Simulates standard local pass-and-play sessions and tests AI logic
for all three difficulties (Novice, Adept, and Architect).
"""

import sys
import os
import time
import unittest

# Force root folder import visibility
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication, QEventLoop

# Establish headless QApplication singleton if not already initialized
app = QApplication.instance()
if not app:
    app = QApplication(["", "-platform", "offscreen"])

from src.controllers.game_controller import GameController
from src.models.game_state import GamePhase
from src.models.wall import WallOrientation


class MockBoardScreen:
    """Lightweight test fixture mimicking BoardScreen presentation hooks."""
    def __init__(self) -> None:
        self.refresh_calls = []

    def refresh(self, **kwargs) -> None:
        self.refresh_calls.append(kwargs)


class TestQuoridorHeadless(unittest.TestCase):
    """Functional integration test suite executing headless gameplay simulations."""

    def setUp(self) -> None:
        self.controller = GameController()
        self.mock_screen = MockBoardScreen()
        self.controller.set_board_screen(self.mock_screen)

    def tearDown(self) -> None:
        self.controller.cancel_game()

    def _wait_for_ai(self, timeout_ms: int = 5000) -> None:
        """Process events while waiting for the background AI thread pool to return."""
        start_time = time.perf_counter()
        while self.controller._ai_thinking:
            QCoreApplication.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
            if (time.perf_counter() - start_time) * 1000 > timeout_ms:
                raise TimeoutError("AI thinking execution limit exceeded.")
            time.sleep(0.01)

    def test_local_game_flow(self) -> None:
        """Verify local turn cycles, custom highlights, and undo/redo operations."""
        self.controller.start_local_game("Alice", "Bob")
        state = self.controller._state

        # Verify structural reset values
        self.assertEqual(state.phase, GamePhase.PLAYING)
        self.assertEqual(state.current_player, 0)
        self.assertEqual(state.pawns[0].position, (8, 4))
        self.assertEqual(state.pawns[1].position, (0, 4))

        # Select pawn and execute standard orthogonal forward step
        self.controller.on_cell_clicked(8, 4)
        self.controller.on_cell_clicked(7, 4)

        self.assertEqual(state.pawns[0].position, (7, 4))
        self.assertEqual(state.current_player, 1)  # Bob's turn

        # Test standard backward undo functionality
        self.controller.on_undo()
        self.assertEqual(state.pawns[0].position, (8, 4))
        self.assertEqual(state.current_player, 0)

        # Verify forward redo execution
        self.controller.on_redo()
        self.assertEqual(state.pawns[0].position, (7, 4))
        self.assertEqual(state.current_player, 1)

    def test_wall_placement_rules(self) -> None:
        """Ensure wall placement transitions state correctly and decrements inventory."""
        self.controller.start_local_game("Alice", "Bob")
        state = self.controller._state

        # Activate Wall Mode
        self.controller.set_wall_mode(True)
        self.assertTrue(self.controller._wall_mode)

        # Place valid horizontal block
        self.controller.on_wall_clicked(7, 4, WallOrientation.HORIZONTAL)
        self.assertIn((7, 4), state.board.h_walls)
        self.assertEqual(state.players[0].walls_remaining, 9)
        self.assertEqual(state.current_player, 1)

    def test_difficulty_novice_ai(self) -> None:
        """Check turn completion and movement under easy (Novice) difficulty."""
        self.controller.start_ai_game("Human", "easy")
        state = self.controller._state

        # Human moves pawn out of starting space
        self.controller.on_cell_clicked(8, 4)
        self.controller.on_cell_clicked(7, 4)

        # Verify background AI execution fires
        self.assertTrue(self.controller._is_ai_turn())
        self._wait_for_ai()

        # AI should have taken its turn and returned play to human
        self.assertEqual(state.current_player, 0)
        self.assertNotEqual(state.pawns[1].position, (0, 4))

    def test_difficulty_adept_ai(self) -> None:
        """Ensure proper move calculations under medium (Adept) difficulty."""
        self.controller.start_ai_game("Human", "medium")
        state = self.controller._state

        self.controller.on_cell_clicked(8, 4)
        self.controller.on_cell_clicked(7, 4)

        self.assertTrue(self.controller._is_ai_turn())
        self._wait_for_ai()

        self.assertEqual(state.current_player, 0)
        self.assertNotEqual(state.pawns[1].position, (0, 4))

    def test_difficulty_architect_ai(self) -> None:
        """Ensure correct deep minimax lookahead execution under hard (Architect) difficulty."""
        self.controller.start_ai_game("Human", "hard")
        state = self.controller._state

        self.controller.on_cell_clicked(8, 4)
        self.controller.on_cell_clicked(7, 4)

        self.assertTrue(self.controller._is_ai_turn())
        self._wait_for_ai()

        self.assertEqual(state.current_player, 0)
        self.assertNotEqual(state.pawns[1].position, (0, 4))


if __name__ == "__main__":
    unittest.main()
"""views/views — UI Screens Displayed."""
from views.screens.board_screen import BoardScreen
from views.screens.ai_match_screen import AiMatchScreen
from views.screens.local_match_screen import LocalMatchScreen
from views.screens.victory_screen import VictoryScreen
from views.screens.main_menu_screen import MainMenuScreen
from views.screens.rules_screen import RulesScreen

__all__ = [
    "BoardScreen",
    "AiMatchScreen",
    "LocalMatchScreen",
    "VictoryScreen",
    "MainMenuScreen",
    "RulesScreen"
]
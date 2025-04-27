# constants.py
# -*- coding: utf-8 -*-
"""
Shared constants for the Network Equation Game.
"""

# --- Game Constants ---
DEFAULT_BOARD_SIZE = 6
MIN_EQ_LEN = 5
EMPTY_CELL = ' '
PLAYERS = {
    'A': {'symbol': 'x', 'name': 'Player A (White)', 'color': 'white', 'text_color': 'black'},
    'B': {'symbol': 'y', 'name': 'Player B (Yellow)', 'color': 'yellow', 'text_color': 'black'}
}

# --- GUI Constants ---
WIN_HIGHLIGHT_BG = "lightgreen" # Background color for winning path cells
WIN_HIGHLIGHT_BORDER = "darkgreen" # Border color for winning path cells

# Board size to GUI size presets
# (board_size_threshold, (button_font_size, char_button_font_size))
GUI_SIZE_PRESETS = [
    (8,  (14, 10)), # <= 8x8
    (12, (12, 10)), # <= 12x12
    (16, (10, 9)),  # <= 16x16
    (22, (9, 8)),   # <= 22x22
    (30, (7, 8)),   # <= 30x30
]
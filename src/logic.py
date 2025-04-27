# logic.py
# -*- coding: utf-8 -*-
"""
Core game logic functions (equation validation, win checking).
Returns the winning equation and its solution upon validation.
"""
from sympy import sympify, solve, symbols, Eq, Integer, Basic # Keep Basic for potential type checks if needed later
import traceback # Import for optional detailed error logging

# Import necessary constants
# Make sure constants.py is accessible (in the same directory or Python path)
try:
    from constants import MIN_EQ_LEN, EMPTY_CELL, PLAYERS
except ImportError:
    print("FATAL ERROR: Could not import constants. Ensure constants.py exists.")
    # Define fallbacks ONLY IF constants.py is missing, to avoid crashing immediately
    # THIS IS NOT IDEAL - FIX THE IMPORT
    MIN_EQ_LEN = 5
    EMPTY_CELL = ' '
    PLAYERS = {
        'A': {'symbol': 'x', 'name': 'Player A', 'color': 'lightblue', 'text_color': 'black'},
        'B': {'symbol': 'y', 'name': 'Player B', 'color': 'lightgreen', 'text_color': 'black'}
    }


# --- Preprocessing & Validation (Core Game Logic) ---
def preprocess_equation_string(raw_str):
    """Adds implicit '*' for multiplication next to variables."""
    processed = ""
    i, n = 0, len(raw_str)
    player_symbols = {p['symbol'] for p in PLAYERS.values()} # Get symbols dynamically

    while i < n:
        ch = raw_str[i]
        if ch.isdigit():
            num = ch; j = i + 1
            while j < n and raw_str[j].isdigit(): num += raw_str[j]; j += 1
            processed += num
            # Add '*' if number is followed by a variable
            if j < n and raw_str[j] in player_symbols:
                 processed += '*'
            i = j # Move index past the number
        elif ch in player_symbols:
            processed += ch
            # Add '*' if variable is followed by a number
            if i+1 < n and raw_str[i+1].isdigit():
                 processed += '*'
            i += 1
        elif ch in '+-*/=':
            processed += ch
            i += 1
        else:
             # Skip other characters silently (like spaces or invalid chars)
            i += 1
    return processed


# --- MODIFIED is_valid_equation ---
def is_valid_equation(raw_eq_str, player_var):
    """
    Checks if a raw string forms a valid equation for the given player variable.
    Returns the integer solution if valid, otherwise None.
    """
    # --- Basic structural checks ---
    if not isinstance(raw_eq_str, str): return None
    if len(raw_eq_str) < MIN_EQ_LEN: return None
    if raw_eq_str.count('=') != 1: return None
    if player_var not in raw_eq_str: return None

    # Ensure opponent's variable is not present
    # Find opponent symbol dynamically
    opp_var = None
    for pid, data in PLAYERS.items():
        if data['symbol'] != player_var:
            opp_var = data['symbol']
            break
    if opp_var and opp_var in raw_eq_str: return None

    # --- Preprocessing and parsing ---
    processed = preprocess_equation_string(raw_eq_str)
    # '=' must still be present after preprocessing
    if '=' not in processed: return None
    # Must contain at least one arithmetic operator (+, -, *, /)
    if not any(op in processed for op in '+-*/'): return None

    try:
        var = symbols(player_var)
        lhs_s, rhs_s = processed.split('=', 1)

        # Handle potentially empty sides after splitting/stripping
        lhs_s = lhs_s.strip() if lhs_s.strip() else '0'
        rhs_s = rhs_s.strip() if rhs_s.strip() else '0'

        # --- Use SymPy to parse and solve ---
        # Use locals dict to map player_var string to the SymPy symbol object
        local_dict = {player_var: var}
        lhs = sympify(lhs_s, locals=local_dict)
        rhs = sympify(rhs_s, locals=local_dict)

        # Ensure the player's variable is actually part of the equation after parsing/simplification
        if not (lhs.has(var) or rhs.has(var)):
            # print(f"Debug: Equation '{raw_eq_str}' -> '{processed}' simplifies without variable '{player_var}'.")
            return None

        # Prevent trivial wins like '5=5'
        if lhs == rhs and not lhs.has(var):
            # print(f"Debug: Equation '{raw_eq_str}' -> '{processed}' is trivial (e.g., 5=5).")
            return None

        # Prevent trivial wins like 'x=x' or '2*x=2*x' (which have infinite solutions)
        # SymPy's solve might return [] or True for these depending on context.
        # We want a *unique* integer solution.
        if lhs == rhs and lhs.has(var):
             # print(f"Debug: Equation '{raw_eq_str}' -> '{processed}' is an identity (e.g., x=x).")
             return None

        # Solve the equation
        sols = solve(Eq(lhs, rhs), var)

        # --- Check solutions ---
        if not sols:
            # print(f"Debug: No solution found for '{raw_eq_str}' -> '{processed}'.")
            return None # No solution found

        valid_integer_solution = None
        for s in sols:
            solution_int = None
            # Try robustly to convert SymPy solution 's' to a Python integer
            try:
                if s.is_Integer and s.is_finite:
                    solution_int = int(s)
                elif s.is_Float and s.is_finite and s == int(s):
                     solution_int = int(s)
                elif s.is_Rational and s.is_finite and s.q == 1: # Denominator is 1
                     solution_int = int(s.p) # Numerator
                # Additional check for real numbers that might represent integers
                elif s.is_real and s.is_finite:
                     # Be cautious with direct float comparison
                     if abs(s - round(s)) < 1e-10: # Check if very close to an integer
                          solution_int = int(round(s))
            except (AttributeError, TypeError, ValueError):
                # Ignore solutions that don't fit expected numeric types or fail conversion
                # print(f"Debug: Solution '{s}' (type: {type(s)}) is not a valid integer format.")
                continue # Check the next solution

            # If we successfully extracted an integer, use it
            if solution_int is not None:
                 valid_integer_solution = solution_int
                 # print(f"Debug: Found valid integer solution {valid_integer_solution} for '{raw_eq_str}' -> '{processed}'.")
                 break # Found the first valid integer solution, stop checking others

        # Return the found integer solution (or None if none was found)
        return valid_integer_solution

    except (SyntaxError, TypeError, ValueError, NotImplementedError, Exception) as e:
        # Catch potential sympy/parsing errors during sympify or solve
        # print(f"Debug: is_valid_equation sympy/parse error for '{raw_eq_str}' -> '{processed}': {e}")
        # traceback.print_exc() # Uncomment for full error details during debugging
        return None


# --- MODIFIED check_win_board ---
def check_win_board(board, size, player_sym):
    """
    Checks the board for a winning equation line for the given player symbol.
    Checks both original and REVERSED directions.

    Returns: tuple (win_status, coordinates, winning_equation_string, solution_value)
        - win_status (bool): True if a win is found, False otherwise.
        - coordinates (list): List of (row, col) tuples for the winning line.
        - winning_equation_string (str | None): The raw equation string that won.
        - solution_value (int | None): The integer solution for the player's variable.
    """
    if not board or not isinstance(board, list): return False, [], None, None

    # Iterate through all possible starting cells
    for r0 in range(size):
        for c0 in range(size):
            # Check all 8 directions (horizontal, vertical, diagonals)
            for dr, dc in [(0, 1), (1, 0), (1, 1), (1, -1), (0, -1), (-1, 0), (-1, -1), (-1, 1)]:
                raw, coords = '', []
                # Extend the line from (r0, c0) in the current direction
                for i in range(size):
                    r, c = r0 + i * dr, c0 + i * dc

                    # Check if coordinates are within board bounds
                    if not (0 <= r < size and 0 <= c < size):
                        # Reached edge of the board, check the sequence formed so far
                        if len(raw) >= MIN_EQ_LEN:
                             # Check original direction
                             solution = is_valid_equation(raw, player_sym)
                             if solution is not None:
                                 return True, coords, raw, solution
                             else:
                                 # Check reversed direction
                                 reversed_raw = raw[::-1]
                                 solution = is_valid_equation(reversed_raw, player_sym)
                                 if solution is not None:
                                     return True, coords, reversed_raw, solution
                        # Stop extending in this direction
                        break

                    # Get character from board safely
                    try:
                        ch = board[r][c]
                    except IndexError:
                        # Should not happen if bounds check is correct, but for safety:
                        # print(f"Warning: IndexError accessing board at ({r},{c})")
                        break # Stop extending this line

                    # Check if cell is empty
                    if ch == EMPTY_CELL:
                         # An empty cell breaks the *current* continuous segment.
                         # Check the segment formed *just before* this empty cell.
                         if len(raw) >= MIN_EQ_LEN:
                              # Check original direction
                              solution = is_valid_equation(raw, player_sym)
                              if solution is not None:
                                   return True, coords, raw, solution
                              else:
                                   # Check reversed direction
                                   reversed_raw = raw[::-1]
                                   solution = is_valid_equation(reversed_raw, player_sym)
                                   if solution is not None:
                                       return True, coords, reversed_raw, solution

                         # Since the segment is broken, stop extending *this* line from (r0,c0) in (dr,dc)
                         raw, coords = '', [] # Reset for safety, although break follows
                         break # Break the inner loop (stop extending this specific segment)

                    else: # Cell is not empty, append to current sequence
                        raw += ch
                        coords.append((r, c))
                        # Check if the *current* segment is a valid win (don't wait for end/gap)
                        if len(raw) >= MIN_EQ_LEN:
                             # Check original direction
                             solution = is_valid_equation(raw, player_sym)
                             if solution is not None:
                                 return True, coords, raw, solution
                             else:
                                 # Check reversed direction
                                 reversed_raw = raw[::-1]
                                 solution = is_valid_equation(reversed_raw, player_sym)
                                 if solution is not None:
                                     return True, coords, reversed_raw, solution

                # After the inner loop finishes (due to hitting edge or empty cell),
                # the necessary checks have already been performed within the loop
                # or just before the 'break'. No extra check needed here.

    # If we've checked all starting points and directions without returning, no win was found.
    return False, [], None, None
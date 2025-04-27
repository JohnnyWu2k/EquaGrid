# gui.py
# -*- coding: utf-8 -*-
"""
Handles the Tkinter GUI for the client. (Integrates Play Again & Closing)
"""
import tkinter as tk
from tkinter import messagebox, simpledialog
import json
import queue # Import the queue module
import threading # Might need for lock if accessing shared state directly later

# Import network client
from network import NetworkClient
# Import necessary game logic functions FROM logic.py
from logic import check_win_board, is_valid_equation
# Import ALL constants from constants.py
from constants import (
    EMPTY_CELL, PLAYERS, MIN_EQ_LEN, DEFAULT_BOARD_SIZE, # Game related
    WIN_HIGHLIGHT_BG, WIN_HIGHLIGHT_BORDER, GUI_SIZE_PRESETS # GUI related
)


# --- Client GUI Class ---
class ClientGUI:
    # --- __init__, start, queue_incoming_message, process_message_queue ---
    # (These methods remain the same as the queue-based version)
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.message_queue = queue.Queue()
        # Pass the correct methods as callbacks
        self.network = NetworkClient(host, port,
                                     self.queue_incoming_message,
                                     self.handle_network_error,    # Method to queue errors
                                     self.handle_connection_closed # Method to queue close notification
                                    )
        self.root = None
        self.board_size = DEFAULT_BOARD_SIZE
        self.board = []
        self.player_id = None
        self.current_turn = 'A'
        self.cell_btns = []
        self.status_label = None
        self.selected_char = None
        self.char_btns = {}
        self.game_over = False
        self.board_frame = None
        self.ctrl_frame = None
        self._gui_initialized = False
        self._gui_running = False # Flag to control the queue checker loop

    def start(self):
        """Initiates connection and starts the GUI and message queue processing."""
        self.root = tk.Tk()
        self.root.withdraw()
        # *** Set the protocol handler BEFORE mainloop ***
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing) # Assign the close handler
        self._gui_running = True

        if not self.network.connect():
            print("Client startup failed. Could not connect.")
            self._gui_running = False
            # Display error even if mainloop hasn't started
            messagebox.showerror("Connection Failed", f"Could not connect to {self.host}:{self.port}")
            if self.root: self.root.destroy()
            return

        self.root.after(100, self.process_message_queue)
        print("Starting Tkinter mainloop...")
        self.root.mainloop()
        print("Tkinter mainloop finished.")

        # Cleanup after mainloop exits (likely due to on_closing)
        self._gui_running = False # Ensure flag is false
        # Network close should have been initiated by on_closing already


    def queue_incoming_message(self, message):
        """ Puts the received message onto the thread-safe queue. """
        if self._gui_running: # Only queue if GUI is supposed to be active
             self.message_queue.put(message)
        # else: print("GUI not running, discarding message:", message.get('type'))


    def process_message_queue(self):
        """ Periodically processes messages from the queue in the main thread. """
        if not self._gui_running: # Stop processing if GUI is closing
             # print("Queue processing stopped.")
             return

        try:
            while not self.message_queue.empty():
                 try:
                      message = self.message_queue.get_nowait()
                      self.handle_server_message(message)
                 except queue.Empty:
                      break
                 except Exception as e:
                      print(f"Error processing message type {message.get('type', 'N/A')} from queue: {e}")

            # Reschedule only if still running
            if self._gui_running and self.root and self.root.winfo_exists():
                self.root.after(100, self.process_message_queue)

        except Exception as e:
             print(f"Error in process_message_queue loop: {e}")
             if self._gui_running and self.root and self.root.winfo_exists():
                 self.root.after(100, self.process_message_queue) # Try to recover


    # --- Callback Methods for NetworkClient (Called by Network Thread) ---
    def handle_network_error(self, error_message):
        """ Queues network errors for handling in the main thread. """
        print(f"Network Error Callback: {error_message}")
        if self._gui_running:
            self.message_queue.put({'type': '_internal_error', 'payload': error_message})

    def handle_connection_closed(self):
        """ Queues connection closed event for handling in the main thread. """
        print("Network Closed Callback.")
        if self._gui_running:
            self.message_queue.put({'type': '_internal_closed'})


    # --- on_closing (Handles window close event) ---
    def on_closing(self, force_close=False):
        """Handles window close button click or forced closure."""
        print("on_closing called...")
        confirm = force_close
        # Check if root exists and is interactable before showing messagebox
        if not force_close and self.root and self.root.winfo_exists():
             try:
                 confirm = messagebox.askokcancel("Quit", "Are you sure you want to quit?", parent=self.root)
             except Exception as e:
                 print(f"Error showing quit dialog: {e}")
                 confirm = True # Default to closing if dialog fails

        if confirm:
            print("Confirmed close. Initiating shutdown sequence.")
            # 1. Signal that the GUI is no longer running
            self._gui_running = False # Stop queue processing loop scheduling

            # 2. Mark game state (less critical now, but good practice)
            self.game_over = True

            # 3. Close the network connection
            # Check if network object exists and has a close method
            print("Attempting to close network connection...")
            if hasattr(self.network, 'close') and callable(self.network.close):
                 self.network.close() # This should trigger the _internal_closed message via callback
            else:
                 print("Network object or close method not found.")

            # 4. Destroy the Tkinter window
            # This will terminate the mainloop()
            if self.root:
                print("Attempting to destroy root window...")
                try:
                    self.root.destroy()
                    print("GUI destroyed.")
                except tk.TclError as e:
                     # This can happen if events fire rapidly during closing
                     print(f"Ignoring error during GUI destroy (window likely already gone): {e}")
                finally:
                     self.root = None # Ensure root is None after trying to destroy
        else:
            print("Close cancelled by user.")


    # --- handle_server_message (Handles logic based on message type) ---
    # (Ensure this method handles '_internal_error' and '_internal_closed' correctly)
    def handle_server_message(self, msg):
        """Processes messages received from the server IN THE MAIN THREAD."""
        # Check root window state at the beginning of processing each message
        if not self.root or not self.root.winfo_exists():
             # Don't process if window is gone, except maybe the internal closed signal
             if msg.get('type') != '_internal_closed':
                print(f"GUI window gone, discarding message: {msg.get('type')}")
                return

        msg_type = msg.get('type')

        # --- Init Handling ---
        if msg_type == 'init':
             # ... (init handling as before) ...
             if not self._gui_initialized:
                 self.initialize_game(msg['player'], msg['board_size'])
             else:
                 print("Warning: Received duplicate 'init' message. Ignoring.")
             return

        # --- Ignore messages before init ---
        # Add check for _gui_running as well, don't process if closing down
        if not self._gui_initialized or not self._gui_running:
             print(f"GUI not initialized or not running, discarding message: {msg_type}")
             return

        # --- Process other messages ---
        elif msg_type == 'move':
            if self.game_over: return
            r, c, ch = msg['row'], msg['col'], msg['char']
            pid = msg['player'] # Player who made the move

            if not (0 <= r < self.board_size and 0 <= c < self.board_size):
                print(f"Warning: Received move with invalid coordinates ({r},{c})")
                return

            # Update local board state
            self.board[r][c] = ch
            # Update GUI button appearance
            try:
                btn = self.cell_btns[r][c]
                if btn.winfo_exists():
                    # Use player info who MADE the move for coloring
                    info = PLAYERS.get(pid, {}) # Use .get for safety
                    btn_bg = info.get('color', 'SystemButtonFace')
                    btn_fg = info.get('text_color', 'black')
                    btn.config(text=ch, state=tk.DISABLED, bg=btn_bg, fg=btn_fg)
            except (IndexError, tk.TclError, AttributeError) as e:
                print(f"Error updating button for move at ({r},{c}): {e}")

            # --- Check for Win/Assist ---
            win_player_id = None # ID of the player whose equation won
            win_coords = []      # Coordinates of the winning line
            win_message = ""     # The final message for status/dialog
            win_eq = ""          # The winning equation string
            win_sol = None       # The solution value (integer)
            win_sym = ""         # The symbol ('x' or 'y') used in the winning eq

            # Check if the player who just moved (pid) won
            p_sym = PLAYERS[pid]['symbol']
            # Call the MODIFIED check_win_board, unpacking all 4 return values
            p_win_status, p_coords, p_eq, p_sol = check_win_board(self.board, self.board_size, p_sym)

            if p_win_status:
                win_player_id = pid
                win_coords = p_coords
                win_eq = p_eq
                win_sol = p_sol
                win_sym = p_sym
                # Format win message including equation and solution
                win_details = f"{win_eq} ({win_sym}={win_sol})"
                if pid == self.player_id:
                    win_message = f"🎉 You Win with {win_details}!"
                else:
                    win_message = f"{PLAYERS[pid]['name']} Wins with {win_details}!"
            else:
                # If the current player didn't win, check if their move *assisted* the opponent
                opponent_pid = 'B' if pid == 'A' else 'A'
                opp_sym = PLAYERS[opponent_pid]['symbol']
                # Call the MODIFIED check_win_board for the opponent
                opp_win_status, opp_coords, opp_eq, opp_sol = check_win_board(self.board, self.board_size, opp_sym)

                if opp_win_status:
                    win_player_id = opponent_pid # The opponent is the one who wins
                    win_coords = opp_coords
                    win_eq = opp_eq
                    win_sol = opp_sol
                    win_sym = opp_sym
                    # Format win message including equation and solution, noting assistance
                    win_details = f"{win_eq} ({win_sym}={win_sol})"
                    # Check who the winner is relative to the client running this code
                    if opponent_pid == self.player_id:
                         # This client's opponent made a move that let THIS client win
                         win_message = f"🎉 Opponent assisted, You Win with {win_details}!"
                    else:
                         # This client made a move that let the opponent win
                         win_message = f"{PLAYERS[opponent_pid]['name']} Wins (Assisted) with {win_details}!"

            # --- Handle Win Condition (if win_player_id is set) ---
            if win_player_id is not None: # A win occurred (direct or assisted)
                self.game_over = True
                self.highlight_winning_path(win_coords) # Highlight the winning cells
                self.update_status(win_message)         # Show the detailed win message
                self.disable_all_controls()             # Disable further interaction

                # --- Schedule post-win dialog ---
                print(f"Game Over. Scheduling 'Play Again?' dialog. Message: {win_message}")
                # Schedule show_post_win_dialog to run after current event processing
                if self.root and self.root.winfo_exists(): # Check root before scheduling
                     # Pass the detailed win_message to the dialog
                     self.root.after(100, lambda msg=win_message: self.show_post_win_dialog(msg))
            else:
                # If no win occurred, switch turn to the other player
                self.current_turn = 'B' if pid == 'A' else 'A'
                self.update_status() # Update status label to show whose turn it is

        elif msg_type == 'reset':
             # ... (reset handling remains the same) ...
            print("Reset message received, resetting GUI board...")
            self.reset_board_gui() # Call the reset method

        elif msg_type == 'opponent_left':
             # ... (opponent left handling as before) ...
            print("Opponent has left the game.")
            opponent_left_message = "Opponent Left"
            if not self.game_over:
                messagebox.showinfo("Opponent Left", "Your opponent has disconnected.", parent=self.root)
                self.update_status(opponent_left_message)
            self.game_over = True
            self.disable_all_controls()
            # --- Schedule post-win dialog after opponent leaves ---
            print("Opponent Left. Scheduling 'Play Again?' dialog.")
            if self.root and self.root.winfo_exists(): # Check root before scheduling
                 self.root.after(100, lambda: self.show_post_win_dialog(opponent_left_message))


        elif msg_type == 'full':
             # ... (full handling as before) ...
             messagebox.showerror("Server Full", "The server is full.", parent=self.root)
             self.on_closing(force_close=True) # Force close if server full after connect

        elif msg_type == 'error':
             # ... (error handling as before) ...
            error_message = msg.get('message', 'Unknown server error')
            print(f"Server Error: {error_message}")
            messagebox.showerror("Server Error", error_message, parent=self.root)


        # --- Handle Internal Messages ---
        elif msg_type == '_internal_error':
             error_payload = msg.get('payload', 'Unknown network error')
             print(f"Handling internal error: {error_payload}")
             # Check root again, as error might signal window closure issues
             if self.root and self.root.winfo_exists():
                  messagebox.showerror("Network Error", error_payload, parent=self.root)
                  self.disable_all_controls()
                  self.update_status("Network Error")
             else:
                 print(f"Network error occurred but GUI is not available: {error_payload}")
             # Don't force close here, let user close window or network manage itself

        elif msg_type == '_internal_closed':
             print("Handling internal connection closed.")
             # This message confirms the network layer finished its close sequence.
             # The GUI should already be shutting down via on_closing.
             if self.root and self.root.winfo_exists():
                 # Update status only if window somehow still exists
                 if not self.game_over: # Avoid overwriting win message
                     self.update_status("Disconnected")
                 self.disable_all_controls()
             # Ensure queue processing stops if it hasn't already
             self._gui_running = False
             print("Internal closed processed.")


        else:
             print(f"Warning: Received unknown message type: {msg_type}")

    # --- Other Methods ---
    # (Ensure initialize_game, _build_gui, show_post_win_dialog, reset_board_gui,
    #  on_char_select, is_variable_placement_valid, on_cell_click, highlight_winning_path,
    #  disable_all_controls, update_status are present and correct)
    # ... PASTE THE FULL IMPLEMENTATION OF THESE METHODS HERE ...
    def initialize_game(self, player_id, board_size):
        """Called by handle_server_message after receiving 'init' message."""
        # This now runs safely in the main thread via process_message_queue

        if not (4 <= board_size <= 30):
            # ... (error handling as before) ...
            errmsg = f"Unsupported board size: {board_size}x{board_size}\nClient supports 4x4 to 30x30."
            print(f"Error: {errmsg}")
            if self.root and self.root.winfo_exists():
                 messagebox.showerror("Error", errmsg, parent=self.root)
            self.on_closing(force_close=True) # Force close on bad init
            return

        self.player_id = player_id
        self.board_size = board_size
        print(f"Initialized as Player {self.player_id}, Board Size: {self.board_size}x{self.board_size}")
        self.board = [[EMPTY_CELL] * self.board_size for _ in range(self.board_size)]
        self.game_over = False
        self.current_turn = 'A'

        if not self.root or not self.root.winfo_exists():
             print("GUI window closed before initialization could complete.")
             self._gui_running = False # Stop queue processing
             # Network connection might already be closing or closed by NetworkClient
             # self.network.close() # Avoid double-closing if possible
             return

        self._build_gui()
        self._gui_initialized = True # Mark as initialized *after* building
        self.root.deiconify() # Show the window
        self.update_status() # Set initial status

    def _build_gui(self):
        """Sets up the Tkinter widgets after board size is known."""
        # Destroy existing widgets if rebuilding (e.g., after reset if we chose that approach)
        for widget in self.root.winfo_children():
            widget.destroy()

        self.root.title(f"Network Equation Game ({self.board_size}x{self.board_size}) - Player {self.player_id}")
        self.root.resizable(True, True)

        # --- Dynamic Font Size ---
        btn_font_size, char_font_size = GUI_SIZE_PRESETS[-1][1] # Default
        for threshold, (bfs, cfs) in GUI_SIZE_PRESETS:
            if self.board_size <= threshold:
                btn_font_size, char_font_size = bfs, cfs
                break
        btn_font = ('Consolas', btn_font_size, 'bold')
        char_font = ('Arial', char_font_size)
        char_font_bold = ('Arial', char_font_size, 'bold')
        print(f"Using board font size: {btn_font_size}, control font size: {char_font_size}")

        # --- Grid Layout ---
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        # Status Label
        self.status_label = tk.Label(self.root, text='', font=('Arial', 12,'bold'), pady=5)
        self.status_label.grid(row=0, column=0, sticky="ew", padx=10)

        # Board Frame
        self.board_frame = tk.Frame(self.root, bd=2, relief=tk.SUNKEN)
        self.board_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        self.cell_btns = [[None]*self.board_size for _ in range(self.board_size)]
        for r in range(self.board_size):
            self.board_frame.grid_rowconfigure(r, weight=1)
            for c in range(self.board_size):
                self.board_frame.grid_columnconfigure(c, weight=1)
                b = tk.Button(self.board_frame, text=EMPTY_CELL, font=btn_font,
                             command=lambda r=r, c=c: self.on_cell_click(r, c))
                b.config(highlightthickness=0)
                b.grid(row=r, column=c, sticky="nsew", padx=1, pady=1)
                self.cell_btns[r][c] = b

        # Control Frame
        self.ctrl_frame = tk.Frame(self.root, pady=10)
        self.ctrl_frame.grid(row=2, column=0, sticky="ew", padx=5)
        self.ctrl_frame.grid_columnconfigure(0, weight=1) # Center content

        ctrl_inner_frame = tk.Frame(self.ctrl_frame)
        ctrl_inner_frame.pack()

        char_panel_digits = tk.Frame(ctrl_inner_frame); char_panel_digits.pack(pady=2)
        char_panel_ops = tk.Frame(ctrl_inner_frame); char_panel_ops.pack()

        digits = [str(i) for i in range(10)]
        ops = list('+-*/=')
        # Make sure player_id exists before accessing PLAYERS
        my_var = PLAYERS.get(self.player_id, {}).get('symbol', '?') # Default symbol if ID unknown

        self.char_btns = {} # Clear previous buttons if any (e.g. during reset)
        for ch in digits:
            btn = tk.Button(char_panel_digits, text=ch, width=3, font=char_font,
                           command=lambda ch=ch: self.on_char_select(ch))
            btn.pack(side=tk.LEFT, padx=2)
            self.char_btns[ch]=btn

        for ch in ops:
            btn = tk.Button(char_panel_ops, text=ch, width=3, font=char_font_bold,
                           command=lambda ch=ch: self.on_char_select(ch))
            btn.pack(side=tk.LEFT, padx=2)
            self.char_btns[ch]=btn

        # Safely get player color/text color
        player_info = PLAYERS.get(self.player_id, {})
        fg_color = player_info.get('text_color', 'black')
        bg_color = player_info.get('color', 'SystemButtonFace')

        vbtn = tk.Button(char_panel_ops, text=my_var, width=3, font=char_font_bold,
                       fg=fg_color, bg=bg_color,
                       command=lambda v=my_var: self.on_char_select(v))
        vbtn.pack(side=tk.LEFT, padx=5)
        self.char_btns[my_var]=vbtn

    def show_post_win_dialog(self, end_game_text):
        """Shows the 'Play Again?' dialog after game ends."""
        # Check root window state before showing dialog
        if not self._gui_initialized or not self.root or not self.root.winfo_exists():
            print("Cannot show post-win dialog, GUI not available.")
            return

        # Define the action in a separate function
        def ask_action():
            # Re-check root window state inside the action
            if not self.root or not self.root.winfo_exists():
                print("Post-win dialog aborted, GUI closed before action.")
                return

            message_content = end_game_text + "\n\nPlay Again?"
            try:
                # Ensure parent is valid when showing messagebox
                parent_window = self.root if self.root.winfo_exists() else None
                if not parent_window: return

                answer = messagebox.askyesno("Game Over", message_content, parent=parent_window)

                # Re-check root window state after messagebox (user might close it)
                if not self.root or not self.root.winfo_exists(): return

                if answer:
                    print("Player chose to play again. Sending reset request...")
                    reset_request_data = {'type': 'reset_request'}
                    if not self.network.send_message(reset_request_data):
                         print("Failed to send reset request.")
                         # Show error only if root still exists
                         if self.root and self.root.winfo_exists():
                             messagebox.showerror("Error", "Failed to send reset request to server.", parent=self.root)
                             self.on_closing(force_close=True) # Close client if can't send reset
                         else: # Just force close if window gone
                             self.on_closing(force_close=True)
                else:
                    print("Player chose not to play again. Closing client.")
                    self.on_closing(force_close=True) # Close the client window and connection
            except Exception as e:
                print(f"Error showing/handling post-win dialog: {e}")
                # Attempt to close gracefully even if dialog fails
                if self.root and self.root.winfo_exists():
                     self.on_closing(force_close=True)

        # This function is already called via root.after, so call action directly.
        ask_action()

    def reset_board_gui(self):
        """Resets the board state and GUI elements for a new game."""
        print("Client GUI resetting board...")
        if not self._gui_initialized or not self.root or not self.root.winfo_exists():
            print("Error: Cannot reset GUI, not initialized or window closed.")
            return

        self.board = [[EMPTY_CELL] * self.board_size for _ in range(self.board_size)]
        self.current_turn = 'A' # Reset turn to Player A
        self.selected_char = None
        self.game_over = False   # <-- IMPORTANT: Reset game_over flag

        # Reset cell buttons appearance and state
        for r in range(self.board_size):
            for c in range(self.board_size):
                try:
                    if r < len(self.cell_btns) and c < len(self.cell_btns[r]):
                        btn = self.cell_btns[r][c]
                        if btn and btn.winfo_exists():
                            # Enable button, clear text, reset colors/highlight
                            btn.config(text=EMPTY_CELL, state=tk.NORMAL,
                                       bg='SystemButtonFace', fg='black',
                                       highlightthickness=0)
                except (tk.TclError, IndexError) as e:
                    print(f"Error resetting button ({r},{c}): {e}")

        # Reset character selection buttons
        for btn in self.char_btns.values():
            try:
                if isinstance(btn, tk.Button) and btn.winfo_exists():
                     # Enable button, reset appearance
                    btn.config(state=tk.NORMAL, relief=tk.RAISED, bg='SystemButtonFace')
            except tk.TclError: pass

        print("Client GUI board reset complete.")
        self.update_status() # Update status label for the new game state (should show Player A's turn)

    def on_char_select(self, char):
        """Handles clicking a character button."""
        # Add check for _gui_running
        if self.game_over or not self._gui_initialized or not self._gui_running: return

        # Reset visual state of all character buttons
        for btn in self.char_btns.values():
            # Add winfo_exists check here too
            if isinstance(btn, tk.Button) and btn.winfo_exists():
                 try: btn.config(relief=tk.RAISED, bg='SystemButtonFace')
                 except tk.TclError: pass # Ignore if destroyed during loop

        # Highlight the selected button
        if char in self.char_btns:
             try:
                 btn = self.char_btns[char]
                 # Add winfo_exists check
                 if isinstance(btn, tk.Button) and btn.winfo_exists():
                     btn.config(relief=tk.SUNKEN, bg='lightblue')
             except tk.TclError: pass

        self.selected_char = char
        self.update_status(f"Selected '{char}'")

    def is_variable_placement_valid(self, r, c):
        """Checks if placing player's variable at (r, c) is valid under the new rule."""
        if not self.player_id: return False # Cannot check if player ID unknown

        my_sym = PLAYERS[self.player_id]['symbol']
        opponent_pid = 'B' if self.player_id == 'A' else 'A'
        opp_sym = PLAYERS[opponent_pid]['symbol']

        for dr in range(-1, 2): # -1, 0, 1
            for dc in range(-1, 2): # -1, 0, 1
                if dr == 0 and dc == 0: continue # Skip self

                # Check along this direction line
                for i in range(1, self.board_size):
                    nr, nc = r + i * dr, c + i * dc

                    if not (0 <= nr < self.board_size and 0 <= nc < self.board_size):
                        break # Reached edge

                    # Access self.board safely
                    check_char = EMPTY_CELL
                    try: # Add try-except for board access safety
                        check_char = self.board[nr][nc]
                    except IndexError:
                         print(f"IndexError accessing board at ({nr},{nc})")
                         break # Should not happen with board_size checks, but safety first

                    if check_char == opp_sym:
                        # Found opponent's variable along this line - INVALID
                        # print(f"Invalid placement: Found opponent '{opp_sym}' at ({nr},{nc}) along direction ({dr},{dc}) from ({r},{c})")
                        return False
                    elif check_char != EMPTY_CELL:
                        # Blocked by another piece (own var, number, op) - stop checking this line
                        break
                    # If EMPTY_CELL, continue checking further

        return True # Valid if no opponent variable found in any direction

    def on_cell_click(self, r, c):
        """Handles clicking a cell on the board."""
        # Add check for _gui_running
        if self.game_over or not self._gui_initialized or not self._gui_running: return

        if self.current_turn != self.player_id:
            messagebox.showwarning("Not Your Turn", "It's not your turn yet!", parent=self.root)
            return
        if not self.selected_char:
            messagebox.showwarning("No Selection", "Please select a character first.", parent=self.root)
            return
        try: # Check board access validity
            if self.board[r][c] != EMPTY_CELL:
                messagebox.showerror("Occupied", "This cell is already occupied.", parent=self.root)
                return
        except IndexError:
             print(f"Error: Clicked cell ({r},{c}) out of bounds for board size {self.board_size}")
             return

        # *** Apply NEW Variable Placement Rule ***
        my_sym = PLAYERS[self.player_id]['symbol']
        if self.selected_char == my_sym:
            if not self.is_variable_placement_valid(r, c):
                opp_sym = PLAYERS['B' if self.player_id == 'A' else 'A']['symbol']
                msg = (f"Cannot place variable '{my_sym}' here.\n"
                       f"A line extending from this cell already contains the opponent's variable ('{opp_sym}').")
                messagebox.showerror("Invalid Placement", msg, parent=self.root)
                return # Stop the move

        # --- Send Move via Network ---
        # Reset selected char button appearance visually
        if self.selected_char in self.char_btns:
             try:
                 btn = self.char_btns[self.selected_char]
                 # Add winfo_exists check
                 if isinstance(btn, tk.Button) and btn.winfo_exists():
                     btn.config(relief=tk.RAISED, bg='SystemButtonFace')
             except tk.TclError: pass

        # Prepare message dictionary
        move_data = {
            'type': 'move',
            'player': self.player_id,
            'row': r,
            'col': c,
            'char': self.selected_char
        }

        # Send using the network client
        if self.network.send_message(move_data):
            self.selected_char = None # Clear selection after successful send
            self.update_status("Move sent, waiting...")
        else:
            print("Failed to send move (handled by network callback).")


    def highlight_winning_path(self, coords):
        """Highlights the background and border of winning cells."""
        print(f"Highlighting winning path: {coords}")
        # Add check for _gui_initialized
        if not self._gui_initialized or not self.root or not self.root.winfo_exists(): return
        for r, c in coords:
            if 0 <= r < self.board_size and 0 <= c < self.board_size:
                try:
                    btn = self.cell_btns[r][c]
                    # Add winfo_exists check
                    if btn and btn.winfo_exists():
                        btn.config(bg=WIN_HIGHLIGHT_BG,
                                   highlightbackground=WIN_HIGHLIGHT_BORDER,
                                   highlightthickness=2)
                except (IndexError, tk.TclError) as e:
                     print(f"Warning: Error highlighting cell ({r},{c}): {e}")
            else:
                print(f"Warning: Winning coordinate ({r},{c}) out of bounds.")

    def disable_all_controls(self):
        """Disables board cells and character buttons, e.g., at game end or disconnect."""
        # Check if GUI is usable before proceeding
        # No need to check _gui_initialized here, as disable might be called during shutdown
        if not self.root or not self.root.winfo_exists():
             return
        print("Disabling game controls...") # Log only when actually disabling

        # Disable board cells
        for r in range(self.board_size):
             for c in range(self.board_size):
                  try:
                       if r < len(self.cell_btns) and c < len(self.cell_btns[r]):
                            btn = self.cell_btns[r][c]
                            if btn and btn.winfo_exists(): btn.config(state=tk.DISABLED)
                  except (tk.TclError, IndexError) as e:
                       print(f"Error disabling button ({r},{c}): {e}")

        # Disable character selection buttons
        for btn in self.char_btns.values():
            try:
                if isinstance(btn, tk.Button) and btn.winfo_exists(): btn.config(state=tk.DISABLED)
            except tk.TclError: pass


    def update_status(self, text=None):
        """Updates the status label text."""
        # Check if label exists and is usable
        if not self._gui_initialized or not self.status_label or not self.status_label.winfo_exists():
            return

        final_text = ""
        if text:
            final_text = text
        elif self.game_over:
            try:
                current_text = self.status_label.cget("text")
                if any(keyword in current_text for keyword in ["Win", "Wins", "Left", "Over", "Disconnected", "Error"]):
                     final_text = current_text
                else:
                     final_text = "Game Over"
            except tk.TclError:
                 final_text = "Game Over"
        elif not self.player_id:
             final_text = "Initializing..."
        else:
            cur_player_info = PLAYERS.get(self.current_turn)
            if cur_player_info:
                 turn_text = f"Turn: {cur_player_info['name']} ({cur_player_info['symbol']})"
                 if self.current_turn == self.player_id:
                     final_text = f"> {turn_text} <"
                 else:
                     final_text = turn_text
            else:
                 final_text = f"Waiting... (Turn: {self.current_turn})"

        try:
            self.status_label.config(text=final_text)
        except tk.TclError: pass
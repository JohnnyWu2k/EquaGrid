# game.py
# -*- coding: utf-8 -*-
"""
Main game logic entry point. Orchestrates Server/Client startup.

Usage:
  Server: python game.py server [port] [board_size]
  Client: python game.py client host port
"""
import sys

# Import constants (needed for main args processing)
from constants import DEFAULT_BOARD_SIZE

# Import classes needed for main execution
from network import GameServer
from gui import ClientGUI
# Note: We don't need to import from logic.py here, as main() doesn't call those functions.
# The logic functions are used by gui.py.


# --- Main Function (Entry Point) ---
def main():
    if len(sys.argv)<2:
        print("Usage:")
        print("  Server: python game.py server [port] [board_size]") # Updated command
        print("  Client: python game.py client host port")          # Updated command
        print("\nArgs:")
        print("  port: Server port (default 12345)")
        print("  board_size: Side length of the board (4-30, default 6)")
        print("  host: Server hostname or IP address")
        print("\nExamples:")
        print("  python game.py server 12345 15")
        print("  python game.py client localhost 12345")
        return

    mode=sys.argv[1].lower()
    if mode=='server':
        port=12345
        # Use DEFAULT_BOARD_SIZE from constants
        size=DEFAULT_BOARD_SIZE
        try:
            if len(sys.argv)>2: port=int(sys.argv[2])
            if len(sys.argv)>3: size=int(sys.argv[3])
            if not (4 <= size <= 30): # Enforce size limit
                 print(f"Error: Board size ({size}) must be between 4 and 30.")
                 return
        except ValueError: print("Error: Port and board_size must be integers."); return
        # Instantiate GameServer from network.py
        server = GameServer(host='0.0.0.0', port=port, board_size=size)
        server.start()
    elif mode=='client':
        if len(sys.argv)!=4: print("Client usage: python game.py client host port"); return
        host = sys.argv[2]; port_str = sys.argv[3]
        try:
            port = int(port_str)
            if not (1024 <= port <= 65535): print(f"Error: Port ({port}) invalid."); return
        except ValueError: print(f"Error: Port '{port_str}' is not a valid integer."); return
        # Instantiate ClientGUI from gui.py
        # ClientGUI internally imports necessary logic functions now
        client = ClientGUI(host, port_str) # Pass host/port for connection
        client.start() # Start the client (connect and run GUI)
    else: print(f"Error: Unknown mode '{mode}'. Use 'server' or 'client'.")


if __name__=='__main__':
    main()
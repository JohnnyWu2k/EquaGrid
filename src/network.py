# network.py (Simplified Version - Extended with Reset Handling)
# -*- coding: utf-8 -*-
"""
Handles network communication for both server and client.
*** Simplified Version - Reduced Error Handling - Added Reset Handling ***
"""
import socket
import threading
import json
import sys
import time

# Define constants directly or import from constants.py if preferred
# from constants import DEFAULT_BOARD_SIZE # Optional

DEFAULT_BOARD_SIZE = 6 # Example if not importing

# --- Server ---
class GameServer:
    def __init__(self, host='0.0.0.0', port=12345, board_size=DEFAULT_BOARD_SIZE):
        self.host = host
        self.port = port
        self.board_size = board_size # Keep board size for init message
        self.clients = []  # List of (socket, player_id) tuples
        self.lock = threading.Lock() # Basic lock for clients list
        self.server_socket = None
        self.running = False

    def start(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(2) # Listen for up to 2 connections
            print(f"Simplified Server started at {self.host}:{self.port}, board size {self.board_size}x{self.board_size}")
            self.running = True
        except OSError as e:
            print(f"Fatal Error: Could not bind to {self.host}:{self.port} - {e}")
            sys.exit(1)

        player_count = 0
        while self.running:
            try:
                client_socket, addr = self.server_socket.accept()

                with self.lock:
                    # Simple A/B assignment (limited robustness)
                    player_id = 'A' if player_count == 0 else 'B'
                    player_count += 1
                    # Allow more than 2 just for testing simplicity if needed
                    # if player_count > 2: player_id = f"Observer{player_count}"

                    print(f"Player {player_id} ({addr}) connected.")
                    self.clients.append((client_socket, player_id))

                # Start thread to handle client communication
                thread = threading.Thread(target=self.handle_client, args=(client_socket, player_id), daemon=True)
                thread.start()

            except OSError:
                print("Server socket closed, shutting down accept loop.")
                self.running = False # Exit loop if server socket closes
            except Exception as e:
                print(f"Error accepting connection: {e}")
                # Continue accepting if possible

        print("Server accept loop finished.")
        self.shutdown() # Attempt cleanup

    def handle_client(self, client_socket, player_id):
        # Send initial info (simplified)
        try:
            init_data = {'type': 'init', 'player': player_id, 'board_size': self.board_size}
            client_socket.sendall(json.dumps(init_data).encode())
            print(f"Sent init to {player_id}")
        except Exception as e:
            print(f"Error sending init to {player_id}: {e}")
            self.remove_client(client_socket, player_id)
            return

        # Receive and process/broadcast loop
        while self.running:
            try:
                data = client_socket.recv(4096)
                if not data:
                    print(f"Player {player_id} disconnected (no data).")
                    break # Exit loop

                # --- Decode JSON to determine message type ---
                try:
                    message = json.loads(data.decode())
                    msg_type = message.get('type')
                    print(f"Received from {player_id}: Type '{msg_type}'")

                    # --- Handle different message types ---
                    if msg_type == 'reset_request':
                        # Handle reset request
                        print(f"Reset request received from {player_id}")
                        # Broadcast a 'reset' message to all clients
                        reset_msg_dict = {'type': 'reset'}
                        reset_msg_bytes = json.dumps(reset_msg_dict).encode()
                        print("Broadcasting reset message...")
                        # Send reset to ALL clients (including the requester)
                        self.broadcast(reset_msg_bytes, sender_socket=None)

                    # --- Default: Echo other valid JSON messages ---
                    # (like 'move' or any other type the client might send)
                    else:
                        print(f"Echoing message type '{msg_type}' from {player_id}")
                        # Broadcast the original raw bytes to all clients
                        self.broadcast(data, sender_socket=None) # Echo to ALL

                except json.JSONDecodeError:
                     # If JSON is invalid, ignore it in this version
                     print(f"Invalid JSON from {player_id}, ignoring.")
                     # Optionally, you could still broadcast raw data if needed for debugging:
                     # self.broadcast(data, sender_socket=None)

            except ConnectionResetError:
                 print(f"Player {player_id} connection reset.")
                 break
            except socket.error as e:
                print(f"Socket error with {player_id}: {e}")
                break # Exit loop on socket error
            except Exception as e:
                print(f"Error handling client {player_id}: {e}")
                break # Exit loop on general error

        # Cleanup
        self.remove_client(client_socket, player_id)
        print(f"Handler for {player_id} finished.")

    def broadcast(self, message_bytes, sender_socket=None):
        """Sends raw bytes to all currently connected clients."""
        # We send to everyone including sender in this simplified echo/reset model
        with self.lock:
            # Create a copy for safe iteration
            current_clients = list(self.clients)

        # print(f"Broadcasting to {len(current_clients)} clients.") # Debug
        disconnected_clients = [] # Track clients failing during broadcast
        for client_sock, pid in current_clients:
            try:
                client_sock.sendall(message_bytes)
            except socket.error as e:
                print(f"Failed to broadcast to Player {pid}: {e}. Marking for removal.")
                disconnected_clients.append((client_sock, pid))
            except Exception as e:
                 print(f"Unknown broadcast error to {pid}: {e}. Marking for removal.")
                 disconnected_clients.append((client_sock, pid))

        # Remove clients that failed after iteration
        if disconnected_clients:
             print(f"Removing {len(disconnected_clients)} clients due to broadcast errors.")
             for sock, pid in disconnected_clients:
                  self.remove_client(sock, pid)


    def remove_client(self, client_socket, player_id):
        """Simplified client removal."""
        client_removed = False
        with self.lock:
            client_tuple = None
            for c in self.clients:
                 if c[0] == client_socket:
                      client_tuple = c
                      break
            if client_tuple:
                 try:
                     self.clients.remove(client_tuple)
                     print(f"Removed Player {player_id} from active list.")
                     client_removed = True
                 except ValueError:
                     # Already removed by another thread (e.g., concurrent broadcast errors)
                     pass

        # Close socket outside the lock only if it was actually found and removed from list
        # to prevent trying to close already closed/removed sockets
        if client_removed:
            try:
                print(f"Closing socket for {player_id}.")
                client_socket.close()
            except Exception as e:
                # Socket might already be closed due to error that triggered removal
                print(f"Error closing socket for {player_id} (might be already closed): {e}")
        # else:
            # print(f"Socket for {player_id} not found in list for removal/closing.")


    def shutdown(self):
        """Attempts to shut down the server and close connections."""
        if not self.running: # Prevent multiple shutdowns
            return
        print("Shutting down simplified server...")
        self.running = False # Signal loops to stop

        # 1. Close the main server socket to stop accepting new connections
        server_sock_to_close = self.server_socket
        self.server_socket = None # Mark as closed
        if server_sock_to_close:
             try:
                  print("Closing server listening socket...")
                  server_sock_to_close.close()
             except Exception as e:
                  print(f"Error closing server socket: {e}")

        # 2. Get a list of clients and clear the main list under lock
        with self.lock:
             clients_to_close = list(self.clients) # Make a copy
             self.clients = [] # Clear the list

        # 3. Close client connections (outside the lock)
        print(f"Closing {len(clients_to_close)} client connections...")
        for sock, pid in clients_to_close:
             try:
                  print(f"Closing connection for {pid}...")
                  # Optional: Send a shutdown message first?
                  # sock.sendall(json.dumps({'type':'server_shutdown'}).encode())
                  sock.close()
             except Exception as e:
                  print(f"Error closing client socket {pid} during shutdown: {e}")

        print("Server shutdown sequence complete.")


# --- Client Network Handling ---
# NetworkClient class remains unchanged from the previous simplified version
class NetworkClient:
    # ... (__init__, connect, listen_server, send_message methods as before) ...
    def __init__(self, host, port, message_callback, error_callback, close_callback):
        self.host = host
        self.port = int(port)
        self.sock = None
        self.listener_thread = None
        self.running = False
        # Callbacks provided by the GUI/main client logic
        self.handle_message = message_callback # Called when a message is received
        self.handle_error = error_callback     # Called on connection/socket errors
        self.handle_close = close_callback     # Called when connection is closed

    def connect(self):
        try:
            print(f"Connecting to {self.host}:{self.port}...")
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # Optional: Set a timeout for connect
            # self.sock.settimeout(5.0) # e.g., 5 seconds
            self.sock.connect((self.host, self.port))
            # self.sock.settimeout(None) # Reset timeout after connect
            print("Connected!")
            self.running = True
            self.listener_thread = threading.Thread(target=self.listen_server, daemon=True)
            self.listener_thread.start()
            return True
        except socket.timeout:
             print(f"Connection timed out to {self.host}:{self.port}")
             self.handle_error(f"Connection timed out")
             self.sock = None
             return False
        except socket.error as e:
            print(f"Connection error: {e}")
            self.handle_error(f"Could not connect: {e}") # Use simple error callback
            self.sock = None
            return False
        except Exception as e:
            print(f"Connect error: {e}")
            self.handle_error(f"Connect error: {e}")
            self.sock = None
            return False

    def listen_server(self):
        print("Listener thread started.")
        while self.running: # Loop controlled by self.running flag
            # Check socket existence before recv
            if not self.sock:
                 print("Listener: Socket is None, exiting.")
                 break
            try:
                data = self.sock.recv(4096)
                if not data:
                    # Server closed connection gracefully
                    if self.running: # Only report if not initiated by client close
                        print("Server disconnected gracefully.")
                    break # Exit loop

                # Process data if received
                try:
                    msg = json.loads(data.decode())
                    # Pass message via callback ONLY if still running
                    if self.running:
                        self.handle_message(msg)
                except json.JSONDecodeError:
                     if self.running: # Avoid logging if shutting down
                         print(f"Received invalid JSON data: {data.decode()[:100]}...")
                     # Ignore invalid JSON

            except ConnectionResetError:
                if self.running: print("Connection reset by server.")
                break # Exit loop
            except socket.timeout:
                 # If timeouts are enabled on recv, this allows checking self.running
                 # print("Socket recv timeout")
                 continue
            except socket.error as e:
                # Handle errors that indicate the socket is closed/unusable
                # errno 10004: Interrupted function call (often during shutdown)
                # errno 10038: Socket operation on non-socket (socket closed)
                # errno 10053: Software caused connection abort (local close)
                # errno 10054: Connection reset by peer (remote close)
                if self.running and e.errno not in [10004, 10038, 10053, 10054]:
                    print(f"Socket read error: {e} (errno={e.errno})")
                # else: print(f"Listener ignoring expected socket error during close: {e.errno}")
                break # Exit loop on socket error
            except Exception as e:
                 if self.running:
                    print(f"Unexpected error in listener: {e}")
                 break # Exit loop

        print("Listener thread finished.")
        # Check running flag *again* before calling handle_close
        # If self.running is False, it means close() was called from the main thread
        if self.running:
            print("Listener loop exited unexpectedly while still running.")
            self.running = False # Ensure flag is false now
            # We don't own the close sequence here, just notify GUI
            self.handle_close()

    def send_message(self, data_dict):
        # Check running state FIRST
        if not self.running or not self.sock:
            print("Error: Cannot send, not connected or not running.")
            return False
        try:
            message_bytes = json.dumps(data_dict).encode()
            self.sock.sendall(message_bytes)
            return True
        except socket.error as e:
            print(f"Socket error sending message: {e}")
            # Assume fatal error on send failure, initiate close sequence
            if self.running: self.close() # Start the close process
            return False
        except Exception as e:
            print(f"Unknown error sending message: {e}")
            if self.running: self.close() # Start the close process
            return False

    def close(self):
        """Initiates the connection closing sequence."""
        # Check if already running the close sequence to prevent recursion
        if not self.running:
            # print("Close called but not running or already closing.") # Debug noise
            return

        print("Close sequence initiated...")
        self.running = False # 1. Signal listener thread FIRST

        # 2. Close the socket (handle potential errors)
        sock_to_close = self.sock
        self.sock = None # Prevent listener/sender using sock after this point
        if sock_to_close:
            print("Closing socket...")
            try:
                # Optional: Shutdown can help ensure buffer flushing, but adds complexity
                # sock_to_close.shutdown(socket.SHUT_RDWR)
                sock_to_close.close()
                print("Socket closed successfully.")
            except socket.error as e:
                 # Ignore specific errors if socket is already closed by other side/thread
                 if e.errno == 10038: # Socket operation on non-socket
                      print("Socket already closed (errno 10038).")
                 else:
                      print(f"Error during socket close: {e} (errno={e.errno})")
            except Exception as e:
                 print(f"Unexpected error during socket close: {e}")


        # 3. Call close handler (callback to GUI) AFTER attempting to close socket
        # This signals that the network layer has finished its part of the shutdown.
        print("Calling handle_close callback...")
        self.handle_close() # Notify GUI layer

        # 4. Optional: Wait briefly for listener thread (not strictly needed with daemon=True)
        # if self.listener_thread and threading.current_thread() != self.listener_thread:
        #    self.listener_thread.join(timeout=0.1) # Very short wait

        print("NetworkClient close sequence finished.")
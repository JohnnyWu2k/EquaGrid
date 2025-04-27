# Network Equation Game

A networked game where players take turns placing characters on a grid to form valid mathematical equations and win.

## Requirements

*   **Python:** Python 3.7 or newer is recommended. Make sure Python and `pip` (Python's package installer) are correctly installed and accessible from your command line/terminal.
*   **Libraries:** The game requires the `sympy` library for equation solving.

## Setup Instructions

Before running the game for the first time, you need to install the required Python library.

1.  **Open Command Prompt or Terminal:** Navigate to the directory where you saved the game files (`game.py`, `gui.py`, `logic.py`, `network.py`, `constants.py`, `requirements.txt`).
2.  **Run Setup Script:** Execute the `setup.bat` file by typing the following command and pressing Enter:

    ```bash
    setup.bat
    ```
    *   **What `setup.bat` does:** This batch file automatically runs the command `pip install -r requirements.txt`. It reads the `requirements.txt` file (which lists `sympy`) and installs that library using `pip`. You need an internet connection for this step.

## How to Play

The game requires one player to run the **Server** and both players (including the server host, if they are playing) to run a **Client**.

### Running the Server

The server waits for two clients to connect.

*   **Command:**
    ```bash
    python game.py server [port] [board_size]
    ```
*   **Arguments:**
    *   `port` (Optional): The network port the server will listen on. Defaults to `12345` if not specified. Must be an integer (e.g., 1024-65535).
    *   `board_size` (Optional): The side length of the square game board. Must be an integer between 4 and 30 (inclusive). Defaults to the value set in `constants.py` (currently seems to be 6, but check the file if needed) if not specified.
*   **Examples:**
    *   Run server on default port 12345 with default size:
        ```bash
        python game.py server
        ```
    *   Run server on port 50000 with a 15x15 board:
        ```bash
        python game.py server 50000 15
        ```
*   **Note:** If you are hosting the server, you might need to configure **port forwarding** on your router and adjust your **firewall** settings to allow other players on different networks to connect to the specified port.

### Running the Client

Each player needs to run the client to connect to the server and play the game.

*   **Command:**
    ```bash
    python game.py client host port
    ```
*   **Arguments:**
    *   `host`: The IP address or hostname of the computer running the server.
        *   If the server is on the *same* computer, use `localhost` or `127.0.0.1`.
        *   If the server is on *another computer on your local network*, use its local IP address (e.g., `192.168.0.132` as seen in your `config.txt`).
        *   If the server is on *another computer over the internet*, use the server's public IP address (the host player needs to find this, e.g., by searching "what is my ip" online).
    *   `port`: The port the server is running on. This *must match* the port used by the server. Must be an integer.
*   **Examples:**
    *   Connect to a server running on the same machine on port 12345:
        ```bash
        python game.py client localhost 12345
        ```
    *   Connect to a server running on another computer (e.g., `192.168.0.132`) on port 12345:
        ```bash
        python game.py client 192.168.0.132 12345
        ```
    *   Connect to a server running on a public IP address on port 50000:
        ```bash
        python game.py client <server_public_ip> 50000
        ```
        (Replace `<server_public_ip>` with the actual public IP address).

## Game Rules

1.  **Objective:** Be the first player to form a valid mathematical equation using your assigned variable ('x' for Player A, 'y' for Player B) along a continuous line (horizontal, vertical, or diagonal) on the board.
2.  **Players:** The first player to connect is Player A ('x'), the second is Player B ('y').
3.  **Turns:** Players take turns placing one character onto an empty cell on the board. Select the character (digit `0-9`, operator `+-*/=`, or your variable `x`/`y`) from the control panel, then click an empty cell on the board.
4.  **Winning Equation Requirements:** A winning line must:
    *   Be a continuous sequence of characters (no empty cells within).
    *   Have a length of at least `MIN_EQ_LEN` (defined in `constants.py`, typically 5).
    *   Contain exactly one equals sign (`=`).
    *   Contain the winning player's variable (`x` or `y`).
    *   *Not* contain the opponent's variable.
    *   Contain at least one arithmetic operator (`+`, `-`, `*`, `/`).
    *   Form a mathematically valid equation that has exactly one **integer** solution for the player's variable.
    *   The equation is considered valid if it reads correctly either **forwards** along the line *or* **backwards** along the line.
5.  **Variable Placement Rule:** You **cannot** place your variable (`x` or `y`) onto a cell if any straight line (horizontal, vertical, or diagonal) extending outwards from that cell already contains your *opponent's* variable symbol. This prevents trivial blockades.
6.  **Game End:**
    *   The game ends immediately when a player makes a move that completes a valid winning equation (either directly or by assisting the opponent).
    *   The game also ends if one player disconnects.
    *   After the game ends (win or disconnect), players are prompted to "Play Again?". If both players agree (by sending a reset request), the board resets for a new game. If either player chooses not to play again, the client closes.
import socket
import threading
import json
import os
from datetime import datetime
from game_manager import GameManager
from question_loader import load_questions

HOST = '0.0.0.0'  # To receive connections from any network interface (not just localhost)
PORT = 5000       # Port number for the server to listen on

# Simple logging function with timestamp
def log(message):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")

# Helper function to send a JSON message over a socket connection
def send_message(conn, data):
    # Package and send JSON message with a newline at the end
    try:
        conn.sendall((json.dumps(data) + '\n').encode('utf-8'))
    except Exception as e:
        log(f"Failed to send message: {e}")

# Function to handle communication with a single client
def handle_client(conn, addr, game_manager):
    player_id = None
    try:
        # Initial handshake to receive the player's name and register them
        data = conn.recv(1024).decode('utf-8')
        if not data:
            return

        init_message = json.loads(data)
        if init_message['type'] == 'connect':
            player_name = init_message['name']
            player_id = game_manager.register_player(conn, player_name)  # Register new player
            log(f"New connection from {addr}, assigned ID {player_id}")

            # Send welcome message to the player
            send_message(conn, {
                'type': 'welcome',
                'player_id': player_id,
                'message': f"Hello {player_name}! You are player {player_id}"
            })

        else:
            # If the first message is not a connect request, reject it
            send_message(conn, {
                'type': 'error',
                'message': 'First message must be a connect request.'
            })
            return

        # Main loop to receive and process messages from the client
        buffer = ""
        while True:
            part = conn.recv(4096).decode('utf-8')
            if not part:
                break  # Client disconnected

            buffer += part
            # Process messages line by line (newline-delimited)
            while '\n' in buffer:
                raw_message, buffer = buffer.split('\n', 1)
                if raw_message.strip():
                    try:
                        # Process message and send response
                        response = game_manager.process_message(player_id, raw_message)
                        if response:
                            send_message(conn, json.loads(response))
                    except json.JSONDecodeError:
                        # Handle case where the client sends invalid JSON
                        log(f"Invalid JSON from {addr}")
                        send_message(conn, {
                            'type': 'error',
                            'message': 'Invalid message format'
                        })

    except Exception as e:
        # Log unexpected errors
        log(f"Error with player {player_id}: {e}")
    finally:
        # Clean up: remove player and close connection
        if player_id:
            game_manager.remove_player(player_id)  # Remove player from game state
        conn.close()
        log(f"Connection with {addr} closed")

# Main server loop that listens for and handles incoming connections
def start_server():
    # Load quiz questions from JSON file
    base_dir = os.path.dirname(os.path.abspath(__file__))  # Current file's directory
    questions_path = os.path.join(base_dir, '..', 'data', 'questions.json')  # Path to questions.json

    questions = load_questions(questions_path)  # Load question data
    game_manager = GameManager(questions)       # Create game manager with loaded questions

    # Start the TCP server
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Allow quick reuse of the port
        s.bind((HOST, PORT))  # Bind the socket to the address and port
        s.listen()  # Start listening for connections
        log(f"Server started on {HOST}:{PORT}")

        while True:
            # Accept a new client connection
            conn, addr = s.accept()
            # Start a new thread to handle the connected client
            thread = threading.Thread(target=handle_client, args=(conn, addr, game_manager))
            thread.start()
            log(f"Active connections: {threading.active_count() - 1}")  # Show number of clients

# Entry point for the script
if __name__ == '__main__':
    start_server()  # Launch the server

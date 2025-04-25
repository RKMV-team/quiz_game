### server.py
import socket
import threading
from game_manager import GameManager
from question_loader import load_questions
from utils import log

HOST = '127.0.0.1'
PORT = 5000

game_manager = GameManager(load_questions('questions/questions.json'))

def handle_client(conn, addr):
    player_id = game_manager.register_player(conn)
    log(f"New connection from {addr}, assigned ID {player_id}")

    try:
        while True:
            data = conn.recv(1024).decode()
            if not data:
                break
            response = game_manager.process_message(player_id, data)
            if response:
                conn.sendall(response.encode())
    except Exception as e:
        log(f"Error with player {player_id}: {e}")
    finally:
        game_manager.remove_player(player_id)
        conn.close()
        log(f"Connection with player {player_id} closed")


def start_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        log(f"Server started on {HOST}:{PORT}")

        while True:
            conn, addr = s.accept()
            thread = threading.Thread(target=handle_client, args=(conn, addr))
            thread.start()


if __name__ == '__main__':
    start_server()
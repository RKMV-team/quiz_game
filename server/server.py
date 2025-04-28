import socket
import threading
import json
import os
from datetime import datetime
from game_manager import GameManager
from question_loader import load_questions

HOST = '0.0.0.0'  # Чтобы принимать подключения не только с localhost
PORT = 5000

def log(message):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")

def send_message(conn, data):
    """Упаковать и отправить JSON сообщение с '\n' в конце."""
    try:
        conn.sendall((json.dumps(data) + '\n').encode('utf-8'))
    except Exception as e:
        log(f"Failed to send message: {e}")

def handle_client(conn, addr, game_manager):
    player_id = None
    try:
        # Initial handshake
        data = conn.recv(1024).decode('utf-8')
        if not data:
            return

        init_message = json.loads(data)
        if init_message['type'] == 'connect':
            player_name = init_message['name']
            player_id = game_manager.register_player(conn, player_name)
            log(f"New connection from {addr}, assigned ID {player_id}")

            # Send welcome message
            send_message(conn, {
                'type': 'welcome',
                'player_id': player_id,
                'message': f"Hello {player_name}! You are player {player_id}"
            })

        else:
            send_message(conn, {
                'type': 'error',
                'message': 'First message must be a connect request.'
            })
            return

        # Main message loop
        buffer = ""
        while True:
            part = conn.recv(4096).decode('utf-8')
            if not part:
                break  # Client disconnected

            buffer += part
            while '\n' in buffer:
                raw_message, buffer = buffer.split('\n', 1)
                if raw_message.strip():
                    try:
                        response = game_manager.process_message(player_id, raw_message)
                        if response:
                            send_message(conn, json.loads(response))
                    except json.JSONDecodeError:
                        log(f"Invalid JSON from {addr}")
                        send_message(conn, {
                            'type': 'error',
                            'message': 'Invalid message format'
                        })

    except Exception as e:
        log(f"Error with player {player_id}: {e}")
    finally:
        if player_id:
            game_manager.remove_player(player_id)  # Убираем игрока из игры
        conn.close()
        log(f"Connection with {addr} closed")

def start_server():
    # Автоматически корректная загрузка questions.json
    base_dir = os.path.dirname(os.path.abspath(__file__))
    questions_path = os.path.join(base_dir, '..', 'data', 'questions.json')

    questions = load_questions(questions_path)
    game_manager = GameManager(questions)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen()
        log(f"Server started on {HOST}:{PORT}")

        while True:
            conn, addr = s.accept()
            thread = threading.Thread(target=handle_client, args=(conn, addr, game_manager))
            thread.start()
            log(f"Active connections: {threading.active_count() - 1}")

if __name__ == '__main__':
    start_server()

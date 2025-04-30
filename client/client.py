import socket
import threading
import json
import time
from typing import Dict

HOST = '127.0.0.1'
PORT = 5000


class QuizClient:
    def __init__(self):
        self.awaiting_join_response = False
        self.join_successful = False
        self.awaiting_room_creation = False
        self.room_created_successfully = False
        self.quiz_started = False
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.player_name = ""
        self.current_question = None
        self.time_limit = 0
        self.question_start_time = 0
        self.connected = False
        self.in_game = False
        self.cached_categories = []

    def connect(self, player_name: str) -> bool:
        try:
            self.socket.connect((HOST, PORT))
            self.player_name = player_name
            self.connected = True

            # Send first message "connect"
            self.send_command('connect', name=self.player_name)

            listener = threading.Thread(target=self.listen_for_messages)
            listener.daemon = True
            listener.start()

            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    def listen_for_messages(self):
        buffer = ""
        while self.connected:
            try:
                data = self.socket.recv(4096).decode('utf-8')
                if not data:
                    break

                buffer += data
                while '\n' in buffer:
                    message, buffer = buffer.split('\n', 1)
                    if message.strip():
                        try:
                            parsed_message = json.loads(message)
                            self.handle_server_message(parsed_message)
                        except json.JSONDecodeError:
                            print(f"⚠️ Invalid JSON received (ignoring): {message}")
            except Exception as e:
                print(f"⚠️ Connection error: {e}")
                self.connected = False
                break

    def handle_server_message(self, data: Dict):
        if data['type'] == 'welcome':
            print(data['message'])

        elif data['type'] == 'categories_list':
            self.cached_categories = data['categories']
            print("\n=== Available Categories ===")
            for idx, category in enumerate(data['categories']):
                print(f"{idx + 1}. {category['name']} - {category['description']}")
            print()

        elif data['type'] == 'rooms_list':
            print("\n=== Available Rooms ===")
            if not data['rooms']:
                print("No active rooms available.")
            else:
                for room in data['rooms']:
                    print(
                        f"ID: {room['room_id']} | Name: {room['name']} | Players: {room['players']} | "
                        f"Status: {room['status']} | Topics: {', '.join(room['categories'])}")
            print()

        elif data['type'] == 'room_created':
            print(f"\n✅ Room '{data['room_id']}' created!")
            print("Selected categories:", ", ".join(data['categories']))
            self.in_game = True
            self.room_created_successfully = True
            self.awaiting_room_creation = False
            threading.Thread(target=self.room_waiting_menu, args=(data['room_id'],), daemon=True).start()

        elif data['type'] == 'room_deleted':
            print("\n🚫 Room was deleted. Returning to main menu.")
            self.in_game = False

        elif data['type'] == 'joined_room':
            print(f"\n✅ Successfully joined room {data['room_id']}")
            self.in_game = True
            self.join_successful = True
            self.awaiting_join_response = False

        elif data['type'] == 'quiz_started':
            # todo: сервак отправляет это сообщение, надо логику прописать, а то тут вроде не прописаны действия на эту штуку
            pass

        elif data['type'] == 'question':
            self.current_question = data
            self.time_limit = data['time_limit']
            self.question_start_time = time.time()
            self.quiz_started = True

            print(f"\n--- New Question ({data['difficulty'].upper()}) ---")
            print(data['question'])
            for idx, option in enumerate(data['options']):
                print(f"{chr(65 + idx)}. {option}")
            print(f"\n⏳ You have {self.time_limit} seconds to answer!")

        elif data['type'] == 'answer_result':
            print("\n=== Result ===")
            print("✅ Correct!" if data['correct'] else "❌ Wrong!")
            print(f"Correct answer was: {data['correct_answer']}")
            print(f"Points earned: +{data['score']}")
            print(f"Your total score: {data['total_score']}")

        elif data['type'] == 'game_over':
            print("\n🏁 The game is over!")
            print("🏆 Final Scores:")
            scores = data.get('final_scores', {})
            for pid, score in scores.items():
                print(f"Player {pid}: {score} points")
            print("\nThanks for playing! 🎉")
            self.in_game = False
            self.current_question = None

        elif data['type'] == 'error':
            print(f"\n⚠️ Error: {data['message']}")
            self.join_successful = False
            self.awaiting_join_response = False

    def send_command(self, command: str, **kwargs):
        if not self.connected:
            print("❌ Not connected to server")
            return

        message = json.dumps({'type': command, **kwargs}) + '\n'
        try:
            self.socket.sendall(message.encode('utf-8'))
        except Exception as e:
            print(f"Failed to send command: {e}")
            self.connected = False
        return message

    def start_game(self):
        name = input("Enter your nickname: ").strip()
        if not name:
            print("❌ Nickname cannot be empty!")
            return

        if not self.connect(name):
            return

        # waiting to receive a welcome message before showing the menu
        time.sleep(0.2)  # a short pause so that the message can arrive and print out

        while True:
            if not self.in_game:
                print("\n=== Main Menu ===")
                print("1. View Categories")
                print("2. Create Room")
                print("3. View Rooms & Join")
                print("4. Exit")
                choice = input("Choose an option: ").strip()

                if choice == '1':
                    self.send_command('get_categories')
                    time.sleep(0.5)

                elif choice == '2':
                    self.create_room_flow()

                elif choice == '3':
                    self.send_command('list_rooms')
                    time.sleep(0.5)
                    self.join_room_flow()

                elif choice == '4':
                    print("Goodbye!")
                    break
                else:
                    print("Invalid choice.")
            else:
                if self.quiz_started:
                    self.play_game_loop()
                else:
                    time.sleep(0.1)

    def create_room_flow(self):
        self.send_command('get_categories')
        time.sleep(0.5)
        if self.in_game:
            print("❌ You already created or joined a room.")
            return

        room_name = input("\nEnter room name: ").strip()
        if not room_name:
            print("❌ Room name cannot be empty!")
            return

        print("Enter category numbers separated by commas (e.g., 1,2,3):")
        categories_input = input("> ").strip()

        try:
            selected_indices = [int(idx) - 1 for idx in categories_input.split(',') if idx.strip()]
            selected_categories = [self.cached_categories[idx]['name'] for idx in selected_indices]

            self.awaiting_room_creation = True
            self.send_command('create_room',
                              room_name=room_name,
                              categories=selected_categories)

            # Wait for the server response for up to 2 sec
            wait_start = time.time()
            while self.awaiting_room_creation and time.time() - wait_start < 2:
                time.sleep(0.1)

            if not self.room_created_successfully:
                return  # Error has printed by server
        except (ValueError, IndexError):
            print("❌ Invalid input. Please enter valid category numbers.")

    def join_room_flow(self):

        room_id = input("Enter room ID to join or 'Q' to quit: ").strip().upper()
        if room_id == "Q":
            return
        if not room_id:
            print("❌ Room ID cannot be empty!")
            return

        self.awaiting_join_response = True
        self.send_command('join_room', room_id=room_id)

        # Wait for the server response for up to 2 sec
        wait_start = time.time()
        while self.awaiting_join_response and time.time() - wait_start < 2:
            time.sleep(0.1)

        if not self.join_successful:
            return  # do not enter the menu, because the error has already been printed

    def room_waiting_menu(self, room_id: str):
        print(f"\n🕓 Waiting in room '{room_id}'...")
        print("Waiting for players to join (auto start at 5)...")

        while self.in_game:
            print("\n=== Waiting Menu ===")
            print("1. Delete Room")
            print("2. Start Quiz")
            choice = input("Choose an option: ").strip()

            if choice == '1':
                self.send_command('delete_room', room_id=room_id)
                time.sleep(0.5)
                self.in_game = False
                break
            elif choice == '2':
                self.send_command('start_quiz', room_id=room_id)
                # break
            elif choice == '':
                continue
            else:
                print("❌ Invalid option.")

    def play_game_loop(self):
        while self.in_game:
            if not self.current_question:
                self.send_command('get_question')
                time.sleep(0.2)
                continue

            while True:
                time_left = max(0, int(self.time_limit - (time.time() - self.question_start_time)))
                if time_left <= 0:
                    print("\n⏳ Time's up! Submitting no answer.")
                    self.send_command('answer', answer=" ", time_left=0)
                    self.current_question = None
                    break

                print(f"\r🕓 Time left: {int(time_left)}s ", end="")
                ans = input("\nYour answer (A/B/C/D) or 'Q' to quit: ").strip().upper()

                if ans == 'Q':
                    print("Exiting game...")
                    self.in_game = False
                    return

                if ans in ['A', 'B', 'C', 'D']:
                    self.send_command('answer', answer=ans, time_left=time_left)
                    self.current_question = None
                    break
                else:
                    print("❌ Invalid answer. Please choose A, B, C, or D.")


if __name__ == '__main__':
    client = QuizClient()
    client.start_game()

import socket
import threading
import json
import time
from typing import Dict

# Network configuration constants
HOST = '127.0.0.1'  # Default localhost address
PORT = 5000         # Default port number


class QuizClient:
    def __init__(self):
        """Initialize the QuizClient with default state and empty data structures."""
        # Connection and game state flags
        self.awaiting_join_response = False
        self.join_successful = False
        self.awaiting_room_creation = False
        self.room_created_successfully = False
        self.quiz_started = False
        self.connected = False
        self.in_game = False
        self.room_menu_active = False
        
        # Network components
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        # Player information
        self.player_name = ""
        
        # Question handling
        self.current_question = None
        self.time_limit = 0
        self.question_start_time = 0
        self.cached_categories = []
        self.waiting_for_next_question = False
        self.question_queue = []
        
        # Answer handling
        self.answer_lock = threading.Lock()
        self.answer_submitted = False
        self.last_question_result = None
        self.user_answer = None
        self.waiting_for_result = False
        
        # Thread management
        self.message_lock = threading.Lock()
        self.active_input_thread = None
        self.active_timer = None
        self.input_thread_active = False
        self.shutdown_flag = threading.Event()

    def connect(self, player_name: str) -> bool:
        """
        Establish connection to the server and start message listener thread.
        
        Args:
            player_name: Name of the player connecting to the server
            
        Returns:
            bool: True if connection was successful, False otherwise
        """
        try:
            # Establish TCP connection
            self.socket.connect((HOST, PORT))
            self.player_name = player_name
            self.connected = True
            
            # Send initial connection command
            self.send_command('connect', name=self.player_name)

            # Start background thread for receiving messages
            listener = threading.Thread(target=self.listen_for_messages)
            listener.daemon = True
            listener.start()

            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    def listen_for_messages(self):
        """
        Continuously listen for incoming messages from the server.
        Handles message buffering and JSON parsing.
        """
        buffer = ""
        while self.connected:
            try:
                # Receive data in chunks
                data = self.socket.recv(4096).decode('utf-8')
                if not data:
                    break

                # Add to buffer and process complete messages
                buffer += data
                while '\n' in buffer:
                    message, buffer = buffer.split('\n', 1)
                    if message.strip():
                        try:
                            # Parse and handle each complete JSON message
                            parsed_message = json.loads(message)
                            self.handle_server_message(parsed_message)
                        except json.JSONDecodeError:
                            print(f"⚠️ Invalid JSON received (ignoring): {message}")
            except Exception as e:
                print(f"⚠️ Connection error: {e}")
                self.connected = False
                break

    def handle_server_message(self, data: Dict):
        """
        Process incoming server messages based on their type.
        
        Args:
            data: Dictionary containing the parsed message data
        """
        with self.message_lock:
            # Handle welcome message
            if data['type'] == 'welcome':
                print(data['message'])

            # Handle categories list update
            elif data['type'] == 'categories_list':
                self.cached_categories = data['categories']
                print("\n=== Available Categories ===")
                for idx, category in enumerate(data['categories']):
                    print(f"{idx + 1}. {category['name']} - {category['description']}")
                print()

            # Handle rooms list update
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

            # Handle room creation success
            elif data['type'] == 'room_created':
                print(f"\n✅ Room '{data['room_id']}' created!")
                print("Selected categories:", ", ".join(data['categories']))
                self.in_game = True
                self.room_created_successfully = True
                self.awaiting_room_creation = False
                # Start room waiting menu in a new thread
                threading.Thread(target=self.room_waiting_menu, args=(data['room_id'],), daemon=True).start()

            # Handle successful room join
            elif data['type'] == 'joined_room':
                print(f"\n✅ Successfully joined room {data['room_id']}")
                self.in_game = True
                self.join_successful = True
                self.awaiting_join_response = False
                self.waiting_for_next_question = True

            # Handle quiz start notification
            elif data['type'] == 'quiz_started':
                print("\n🚀 Quiz is starting now!")
                self.quiz_started = True
                self.in_game = True
                self.current_question = None
                self.room_menu_active = False
                self.waiting_for_next_question = True

            # Handle incoming question
            elif data['type'] == 'question':
                self.question_queue.append(data)
                if not self.waiting_for_result:
                    self.process_question_queue()

            # Handle answer result
            elif data['type'] == 'answer_result':
                self.last_question_result = data
                self.waiting_for_result = False
                self.show_question_result(data)
                if self.question_queue:
                    question = self.question_queue.pop(0)
                    self.show_new_question(question)

            # Handle game over
            elif data['type'] == 'game_over':
                print("\n🏁 The game is over!")
                print("🏆 Final Scores:")
                scores = data.get('final_scores', {})
                for pid, score in scores.items():
                    print(f"Player {pid}: {score} points")
                print("\nThanks for playing! 🎉")
                self.reset_game_state()

            # Handle error messages
            elif data['type'] == 'error':
                print(f"\n⚠️ Error: {data['message']}")
                if self.awaiting_join_response:
                    self.join_successful = False
                    self.awaiting_join_response = False

    def process_question_queue(self):
        """Process the next question in the queue if not waiting for a result."""
        if self.question_queue and not self.waiting_for_result:
            question = self.question_queue.pop(0)
            self.show_new_question(question)

    def show_question_result(self, result):
        """Display the result of the previous question."""
        print("\n=== Result ===")
        print("✅ Correct!" if result['correct'] else "❌ Wrong!")
        print(f"Correct answer was: {result['correct_answer']}")
        print(f"Points earned: +{result['score']}")
        print(f"Your total score: {result['total_score']}\n")

    def show_new_question(self, question):
        """
        Display a new question and start the answer input process.
        
        Args:
            question: Dictionary containing question data
        """
        self.current_question = question
        self.time_limit = question['time_limit']
        self.question_start_time = time.time()
        self.answer_submitted = False
        self.user_answer = None
        self.waiting_for_result = True
        
        # Display question information
        print(f"\n--- New Question ({question['difficulty'].upper()}) ---")
        print(question['question'])
        for idx, option in enumerate(question['options']):
            print(f"{chr(65 + idx)}. {option}")
        print(f"\n⏳ You have {self.time_limit} seconds to answer!")
        
        # Start game loop for this question
        self.play_game_loop()

    def reset_game_state(self):
        """Reset all game state variables to their initial values."""
        with self.answer_lock:
            # Signal all threads to shutdown
            self.shutdown_flag.set()
            
            # Clean up active threads
            if self.active_input_thread and self.active_input_thread.is_alive():
                self.active_input_thread.join(timeout=0.5)
            
            if self.active_timer and self.active_timer.is_alive():
                self.active_timer.cancel()
                
            # Reset game state flags
            self.in_game = False
            self.current_question = None
            self.quiz_started = False
            self.room_menu_active = False
            self.waiting_for_next_question = False
            self.answer_submitted = False
            self.last_question_result = None
            self.question_queue = []
            self.user_answer = None
            self.waiting_for_result = False
            self.active_timer = None
            self.active_input_thread = None
            self.input_thread_active = False
            self.shutdown_flag.clear()

    def send_command(self, command: str, **kwargs):
        """
        Send a command to the server in JSON format.
        
        Args:
            command: The command type to send
            **kwargs: Additional arguments for the command
            
        Returns:
            The sent message string or None if failed
        """
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
        """Main game entry point that handles player connection and main loop."""
        name = input("Enter your nickname: ").strip()
        if not name:
            print("❌ Nickname cannot be empty!")
            return

        if not self.connect(name):
            return

        time.sleep(0.2)  # Brief pause for initial connection

        # Main game loop
        while True:
            if not self.in_game:
                self.main_menu()
            else:
                time.sleep(0.1)  # Small delay to prevent CPU overuse

    def main_menu(self):
        """Display and handle the main menu options."""
        print("\n=== Main Menu ===")
        print("1. View Categories")
        print("2. Create Room")
        print("3. View Rooms & Join")
        print("4. Exit")
        choice = input("Choose an option: ").strip()

        if choice == '1':
            self.send_command('get_categories')
            time.sleep(0.5)  # Wait for server response

        elif choice == '2':
            self.create_room_flow()

        elif choice == '3':
            self.send_command('list_rooms')
            time.sleep(0.5)  # Wait for server response
            self.join_room_flow()

        elif choice == '4':
            print("Goodbye!")
            self.socket.close()
            exit()
        else:
            print("Invalid choice.")

    def create_room_flow(self):
        """Handle the room creation process with user input."""
        self.send_command('get_categories')
        time.sleep(0.5)  # Wait for categories to load
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
            # Process category selection
            selected_indices = [int(idx) - 1 for idx in categories_input.split(',') if idx.strip()]
            selected_categories = [self.cached_categories[idx]['name'] for idx in selected_indices]

            self.awaiting_room_creation = True
            self.send_command('create_room',
                            room_name=room_name,
                            categories=selected_categories)

            # Wait for server response with timeout
            wait_start = time.time()
            while self.awaiting_room_creation and time.time() - wait_start < 2:
                time.sleep(0.1)

        except (ValueError, IndexError):
            print("❌ Invalid input. Please enter valid category numbers.")

    def join_room_flow(self):
        """Handle the room joining process with user input."""
        time.sleep(0.1)  # Small delay for UI stability
        room_id = input("Enter room ID to join or 'Q' to quit: ").strip().upper()
        if room_id == "Q":
            return
        if not room_id:
            print("❌ Room ID cannot be empty!")
            return

        self.send_command('join_room', room_id=room_id)
        self.awaiting_join_response = True

        # Wait for server response with timeout
        wait_start = time.time()
        while self.awaiting_join_response and time.time() - wait_start < 2:
            time.sleep(0.1)

    def room_waiting_menu(self, room_id: str):
        """
        Display and handle the waiting room menu.
        
        Args:
            room_id: The ID of the room being waited in
        """
        print(f"\n🕓 Waiting in room '{room_id}'...")
        print("Waiting for players to join (auto start at 5)...")

        self.room_menu_active = True
        while self.in_game and self.room_menu_active:
            print("\n=== Waiting Menu ===")
            print("1. Delete Room")
            print("2. Start Quiz")
            choice = input("Choose an option: ").strip()

            if not self.room_menu_active:
                break

            if choice == '1':
                self.send_command('delete_room', room_id=room_id)
                time.sleep(0.5)
                self.reset_game_state()
                break
            elif choice == '2':
                self.send_command('start_quiz', room_id=room_id)
                break
            elif choice == '':
                continue
            else:
                print("❌ Invalid option.")

    def play_game_loop(self):
        """Handle the question answering process with timer and input thread."""
        if not self.current_question:
            return

        self.shutdown_flag.clear()
        start_time = time.time()
        self.answer_submitted = False
        self.user_answer = None
        self.input_thread_active = True

        # Setup question timeout timer
        self.active_timer = threading.Timer(self.time_limit, self.handle_timeout)
        self.active_timer.daemon = True
        self.active_timer.start()

        # Start input thread for getting user answer
        self.active_input_thread = threading.Thread(target=self.get_user_input)
        self.active_input_thread.daemon = True
        self.active_input_thread.start()

        # Main waiting loop
        while time.time() - start_time < self.time_limit and not self.answer_submitted:
            if self.shutdown_flag.is_set():
                return
            time.sleep(0.1)

        # If answer was given, wait remaining time
        if self.user_answer is not None:
            remaining_time = max(0, self.time_limit - (time.time() - start_time))
            if remaining_time > 0:
                time.sleep(remaining_time)
            print("\n⏳ Time's up! Submitting answer.")

        # Submit answer to server
        with self.answer_lock:
            if not self.answer_submitted:
                self.handle_timeout()
            elif self.user_answer is not None:
                time_left = max(0, self.time_limit - (time.time() - start_time))
                self.send_command('answer', answer=self.user_answer, time_left=time_left)

        # Cleanup threads
        self.input_thread_active = False
        if self.active_timer and self.active_timer.is_alive():
            self.active_timer.cancel()
        if self.active_input_thread and self.active_input_thread.is_alive():
            self.active_input_thread.join(timeout=0.1)

    def get_user_input(self):
        """Thread function to get user input for the current question."""
        while self.input_thread_active and not self.answer_submitted:
            try:
                ans = input("Your answer (A/B/C/D) or 'Q' to quit: ").strip().upper()
                
                if self.shutdown_flag.is_set():
                    return

                if ans == 'Q':
                    print("Exiting game...")
                    self.send_command('leave_room')
                    self.reset_game_state()
                    return

                if ans in ['A', 'B', 'C', 'D']:
                    with self.answer_lock:
                        if not self.answer_submitted:
                            self.user_answer = ans
                            self.answer_submitted = True
                            return
                else:
                    print("❌ Invalid answer. Please choose A, B, C, or D.")
            except Exception as e:
                if not self.shutdown_flag.is_set():
                    print(f"Input error: {e}")
                return

    def handle_timeout(self):
        """Handle the case when question time runs out without an answer."""
        with self.answer_lock:
            if not self.answer_submitted:
                print("\n⏳ Time's up! Submitting no answer.")
                self.answer_submitted = True
                self.send_command('answer', answer=" ", time_left=0)


if __name__ == '__main__':
    # Create and start client instance
    client = QuizClient()
    try:
        client.start_game()
    except KeyboardInterrupt:
        print("\nClosing client...")
        client.socket.close()
    except Exception as e:
        print(f"Unexpected error: {e}")
        client.socket.close()

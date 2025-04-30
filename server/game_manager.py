import json
import random
import threading
import time
from datetime import datetime
from typing import Dict, List, Set


# Helper function to log messages with timestamp
def log(message):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")


class GameManager:
    def __init__(self, questions: Dict[str, Dict]):
        # Initialize question bank and containers for players, rooms, and used questions
        self.questions = questions
        self.players: Dict[str, Dict] = {}
        self.rooms: Dict[str, Dict] = {}
        self.lock = threading.Lock()  # Ensures thread-safe access to shared data
        self.used_questions: Dict[str, Set[str]] = {}  # Tracks used questions per room

    # Registers a new player and assigns a unique player ID
    def register_player(self, conn, player_name: str) -> str:
        with self.lock:
            player_id = 1
            while str(player_id) in self.players.keys():
                player_id += 1
            player_id = str(player_id)
            self.players[player_id] = {
                'conn': conn,
                'name': player_name,
                'score': 0,
                'room_id': None,
                'selected_categories': []
            }
            return player_id

    # Removes a player and updates their associated room if applicable
    def remove_player(self, player_id: str):
        with self.lock:
            player = self.players[player_id]
            if player["room_id"]:
                self.rooms[player["room_id"]]['players'].remove(player_id)
            del self.players[player_id]

    # Creates a new room and assigns the creating player as host
    def create_room(self, player_id: str, room_name: str, categories: List[str]) -> str:
        with self.lock:
            room_id = 1
            while str(room_id) in self.rooms.keys():
                room_id += 1
            room_id = str(room_id)
            self.rooms[room_id] = {
                'name': room_name,
                'players': [player_id],
                'game_started': False,
                'current_question': None,
                'categories': categories,
                'current_round': 0,
                'total_rounds': 10,
                'status': 'available'
            }
            self.used_questions[room_id] = set()
            self.players[player_id]['room_id'] = room_id
            self.players[player_id]['selected_categories'] = categories
            log(f"Creating room: {room_id}")
            return room_id

    # Adds a player to an existing room if it's not full or started
    def join_room(self, player_id: str, room_id: str) -> bool:
        with self.lock:
            if player_id in self.players and self.players[player_id]['room_id'] is None:
                if room_id in self.rooms and not self.rooms[room_id]['game_started'] \
                        and self.rooms[room_id]['status'] == 'available':
                    if len(self.rooms[room_id]['players']) < 5:
                        self.rooms[room_id]['players'].append(player_id)
                        self.players[player_id]['room_id'] = room_id

                        # Automatically start game when 5 players join
                        if len(self.rooms[room_id]['players']) == 5:
                            self.rooms[room_id]['game_started'] = True
                            self.rooms[room_id]['status'] = 'running'
                            log(f"Starting game in room: {room_id}")
                            self.broadcast(room_id, {'type': 'quiz_started'})
                            self.start_round_loop(room_id)

                        return True
            return False

    # Returns list of rooms that haven't started yet
    def list_rooms(self) -> List[Dict]:
        with self.lock:
            return [
                {'room_id': room_id, 'name': room['name'], 'players': len(room['players']),
                 'status': room['status'], 'categories': room['categories']}
                for room_id, room in self.rooms.items() if not room['game_started']
            ]

    # Returns all available quiz categories
    def get_available_categories(self) -> List[Dict]:
        return [{'name': name, 'description': data['description']} for name, data in self.questions.items()]

    # Deletes a room if the requesting player is the host
    def delete_room(self, player_id: str) -> bool:
        with self.lock:
            room_id = self.players[player_id]['room_id']
            if room_id and room_id in self.rooms:
                if player_id == self.rooms[room_id]['players'][0]:  # Host
                    for pid in self.rooms[room_id]['players']:
                        self.players[pid]['room_id'] = None
                    del self.rooms[room_id]
                    log(f"Deleting room: {room_id}")
                    return True
            return False

    # Force start the game if the requesting player is the host
    def force_start_game(self, player_id: str) -> bool:
        with self.lock:
            room_id = self.players[player_id]['room_id']
            if room_id and room_id in self.rooms:
                if player_id == self.rooms[room_id]['players'][0]:
                    self.rooms[room_id]['game_started'] = True
                    self.rooms[room_id]['status'] = 'running'
                    self.broadcast(room_id, {'type': 'quiz_started'})
                    self.start_round_loop(room_id)
                    return True
            return False

    # Manually starts the quiz in a specified room
    def start_quiz(self, room_id: str):
        with self.lock:
            if room_id in self.rooms:
                self.rooms[room_id]['game_started'] = True
                self.rooms[room_id]['status'] = 'running'
                log(f"Manually starting quiz in room: {room_id}")
                self.broadcast(room_id, {'type': 'quiz_started'})
        self.start_round_loop(room_id)

    # Starts a thread to handle the quiz rounds for a room
    def start_round_loop(self, room_id: str):
        def round_thread():
            for _ in range(self.rooms[room_id]['total_rounds']):
                question = self.get_random_question(room_id)
                if not question:
                    break

                with self.lock:
                    self.rooms[room_id]['current_question'] = question

                # Send question to all players in the room
                self.broadcast(room_id, {
                    'type': 'question',
                    'question': question['question'],
                    'options': question['options'],
                    'difficulty': question.get('difficulty', 'medium'),
                    'time_limit': 15
                })

                time.sleep(15)  # Wait for players to answer

                with self.lock:
                    self.rooms[room_id]['current_round'] += 1

            self.end_game(room_id)  # End game after all rounds

        threading.Thread(target=round_thread, daemon=True).start()

    # Allows player to leave a room
    def leave_room(self, player_id: str) -> bool:
        with self.lock:
            player = self.players.get(player_id)
            if not player or not player['room_id']:
                return False

            room_id = player['room_id']
            if room_id not in self.rooms:
                return False

            self.rooms[room_id]['players'].remove(player_id)
            self.players[player_id]['room_id'] = None
            self.players[player_id]['score'] = 0
            self.players[player_id]['selected_categories'] = []

            return True

    # Sends a message to all players in a room
    def broadcast(self, room_id: str, message: Dict):
        if room_id not in self.rooms:
            return
        for pid in self.rooms[room_id]['players']:
            try:
                self.players[pid]['conn'].sendall((json.dumps(message) + '\n').encode('utf-8'))
            except Exception as e:
                log(f"Broadcast failed for player {pid}: {e}")

    # Selects a random unused question from room's selected categories
    def get_random_question(self, room_id: str) -> Dict:
        with self.lock:
            if room_id not in self.rooms:
                return {}

            room = self.rooms[room_id]
            available_questions = []

            for category in room['categories']:
                for idx, question in enumerate(self.questions[category]['questions']):
                    qid = f"{category}_{idx}"
                    if qid not in self.used_questions[room_id]:
                        available_questions.append((category, idx, question))

            if not available_questions:
                self.used_questions[room_id] = set()  # Reset used questions if all used
                return self.get_random_question(room_id)

            category, idx, question = random.choice(available_questions)
            self.used_questions[room_id].add(f"{category}_{idx}")
            return question

    # Calculates score based on difficulty and remaining time
    def calculate_score(self, difficulty: str, time_left: float) -> int:
        base_scores = {'easy': 10, 'medium': 20, 'hard': 30}
        return base_scores.get(difficulty, 10) + int(time_left)

    # Processes incoming messages from a player
    def process_message(self, player_id: str, data: str) -> str:
        try:
            message = json.loads(data)
            response = {'type': 'error', 'message': 'Unknown command'}

            if message['type'] == 'get_categories':
                response = {'type': 'categories_list', 'categories': self.get_available_categories()}

            elif message['type'] == 'start_quiz':
                room_id = message.get('room_id')
                if not room_id:
                    return json.dumps({'type': 'error', 'message': 'Room ID is required'})
                self.start_quiz(room_id)
                return json.dumps({'type': 'quiz_started', 'room_id': room_id})

            elif message['type'] == 'create_room':
                room_id = self.create_room(player_id, message['room_name'], message['categories'])
                response = {'type': 'room_created', 'room_id': room_id, 'categories': message['categories']}

            elif message['type'] == 'list_rooms':
                response = {'type': 'rooms_list', 'rooms': self.list_rooms()}

            elif message['type'] == 'join_room':
                room_id = message['room_id']
                if self.join_room(player_id, room_id):
                    response = {'type': 'joined_room', 'room_id': room_id}
                else:
                    response = {'type': 'error', 'message': 'Room not found or already started'}

            elif message['type'] == 'leave_room':
                # Processing the exit from the room
                if self.leave_room(player_id):
                    response = {'type': 'player_left', 'message': 'You have left the room.'}
                else:
                    response = {'type': 'error', 'message': 'Failed to leave the room.'}

            elif message['type'] == 'answer':
                player = self.players[player_id]
                room_id = player['room_id']

                with self.lock:
                    if room_id not in self.rooms:
                        return json.dumps({'type': 'error', 'message': 'Room deleted'})
                    question = self.rooms[room_id]['current_question']

                is_correct = (message['answer'].upper() == question['answer'])
                time_left = message.get('time_left', 0)

                score = self.calculate_score(question.get('difficulty', 'medium'), time_left) if is_correct else 0
                player['score'] += score

                response = {
                    'type': 'answer_result',
                    'correct': is_correct,
                    'correct_answer': question['answer'],
                    'score': score,
                    'total_score': player['score']
                }

            return json.dumps(response)

        except Exception as e:
            log(f"Error processing message: {e}")
            return json.dumps({'type': 'error', 'message': str(e)})

    # Ends the game, sends final scores, and cleans up the room
    def end_game(self, room_id: str):
        with self.lock:
            if room_id not in self.rooms:
                return
            final_scores = {pid: self.players[pid]['score'] for pid in self.rooms[room_id]['players']}
            for pid in self.rooms[room_id]['players']:
                try:
                    conn = self.players[pid]['conn']
                    conn.sendall(json.dumps({'type': 'game_over', 'final_scores': final_scores}).encode('utf-8') + b'\n')
                except Exception as e:
                    log(f"Failed to send game over to {pid}: {e}")
            
            # Cleaning players' status
            for pid in self.rooms[room_id]['players']:
                self.players[pid]['room_id'] = None
                self.players[pid]['score'] = 0
                self.players[pid]['selected_categories'] = []
            
            del self.rooms[room_id]
            log(f"Game ended. Room {room_id} deleted.")

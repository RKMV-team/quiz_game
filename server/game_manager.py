import json
import random
import threading
from datetime import datetime
from typing import Dict, List, Set


def log(message):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")


class GameManager:
    def __init__(self, questions: Dict[str, Dict]):
        self.questions = questions
        self.players: Dict[str, Dict] = {}
        self.rooms: Dict[str, Dict] = {}
        self.lock = threading.Lock()
        self.used_questions: Dict[str, Set[str]] = {}  # room_id: set(question_ids)

    def register_player(self, conn, player_name: str) -> str:
        with self.lock:
            player_id = str(len(self.players) + 1)
            while player_id in self.players:
                player_id += 1
            self.players[player_id] = {
                'conn': conn,
                'name': player_name,
                'score': 0,
                'room_id': None,
                'selected_categories': []
            }
            return player_id

    def remove_player(self, player_id):
        with self.lock:
            self.players.pop(player_id)

    def create_room(self, player_id: str, room_name: str, categories: List[str]) -> str:
        with self.lock:
            room_id = str(len(self.rooms) + 1)
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

    def join_room(self, player_id: str, room_id: str) -> bool:
        with (self.lock):
            if player_id in self.players and self.players[player_id]['room_id'] is None:
                if room_id in self.rooms and not self.rooms[room_id]['game_started'] and \
                        self.rooms[room_id]['status'] == 'available':
                    if len(self.rooms[room_id]['players']) < 5:
                        self.rooms[room_id]['players'].append(player_id)
                        self.players[player_id]['room_id'] = room_id

                        if len(self.rooms[room_id]['players']) == 5:
                            if room_id in self.rooms:
                                self.rooms[room_id]['game_started'] = True
                                self.rooms[room_id]['status'] = 'running'
                                log(f"Starting game in room: {room_id}")
                                self.broadcast(room_id, {
                                    'type': 'quiz_started'
                                })
                        return True
            return False

    def list_rooms(self) -> List[Dict]:
        with self.lock:
            return [
                {'room_id': room_id, 'name': room['name'], 'players': len(room['players']), 'status': room['status']}
                for room_id, room in self.rooms.items() if not room['game_started']]

    def get_available_categories(self) -> List[Dict]:
        return [{'name': name, 'description': data['description']}
                for name, data in self.questions.items()]

    def delete_room(self, player_id: str) -> bool:
        with self.lock:
            room_id = self.players[player_id]['room_id']
            if room_id and room_id in self.rooms:
                if player_id == self.rooms[room_id]['players'][0]:  # host check
                    for pid in self.rooms[room_id]['players']:
                        self.players[pid]['room_id'] = None
                    del self.rooms[room_id]
                    log(f"Deleting room: {room_id}")
                    return True
            return False

    def force_start_game(self, player_id: str) -> bool:
        with self.lock:
            room_id = self.players[player_id]['room_id']
            if room_id and room_id in self.rooms:
                if player_id == self.rooms[room_id]['players'][0]:  # host check
                    self.rooms[room_id]['game_started'] = True
                    self.rooms[room_id]['status'] = 'in_game'
                    return True
            return False

    def start_quiz(self, room_id: str):
        with self.lock:
            if room_id in self.rooms:
                self.rooms[room_id]['game_started'] = True
                self.rooms[room_id]['status'] = 'running'
                log(f"Manually starting quiz in room: {room_id}")
                self.broadcast(room_id, {
                    'type': 'quiz_started'
                })

    def broadcast(self, room_id: str, message: Dict):
        with self.lock:
            if room_id not in self.rooms:
                return
            for pid in self.rooms[room_id]['players']:
                conn = self.players[pid]['conn']
                try:
                    conn.sendall((json.dumps(message) + '\n').encode('utf-8'))
                except Exception as e:
                    log(f"Broadcast failed for player {pid}: {e}")

    def get_random_question(self, room_id: str) -> Dict:
        with self.lock:
            if room_id not in self.rooms:
                return {}

            room = self.rooms[room_id]
            available_questions = []

            for category in room['categories']:
                category_questions = self.questions[category]['questions']
                for idx, question in enumerate(category_questions):
                    question_id = f"{category}_{idx}"
                    if question_id not in self.used_questions[room_id]:
                        available_questions.append((category, idx, question))

            if not available_questions:
                self.used_questions[room_id] = set()
                return self.get_random_question(room_id)

            category, idx, question = random.choice(available_questions)
            question_id = f"{category}_{idx}"
            self.used_questions[room_id].add(question_id)
            return question

    def calculate_score(self, difficulty: str, time_left: float) -> int:
        base_scores = {'easy': 10, 'medium': 20, 'hard': 30}
        time_bonus = int(time_left)
        return base_scores.get(difficulty, 10) + time_bonus

    def process_message(self, player_id: str, data: str) -> str:
        try:
            message = json.loads(data)
            response = {'type': 'error', 'message': 'Unknown command'}

            if message['type'] == 'get_categories':
                response = {
                    'type': 'categories_list',
                    'categories': self.get_available_categories()
                }

            elif message['type'] == 'start_quiz':
                room_id = message.get('room_id')
                if not room_id:
                    return json.dumps({'type': 'error', 'message': 'Room ID is required to start quiz'})
                success = self.start_quiz(room_id)
                if success:
                    return json.dumps({'type': 'quiz_started', 'room_id': room_id})
                else:
                    return json.dumps({'type': 'error', 'message': 'Failed to start quiz'})

            elif message['type'] == 'create_room':
                selected_categories = message['categories']
                room_id = self.create_room(
                    player_id,
                    message['room_name'],
                    selected_categories
                )
                response = {
                    'type': 'room_created',
                    'room_id': room_id,
                    'categories': selected_categories
                }

            elif message['type'] == 'list_rooms':
                response = {
                    'type': 'rooms_list',
                    'rooms': self.list_rooms()
                }

            elif message['type'] == 'join_room':
                room_id = message['room_id']
                success = self.join_room(player_id, room_id)
                if success:
                    response = {
                        'type': 'joined_room',
                        'room_id': room_id
                    }
                else:
                    response = {
                        'type': 'error',
                        'message': 'Room does not exist or already started'
                    }

            elif message['type'] == 'get_question':
                room_id = self.players[player_id]['room_id']
                question = self.get_random_question(room_id)
                if not question:
                    return json.dumps({'type': 'error', 'message': 'Room no longer exists'})
                with self.lock:
                    self.rooms[room_id]['current_question'] = question
                response = {
                    'type': 'question',
                    'question': question['question'],
                    'options': question['options'],
                    'difficulty': question.get('difficulty', 'medium'),
                    'time_limit': 15
                }

            elif message['type'] == 'answer':
                player = self.players[player_id]
                room_id = player['room_id']
                with self.lock:
                    if room_id not in self.rooms:
                        return json.dumps({'type': 'error', 'message': 'Room was deleted'})
                    current_question = self.rooms[room_id]['current_question']

                is_correct = (message['answer'].upper() == current_question['answer'])
                time_left = message.get('time_left', 0)

                if is_correct:
                    score = self.calculate_score(
                        current_question.get('difficulty', 'medium'),
                        time_left
                    )
                    player['score'] += score
                else:
                    score = 0

                response = {
                    'type': 'answer_result',
                    'correct': is_correct,
                    'correct_answer': current_question['answer'],
                    'score': score,
                    'total_score': player['score'],
                    'difficulty': current_question.get('difficulty', 'medium')
                }

                with self.lock:
                    self.rooms[room_id]['current_round'] += 1
                    if self.rooms[room_id]['current_round'] >= self.rooms[room_id]['total_rounds']:
                        self.end_game(room_id)

            return json.dumps(response)

        except Exception as e:
            log(f"Error processing message: {e}")
            return json.dumps({'type': 'error', 'message': str(e)})

    def end_game(self, room_id: str):
        with self.lock:
            if room_id not in self.rooms:
                return
            final_scores = {pid: self.players[pid]['score'] for pid in self.rooms[room_id]['players']}
            for pid in self.rooms[room_id]['players']:
                try:
                    conn = self.players[pid]['conn']
                    conn.sendall(json.dumps({
                        'type': 'game_over',
                        'final_scores': final_scores
                    }).encode('utf-8') + b'\n')
                except Exception as e:
                    log(f"Failed to send game over to {pid}: {e}")
            del self.rooms[room_id]
            log(f"Game ended, room deleted: {room_id}")

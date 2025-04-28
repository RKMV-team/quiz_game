import json
import random
import threading
from typing import Dict, List, Set
from utils import log

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
            self.players[player_id] = {
                'conn': conn,
                'name': player_name,
                'score': 0,
                'room_id': None,
                'selected_categories': []
            }
            return player_id

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
                'total_rounds': 10
            }
            self.used_questions[room_id] = set()
            self.players[player_id]['room_id'] = room_id
            self.players[player_id]['selected_categories'] = categories
            return room_id

    def join_room(self, player_id: str, room_id: str) -> bool:
        with self.lock:
            if room_id in self.rooms and not self.rooms[room_id]['game_started']:
                if len(self.rooms[room_id]['players']) < 4:
                    self.rooms[room_id]['players'].append(player_id)
                    self.players[player_id]['room_id'] = room_id
                    return True
            return False

    def list_rooms(self) -> List[Dict]:
        with self.lock:
            return [{'room_id': room_id, 'name': room['name'], 'players': len(room['players'])}
                    for room_id, room in self.rooms.items() if not room['game_started']]

    def get_available_categories(self) -> List[Dict]:
        return [{'name': name, 'description': data['description']} 
                for name, data in self.questions.items()]

    def get_random_question(self, room_id: str) -> Dict:
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
                        'message': 'Room is full or already started'
                    }

            elif message['type'] == 'get_question':
                room_id = self.players[player_id]['room_id']
                question = self.get_random_question(room_id)
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

                self.rooms[room_id]['current_round'] += 1

                if self.rooms[room_id]['current_round'] >= self.rooms[room_id]['total_rounds']:
                    self.end_game(room_id)

            return json.dumps(response)

        except Exception as e:
            log(f"Error processing message: {e}")
            return json.dumps({'type': 'error', 'message': str(e)})

    def end_game(self, room_id: str):
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
        
        # После окончания игры можно удалить комнату
        with self.lock:
            if room_id in self.rooms:
                del self.rooms[room_id]

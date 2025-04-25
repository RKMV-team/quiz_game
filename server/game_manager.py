### game_manager.py
import json
import threading
import random
from utils import log

class GameManager:
    def __init__(self, questions):
        self.players = {}
        self.lock = threading.Lock()
        self.questions = questions
        self.current_question_index = 0

    def register_player(self, conn):
        with self.lock:
            player_id = str(len(self.players) + 1)
            self.players[player_id] = {
                'conn': conn,
                'score': 0
            }
            return player_id

    def remove_player(self, player_id):
        with self.lock:
            if player_id in self.players:
                del self.players[player_id]

    def get_current_question(self):
        return self.questions[self.current_question_index]

    def process_message(self, player_id, data):
        message = json.loads(data)
        response = {}

        if message['type'] == 'get_question':
            q = self.get_current_question()
            response = {
                'type': 'question',
                'question': q['question'],
                'options': q['options']
            }

        elif message['type'] == 'answer':
            answer = message['answer']
            correct = self.get_current_question()['answer']
            if answer == correct:
                self.players[player_id]['score'] += 1
                result = True
            else:
                result = False

            self.current_question_index = (self.current_question_index + 1) % len(self.questions)
            response = {
                'type': 'result',
                'correct': result,
                'score': self.players[player_id]['score']
            }

        return json.dumps(response)
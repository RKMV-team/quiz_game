### player.py
import json

class Player:
    def __init__(self, socket):
        self.socket = socket

    def request_question(self):
        message = {
            'type': 'get_question'
        }
        self.socket.sendall(json.dumps(message).encode())

    def send_answer(self, answer):
        message = {
            'type': 'answer',
            'answer': answer
        }
        self.socket.sendall(json.dumps(message).encode())
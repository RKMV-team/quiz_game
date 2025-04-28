import json

class Player:
    def __init__(self, socket, name: str):
        self.socket = socket
        self.name = name
        self.score = 0
        self.selected_categories = []

    def send(self, message_type: str, **kwargs):
        message = {'type': message_type, **kwargs}
        self.socket.sendall(json.dumps(message).encode())
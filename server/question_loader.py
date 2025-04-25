### question_loader.py
import json

def load_questions(path):
    with open(path, 'r') as f:
        return json.load(f)
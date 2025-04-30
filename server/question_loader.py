import json
from typing import Dict


def load_questions(path: str) -> Dict[str, Dict]:
    """
    Load questions from JSON
    Return dict: {category_name: {"description": str, "questions": List[Dict]}}
    """
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    categories = {}
    for category in data['categories']:
        categories[category['name']] = {
            'description': category['description'],
            'questions': category['questions']
        }
    return categories

import json
from typing import Dict

# Function to load quiz questions from a JSON file
def load_questions(path: str) -> Dict[str, Dict]:
    """
    Load questions from JSON
    Return dict: {category_name: {"description": str, "questions": List[Dict]}}
    """
    # Open the JSON file in read mode with UTF-8 encoding
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)  # Load the entire JSON content into a Python dictionary

    categories = {}  # Initialize an empty dictionary to store category-wise questions

    # Iterate over each category in the loaded data
    for category in data['categories']:
        # Map the category name to its description and list of questions
        categories[category['name']] = {
            'description': category['description'],
            'questions': category['questions']
        }

    # Return the structured dictionary containing categories and their questions
    return categories

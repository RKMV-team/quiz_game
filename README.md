# 🧠 Multiplayer Trivia Quiz Game (Python Sockets)

## 📌 Description
A multiplayer trivia quiz game implemented in Python using TCP sockets. Players connect to the server, receive questions, and answer them in turns. The server tracks scores and ensures turn-based play.

## 🗂️ Project Structure
```
quiz_game/ 
├── server/ 
│ ├── server.py 
│ ├── game_manager.py 
│ ├── question_loader.py 
│ └── utils.py 
├── client/ 
│ ├── client.py 
│ └── player.py 
├── questions/ 
│ └── questions.json ├── tests/ 
│ ├── test_game_manager.py 
│ └── test_question_loader.py 
├── requirements.txt 
└── README.md
```
## ▶️ How to Run

1. **Start the server:**
```python3 server/server.py```

2. **Start clients in separate terminals:**
```python3 client/client.py```

💡 Features
Supports multiple players

Turn-based gameplay

Score tracking

Questions loaded from a JSON file

Command-line interface (CLI)

Easy to extend (e.g., GUI, game rooms)

🧪 Running Tests
To run the tests:
```python3 -m unittest discover tests```

⚙️ Dependencies
This project only uses the standard Python 3.8+ library, no external dependencies are required.

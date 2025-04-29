import json
import unittest
from server.game_manager import GameManager


class FakeConn:
    def __init__(self):
        self.sent = []

    def sendall(self, data):
        self.sent.append(data)


class TestGameManager(unittest.TestCase):
    def setUp(self):
        self.sample_questions = [
            {"question": "Test Q1", "options": ["A", "B", "C", "D"], "answer": "A"},
            {"question": "Test Q2", "options": ["A", "B", "C", "D"], "answer": "B"}
        ]
        self.manager = GameManager(self.sample_questions)
        self.conn = FakeConn()
        self.player_id = self.manager.register_player(self.conn)

    def test_register_and_remove_player(self):
        self.assertIn(self.player_id, self.manager.players)
        self.manager.remove_player(self.player_id)
        self.assertNotIn(self.player_id, self.manager.players)

    def test_get_question(self):
        question = self.manager.get_current_question()
        self.assertEqual(question['question'], "Test Q1")

    def test_process_correct_answer(self):
        msg = json.dumps({"type": "answer", "answer": "A"})
        result = self.manager.process_message(self.player_id, msg)
        self.assertIn("correct", result)
        parsed = json.loads(result)
        self.assertTrue(parsed['correct'])
        self.assertEqual(parsed['score'], 1)

    def test_process_incorrect_answer(self):
        msg = json.dumps({"type": "answer", "answer": "D"})
        result = self.manager.process_message(self.player_id, msg)
        parsed = json.loads(result)
        self.assertFalse(parsed['correct'])
        self.assertEqual(parsed['score'], 0)


if __name__ == '__main__':
    unittest.main()

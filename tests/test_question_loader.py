import unittest
from server.question_loader import load_questions

class TestQuestionLoader(unittest.TestCase):
    def test_load_questions(self):
        questions = load_questions('questions/questions.json')
        self.assertIsInstance(questions, list)
        self.assertGreater(len(questions), 0)

        for q in questions:
            self.assertIn('question', q)
            self.assertIn('options', q)
            self.assertIn('answer', q)
            self.assertEqual(len(q['options']), 4)
            self.assertIn(q['answer'], ['A', 'B', 'C', 'D'])


if __name__ == '__main__':
    unittest.main()
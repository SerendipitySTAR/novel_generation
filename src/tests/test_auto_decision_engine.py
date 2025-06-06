import unittest
from src.core.auto_decision_engine import AutoDecisionEngine

class TestAutoDecisionEngine(unittest.TestCase):

    def setUp(self):
        self.engine = AutoDecisionEngine()

    def test_decide_basic_list(self):
        options = ["Option A", "Option B", "Option C"]
        decision = self.engine.decide(options)
        self.assertEqual(decision, "Option A", "Should select the first option")

    def test_decide_list_of_numbers(self):
        options = [10, 20, 30]
        decision = self.engine.decide(options, context={"reason": "numerical selection"})
        self.assertEqual(decision, 10, "Should select the first number")

    def test_decide_empty_list(self):
        options = []
        decision = self.engine.decide(options)
        self.assertIsNone(decision, "Should return None for empty list")

    def test_decide_single_option_list(self):
        options = [{"id": 1, "value": "Unique"}]
        decision = self.engine.decide(options)
        self.assertEqual(decision, {"id": 1, "value": "Unique"}, "Should select the single option")

    def test_decide_with_context(self):
        options = ["Contextual Choice"]
        # Context is logged by the engine, not changing behavior in this basic version
        decision = self.engine.decide(options, context={"user_preference": "action"})
        self.assertEqual(decision, "Contextual Choice")

if __name__ == '__main__':
    unittest.main()

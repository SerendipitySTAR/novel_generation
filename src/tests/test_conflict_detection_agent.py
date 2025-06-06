import unittest
from unittest.mock import MagicMock
import uuid # Ensure uuid is imported for the agent's potential use if not mocked

from src.agents.conflict_detection_agent import ConflictDetectionAgent
# from src.llm_abstraction.llm_client import LLMClient # Not strictly needed for these tests if LLMClient is mocked

# Mock LLMClient for tests
class MockLLMClientForConflictTest:
    def __init__(self):
        self.response_map = {} # Maps parts of prompts to responses
        self.default_response = "No clear conflicts found by mock LLM."

    def set_response_for_prompt_containing(self, text_fragment: str, response: str):
        self.response_map[text_fragment] = response

    def generate_text(self, prompt: str, max_tokens: int) -> str:
        # print(f"MockLLMClientForConflictTest: Received prompt: {prompt[:100]}...")
        for fragment, resp in self.response_map.items():
            if fragment in prompt:
                # print(f"MockLLMClientForConflictTest: Matched fragment '{fragment}', returning '{resp}'")
                return resp
        # print(f"MockLLMClientForConflictTest: No match, returning default: '{self.default_response}'")
        return self.default_response

class TestConflictDetectionAgent(unittest.TestCase):

    def setUp(self):
        self.mock_llm_client = MockLLMClientForConflictTest()
        self.agent = ConflictDetectionAgent(llm_client=self.mock_llm_client)

    def test_detect_conflicts_no_text(self):
        conflicts = self.agent.detect_conflicts("", 1)
        self.assertEqual(len(conflicts), 0)

    def test_detect_conflicts_heuristic_positive(self):
        # Test the built-in heuristic: "Character A is dead." and "Character A smiled."
        test_text = "Character A is dead. Later, Character A smiled."
        conflicts = self.agent.detect_conflicts(test_text, 1)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["type"], "Plot Contradiction")
        self.assertIn("Character A is stated to be dead", conflicts[0]["description"])

    def test_detect_conflicts_heuristic_negative(self):
        test_text = "Character A is alive and well. Character A smiled."
        conflicts = self.agent.detect_conflicts(test_text, 1)
        # Expecting 0 from heuristic, but LLM might find something if not configured.
        # The mock LLM will return "No clear conflicts found"
        self.mock_llm_client.default_response = "No clear conflicts found"
        conflicts_llm_check = self.agent.detect_conflicts(test_text, 1)
        found_non_heuristic = any(c['type'] != "Plot Contradiction" for c in conflicts_llm_check)

        is_heuristic_present = any(c['type'] == "Plot Contradiction" for c in conflicts_llm_check)
        self.assertFalse(is_heuristic_present, "Heuristic conflict should not be present")


    def test_detect_conflicts_llm_finds_conflict(self):
        test_text = "The sword was made of pure wood. It cut through steel easily."
        # Configure mock LLM to respond to a fragment of the text or a concept
        # The agent's current LLM prompt is generic, so we rely on the agent's
        # own simulated LLM logic for this test, or a smarter mock.
        # The agent's current conceptual LLM call looks for "magic suddenly failed"
        # Let's align with that or assume a more general mock response.

        self.mock_llm_client.default_response = "The wooden sword cutting steel is a physical inconsistency."

        conflicts = self.agent.detect_conflicts(test_text, 1, novel_context={"worldview_description":"fantasy setting"})

        llm_conflict_found = False
        for conflict in conflicts:
            if conflict["type"] == "Potential LLM-flagged Inconsistency":
                self.assertIn("wooden sword cutting steel", conflict["description"])
                llm_conflict_found = True
                break
        self.assertTrue(llm_conflict_found, "LLM should have flagged a conflict.")

    def test_detect_conflicts_llm_no_conflict(self):
        test_text = "The hero was brave and strong."
        self.mock_llm_client.default_response = "No clear conflicts found" # Explicitly set
        conflicts = self.agent.detect_conflicts(test_text, 1)

        llm_conflict_found = any(c["type"] == "Potential LLM-flagged Inconsistency" for c in conflicts)
        self.assertFalse(llm_conflict_found, f"LLM should not have found a conflict. Conflicts: {conflicts}")

    def test_detect_conflicts_no_llm_client(self):
        agent_no_llm = ConflictDetectionAgent(llm_client=None)
        test_text = "Character A is dead. Later, Character A smiled. This is a test."
        # Should still find heuristic conflict
        conflicts = agent_no_llm.detect_conflicts(test_text, 1)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["type"], "Plot Contradiction")

if __name__ == '__main__':
    unittest.main()

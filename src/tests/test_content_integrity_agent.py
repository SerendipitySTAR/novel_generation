import unittest
from unittest.mock import MagicMock, patch
import os
from src.agents.content_integrity_agent import ContentIntegrityAgent
from src.llm_abstraction.llm_client import LLMClient

# Mock LLMClient for tests where API key might not be present or to control responses
class MockLLMClient:
    def __init__(self, api_key=None): # Added api_key to match LLMClient constructor if needed
        self.dummy_response_text = ""

    def generate_text(self, prompt: str, max_tokens: int) -> str:
        # print(f"MockLLMClient: generate_text called with prompt starting: {prompt[:100]}")
        return self.dummy_response_text

    def set_dummy_response(self, text: str):
        self.dummy_response_text = text

class TestContentIntegrityAgent(unittest.TestCase):

    def setUp(self):
        self.mock_llm_client = MockLLMClient()
        self.agent = ContentIntegrityAgent(llm_client=self.mock_llm_client)
        self.dimensions = ContentIntegrityAgent.SCORING_DIMENSIONS

    def test_review_empty_content(self):
        review = self.agent.review_content("", "Empty Chapter")
        self.assertEqual(review["overall_score"], 0.0)
        self.assertIn("Empty content", review["error"])
        for dim_name, _ in self.dimensions:
            self.assertEqual(review["scores"].get(dim_name), 0)

    def test_parse_valid_response(self):
        response_text = """
Coherence: 8
Consistency: 7
Pacing: 9
Engagement: 8
Originality: 6
Detail: 7
Grammar: 9
Overall Score: 7.7
Justification: The chapter flows well and maintains consistency, with good pacing. Engagement is high. Originality is somewhat lacking but detail is adequate. Grammar is strong.
            """
        self.mock_llm_client.set_dummy_response(response_text)

        # _parse_review_response is a protected method, but we can test it indirectly
        # by calling review_content or test it directly for unit testing specific logic.
        # For this test, let's call the protected method for focused testing.
        parsed_review = self.agent._parse_review_response(response_text)

        self.assertEqual(parsed_review["scores"]["Coherence"], 8)
        self.assertEqual(parsed_review["scores"]["Consistency"], 7)
        self.assertEqual(parsed_review["scores"]["Pacing"], 9)
        self.assertEqual(parsed_review["scores"]["Engagement"], 8)
        self.assertEqual(parsed_review["scores"]["Originality"], 6)
        self.assertEqual(parsed_review["scores"]["Detail"], 7)
        self.assertEqual(parsed_review["scores"]["Grammar"], 9)
        self.assertEqual(parsed_review["overall_score"], 7.7)
        self.assertIn("flows well", parsed_review["justification"])

    def test_parse_response_missing_scores(self):
        response_text = """
Coherence: 8
Consistency:
Pacing: 9
Engagement: 7
Originality:
Detail: 6
Grammar: 8
Overall Score: 7.0
Justification: Some scores were missing in the LLM response.
            """
        self.mock_llm_client.set_dummy_response(response_text)
        parsed_review = self.agent._parse_review_response(response_text)

        self.assertEqual(parsed_review["scores"]["Coherence"], 8)
        self.assertIsNone(parsed_review["scores"]["Consistency"]) # Was missing
        self.assertEqual(parsed_review["scores"]["Pacing"], 9)
        self.assertEqual(parsed_review["overall_score"], 7.0) # As provided

        # Test overall score calculation if not provided in text
        response_text_no_overall = """
Coherence: 8
Pacing: 9
Engagement: 7
Detail: 6
Grammar: 8
Justification: Overall score not in text.
            """
        self.mock_llm_client.set_dummy_response(response_text_no_overall)
        parsed_review_no_overall = self.agent._parse_review_response(response_text_no_overall)
        # Sum = 8+9+7+6+8 = 38. Count = 5. Avg = 38/5 = 7.6
        self.assertEqual(parsed_review_no_overall["overall_score"], 7.6)


    def test_parse_response_malformed_scores(self):
        response_text = "Coherence: eight, Consistency: 7, Overall Score: 7, Justification: Malformed."
        self.mock_llm_client.set_dummy_response(response_text)
        parsed_review = self.agent._parse_review_response(response_text)
        self.assertIsNone(parsed_review["scores"]["Coherence"]) # "eight" is not a number
        self.assertEqual(parsed_review["scores"]["Consistency"], 7)
        self.assertEqual(parsed_review["overall_score"], 7)

    def test_review_content_llm_call(self):
        # This test ensures review_content calls the LLM client
        # and returns its parsed response.
        response_text = "Coherence: 9, Overall Score: 9, Justification: Perfect."
        self.mock_llm_client.set_dummy_response(response_text)

        # Patch the _parse_review_response to check its input and control its output
        # This is not strictly necessary if we trust the parser from other tests,
        # but can be useful. For now, we'll rely on the mock LLM.

        review = self.agent.review_content("Sample chapter text.", "Test Chapter")

        self.assertEqual(review["scores"].get("Coherence"), 9) # Check one score
        self.assertEqual(review["overall_score"], 9)
        self.assertEqual(review["justification"], "Perfect.")

    # Test with live LLM if API key is available and a flag is set (e.g., environment variable)
    # This is more of an integration test for the agent.
    @unittest.skipIf(not os.getenv("RUN_LIVE_AGENT_TESTS") or not os.getenv("OPENAI_API_KEY"),
                     "Skipping live LLM test for ContentIntegrityAgent. Set RUN_LIVE_AGENT_TESTS=true and OPENAI_API_KEY.")
    def test_review_content_live_llm(self):
        live_agent = ContentIntegrityAgent() # Uses real LLMClient
        sample_content = "This is a short piece of text for a live LLM review. It should be coherent and grammatically correct, but perhaps not very original or detailed."
        review = live_agent.review_content(sample_content, "Live Test Chapter")

        print(f"Live LLM Review: {review}") # Print for manual inspection during tests
        self.assertIsNotNone(review.get("overall_score"))
        self.assertTrue(1 <= review.get("overall_score", 0) <= 10)
        self.assertIsNotNone(review.get("justification"))
        self.assertTrue(len(review.get("scores", {})) == len(self.dimensions))


if __name__ == '__main__':
    unittest.main()

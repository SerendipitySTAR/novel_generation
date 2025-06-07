# src/tests/test_conflict_resolution_agent.py
import unittest
from unittest.mock import MagicMock, patch
import logging
import uuid # For asserting conflict_id format if needed

from src.agents.conflict_resolution_agent import ConflictResolutionAgent
from src.llm_abstraction.llm_client import LLMClient # For type hinting and mock base

# Suppress most logging output during tests unless specifically testing for it globally
# To see logs for a specific test, you might need to adjust this or use a debugger
logging.disable(logging.CRITICAL)

class TestConflictResolutionAgentFunctional(unittest.TestCase):

    def setUp(self):
        self.mock_llm_client = MagicMock(spec=LLMClient)
        self.db_name = "test_db_for_conflict_resolver_functional.db"

        # Patch the logger within the agent's module for controlled testing of log messages
        self.patcher = patch('src.agents.conflict_resolution_agent.logger')
        self.mock_logger = self.patcher.start()

        self.agent = ConflictResolutionAgent(llm_client=self.mock_llm_client, db_name=self.db_name)
        self.sample_novel_id = 1
        self.sample_novel_context = {"theme": "sci-fi", "style_preferences": "noir"} # Matched key from agent

    def tearDown(self):
        self.patcher.stop()

    def test_initialization(self):
        self.assertEqual(self.agent.llm_client, self.mock_llm_client)
        self.assertEqual(self.agent.db_name, self.db_name)
        self.mock_logger.info.assert_called_with(f"ConflictResolutionAgent initialized. DB name: {self.db_name}")

    # --- Tests for attempt_auto_resolve (Functional Version) ---
    def test_attempt_auto_resolve_llm_revises_excerpt(self):
        self.mock_logger.reset_mock()
        self.mock_llm_client.generate_text.return_value = "\"revised excerpt text\"" # LLM might add quotes

        chapter_text = "This is some text with a problematic excerpt here that needs fixing."
        conflicts = [{"conflict_id": "c1", "description": "Problem!", "excerpt": "problematic excerpt here"}]

        resolved_text = self.agent.attempt_auto_resolve(
            self.sample_novel_id, chapter_text, conflicts, self.sample_novel_context
        )

        self.mock_llm_client.generate_text.assert_called_once()
        prompt_arg = self.mock_llm_client.generate_text.call_args[0][0]
        self.assertIn("problematic excerpt here", prompt_arg)
        self.assertIn("This is some text with a problematic excerpt here that needs fixing.", prompt_arg) # Context window

        self.assertEqual(resolved_text, "This is some text with a revised excerpt text that needs fixing.")
        self.mock_logger.info.assert_any_call("Conflict 'Problem!' auto-resolved. Original: 'problematic excerpt here' -> Revised: 'revised excerpt text'")
        self.mock_logger.info.assert_any_call("ConflictResolutionAgent.attempt_auto_resolve: Text was modified.")


    def test_attempt_auto_resolve_llm_no_change(self):
        self.mock_logger.reset_mock()
        original_excerpt = "problematic excerpt here"
        self.mock_llm_client.generate_text.return_value = original_excerpt # LLM returns original

        chapter_text = "This is some text with a problematic excerpt here that needs fixing."
        conflicts = [{"conflict_id": "c1", "description": "Problem!", "excerpt": original_excerpt}]

        resolved_text = self.agent.attempt_auto_resolve(
            self.sample_novel_id, chapter_text, conflicts, self.sample_novel_context
        )
        self.assertEqual(resolved_text, chapter_text)
        self.mock_logger.info.assert_any_call(f"LLM suggested no change for conflict 'Problem!' with excerpt '{original_excerpt}'.")
        self.mock_logger.info.assert_any_call("ConflictResolutionAgent.attempt_auto_resolve: No changes made to the text after processing all conflicts.")

    def test_attempt_auto_resolve_llm_failure_for_one_conflict(self):
        self.mock_logger.reset_mock()
        original_text = "Conflict one is here. Conflict two is there."
        excerpt1 = "Conflict one is here"
        excerpt2 = "Conflict two is there"
        revised_excerpt2 = "Conflict two was resolved"

        conflicts = [
            {"conflict_id": "c1", "description": "Problem 1!", "excerpt": excerpt1},
            {"conflict_id": "c2", "description": "Problem 2!", "excerpt": excerpt2}
        ]

        # LLM fails for first, succeeds for second
        self.mock_llm_client.generate_text.side_effect = [
            Exception("LLM API Error"),
            f"\"{revised_excerpt2}\""
        ]

        resolved_text = self.agent.attempt_auto_resolve(
            self.sample_novel_id, original_text, conflicts, self.sample_novel_context
        )

        self.assertEqual(self.mock_llm_client.generate_text.call_count, 2)
        self.mock_logger.error.assert_any_call(f"Error during LLM call or processing for conflict 'Problem 1!': LLM API Error")
        self.mock_logger.info.assert_any_call(f"Conflict 'Problem 2!' auto-resolved. Original: '{excerpt2}' -> Revised: '{revised_excerpt2}'")
        self.assertEqual(resolved_text, f"Conflict one is here. {revised_excerpt2}.")
        self.mock_logger.info.assert_any_call("ConflictResolutionAgent.attempt_auto_resolve: Text was modified.")


    def test_attempt_auto_resolve_excerpt_not_found(self):
        self.mock_logger.reset_mock()
        chapter_text = "Some text."
        conflicts = [{"conflict_id": "c1", "description": "Problem!", "excerpt": "non_existent_excerpt"}]

        resolved_text = self.agent.attempt_auto_resolve(
            self.sample_novel_id, chapter_text, conflicts, self.sample_novel_context
        )
        self.assertEqual(resolved_text, chapter_text)
        self.mock_logger.warning.assert_any_call(f"Could not find original excerpt \"non_existent_excerpt\" in (potentially modified) chapter text for conflict: Problem!. Skipping this conflict's resolution.")

    def test_attempt_auto_resolve_no_llm_client(self):
        self.mock_logger.reset_mock()
        self.agent.llm_client = None
        chapter_text = "Some text."
        conflicts = [{"conflict_id": "c1", "description": "Problem!", "excerpt": "excerpt"}]

        resolved_text = self.agent.attempt_auto_resolve(
            self.sample_novel_id, chapter_text, conflicts, self.sample_novel_context
        )
        self.assertEqual(resolved_text, chapter_text)
        self.mock_logger.error.assert_called_with("LLMClient not available in ConflictResolutionAgent. Cannot attempt auto-resolve.")

    # --- Tests for suggest_revisions_for_human_review (Functional Version) ---
    def test_suggest_revisions_llm_provides_suggestions(self):
        self.mock_logger.reset_mock()
        self.mock_llm_client.generate_text.return_value = "Suggestion 1: Do this.\n---\nSuggestion 2: Or do that."
        conflicts_in = [{"conflict_id": "c1", "description": "Desc1", "excerpt": "Excerpt1"}]

        augmented_conflicts = self.agent.suggest_revisions_for_human_review(
            self.sample_novel_id, "Chapter text with Excerpt1 here.", conflicts_in, self.sample_novel_context
        )
        self.mock_llm_client.generate_text.assert_called_once()
        self.assertEqual(len(augmented_conflicts), 1)
        self.assertEqual(augmented_conflicts[0]["llm_suggestions"], ["Do this.", "Or do that."])
        self.assertNotIn("suggested_action_placeholder", augmented_conflicts[0]) # Check old stub field removed

    def test_suggest_revisions_llm_no_specific_suggestion(self):
        self.mock_logger.reset_mock()
        self.mock_llm_client.generate_text.return_value = "No specific rewrite suggestion for this excerpt."
        conflicts_in = [{"conflict_id": "c1", "description": "Desc1", "excerpt": "Excerpt1"}]

        augmented_conflicts = self.agent.suggest_revisions_for_human_review(
            self.sample_novel_id, "Chapter text with Excerpt1 here.", conflicts_in, self.sample_novel_context
        )
        self.assertEqual(len(augmented_conflicts), 1)
        self.assertEqual(augmented_conflicts[0]["llm_suggestions"], ["LLM indicated no specific rewrite suggestion needed for the excerpt."])

    def test_suggest_revisions_llm_empty_response(self):
        self.mock_logger.reset_mock()
        self.mock_llm_client.generate_text.return_value = "  " # Empty/whitespace
        conflicts_in = [{"conflict_id": "c1", "description": "Desc1", "excerpt": "Excerpt1"}]

        augmented_conflicts = self.agent.suggest_revisions_for_human_review(
            self.sample_novel_id, "Chapter text with Excerpt1 here.", conflicts_in, self.sample_novel_context
        )
        self.assertEqual(len(augmented_conflicts), 1)
        self.assertEqual(augmented_conflicts[0]["llm_suggestions"], ["LLM response did not yield parseable suggestions."])

    def test_suggest_revisions_no_excerpt_in_conflict(self):
        self.mock_logger.reset_mock()
        conflicts_in = [{"conflict_id": "c1", "description": "Desc1"}] # No excerpt

        augmented_conflicts = self.agent.suggest_revisions_for_human_review(
            self.sample_novel_id, "Chapter text.", conflicts_in, self.sample_novel_context
        )
        self.assertEqual(len(augmented_conflicts), 1)
        self.assertEqual(augmented_conflicts[0]["llm_suggestions"], ["No excerpt provided to base suggestions on."])
        self.mock_llm_client.generate_text.assert_not_called()


    def test_suggest_revisions_no_llm_client(self):
        self.mock_logger.reset_mock()
        self.agent.llm_client = None
        conflicts_in = [{"conflict_id": "c1", "description": "Desc1", "excerpt": "Excerpt1"}]

        augmented_conflicts = self.agent.suggest_revisions_for_human_review(
            self.sample_novel_id, "Chapter text.", conflicts_in, self.sample_novel_context
        )
        self.assertEqual(len(augmented_conflicts), 1)
        self.assertEqual(augmented_conflicts[0]["llm_suggestions"], ["LLM suggestions unavailable due to missing client."])

if __name__ == '__main__':
    logging.disable(logging.NOTSET) # Re-enable logging for manual test runs
    logging.basicConfig(level=logging.INFO)
    # If you want to see logs from the agent itself during tests:
    # logging.getLogger('src.agents.conflict_resolution_agent').setLevel(logging.INFO)
    unittest.main()

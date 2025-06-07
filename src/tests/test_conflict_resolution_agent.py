# src/tests/test_conflict_resolution_agent.py
import unittest
from unittest.mock import MagicMock, patch
import logging

# Make sure to import the agent from the correct path
from src.agents.conflict_resolution_agent import ConflictResolutionAgent
from src.llm_abstraction.llm_client import LLMClient # For type hinting and mock base

# Suppress most logging output during tests unless specifically testing for it
# logging.disable(logging.CRITICAL) # Keep disabled globally for automated runs
# Re-enable for specific tests if needed, or when running manually

class TestConflictResolutionAgent(unittest.TestCase):

    def setUp(self):
        self.mock_llm_client = MagicMock(spec=LLMClient)
        self.db_name = "test_db_for_conflict_resolver.db"
        # Patch the logger within the agent's module for controlled testing of log messages
        self.patcher = patch('src.agents.conflict_resolution_agent.logger')
        self.mock_logger = self.patcher.start()

        self.agent = ConflictResolutionAgent(llm_client=self.mock_llm_client, db_name=self.db_name)
        self.sample_novel_id = 1
        self.sample_chapter_text = "Original chapter text with potential issues."
        self.sample_conflicts = [
            {"conflict_id": "c1", "description": "Conflict 1 desc", "type": "Plot"},
            {"conflict_id": "c2", "description": "Conflict 2 desc", "type": "Character"},
        ]
        self.sample_novel_context = {"theme": "sci-fi", "style": "noir"}

    def tearDown(self):
        self.patcher.stop()

    def test_initialization(self):
        self.assertEqual(self.agent.llm_client, self.mock_llm_client)
        self.assertEqual(self.agent.db_name, self.db_name)
        self.mock_logger.info.assert_called_with(f"ConflictResolutionAgent initialized. DB name: {self.db_name}")

    def test_attempt_auto_resolve_no_conflicts(self):
        self.mock_logger.reset_mock() # Reset mock for clean assertion in this test
        resolved_text = self.agent.attempt_auto_resolve(
            self.sample_novel_id, self.sample_chapter_text, [], self.sample_novel_context
        )
        self.assertEqual(resolved_text, self.sample_chapter_text)
        # Check that the initial info log is called, but not the warning for stub.
        self.mock_logger.info.assert_called_with(f"Attempting auto-resolution for 0 conflicts in novel {self.sample_novel_id}.")
        self.mock_logger.warning.assert_not_called()


    def test_attempt_auto_resolve_with_conflicts_stub_behavior(self):
        self.mock_logger.reset_mock()
        resolved_text = self.agent.attempt_auto_resolve(
            self.sample_novel_id, self.sample_chapter_text, self.sample_conflicts, self.sample_novel_context
        )
        self.assertEqual(resolved_text, self.sample_chapter_text)
        self.mock_logger.info.assert_called_with(f"Attempting auto-resolution for {len(self.sample_conflicts)} conflicts in novel {self.sample_novel_id}.")
        self.mock_logger.warning.assert_called_once_with("Auto-resolution is a stub. Returning original text.")

    def test_suggest_revisions_for_human_review_no_conflicts(self):
        self.mock_logger.reset_mock()
        suggestions = self.agent.suggest_revisions_for_human_review(
            self.sample_novel_id, self.sample_chapter_text, [], self.sample_novel_context
        )
        self.assertEqual(suggestions, [])
        self.mock_logger.info.assert_called_with(f"Preparing 0 conflicts for human review for novel {self.sample_novel_id}.")


    def test_suggest_revisions_for_human_review_with_conflicts_stub_behavior(self):
        self.mock_logger.reset_mock()
        suggestions = self.agent.suggest_revisions_for_human_review(
            self.sample_novel_id, self.sample_chapter_text, self.sample_conflicts, self.sample_novel_context
        )
        self.assertEqual(len(suggestions), len(self.sample_conflicts))
        self.mock_logger.info.assert_called_with(f"Preparing {len(self.sample_conflicts)} conflicts for human review for novel {self.sample_novel_id}.")
        for i, suggestion in enumerate(suggestions):
            self.assertEqual(suggestion["conflict_id"], self.sample_conflicts[i]["conflict_id"])
            self.assertIn("suggested_action_placeholder", suggestion)
            self.assertEqual(suggestion["suggested_action_placeholder"], "Review this conflict.") # Matches current stub
            self.assertIn("status_for_review", suggestion)
            self.assertEqual(suggestion["status_for_review"], "pending_review")

if __name__ == '__main__':
    # logging.disable(logging.NOTSET) # Re-enable logging for manual test runs
    # logging.basicConfig(level=logging.INFO) # Ensure logger for the module is also enabled if needed
    # Example: logging.getLogger('src.agents.conflict_resolution_agent').setLevel(logging.INFO)
    unittest.main()

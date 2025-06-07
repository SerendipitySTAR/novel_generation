import unittest
from unittest.mock import patch, MagicMock, call
import os
import json

from src.orchestration.workflow_manager import WorkflowManager, NovelWorkflowState, UserInput, _should_retry_chapter
from src.persistence.database_manager import DatabaseManager
# It's good practice to mock the actual classes you intend to mock later
from src.agents.content_integrity_agent import ContentIntegrityAgent
from src.agents.conflict_detection_agent import ConflictDetectionAgent
from src.agents.context_synthesizer_agent import ContextSynthesizerAgent
from src.agents.chapter_chronicler_agent import ChapterChroniclerAgent
from src.agents.lore_keeper_agent import LoreKeeperAgent
from src.core.models import Chapter, PlotChapterDetail, Character, Outline, WorldView, Plot, Novel


class TestWorkflowManagerExtensions(unittest.TestCase):
    def setUp(self):
        self.db_name = "test_workflow_extensions.db"
        # Ensure a clean slate for each test
        if os.path.exists(self.db_name):
            os.remove(self.db_name)
        if os.path.exists(f"{self.db_name}-journal"): # SQLite specific
             os.remove(f"{self.db_name}-journal")

        self.db_manager = DatabaseManager(db_name=self.db_name)
        # Create tables, etc.
        self.db_manager.add_novel("Test Theme", "Test Style") # Novel ID 1
        self.db_manager.add_outline(1, "Test Outline") # Outline ID 1
        self.db_manager.add_worldview(1, "Test Worldview") # Worldview ID 1
        self.db_manager.add_plot(1, json.dumps([{"chapter_number": 1, "title": "Chapter 1 Plot"}])) # Plot ID 1
        self.db_manager.add_character(1, "Test Character", "A test character", "Protagonist", "{}", "{}", "{}", "{}", "{}", "{}", "{}", "{}", "{}", "{}", "{}", "{}") # Character ID 1

        self.user_input_data = {
            "theme": "Test Theme",
            "style_preferences": "Test Style",
            "chapters": 1, # Default to 1 chapter for simplicity, can override
            "words_per_chapter": 50, # Small for speed
            "auto_mode": False, # Default, override in tests
        }
        # Minimal state that might be needed by some nodes if not fully mocked
        self.base_initial_state_extras = {
            "novel_id": 1,
            "outline_id": 1,
            "worldview_id": 1,
            "plot_id": 1,
            "narrative_outline_text": "Test Outline",
            "selected_worldview_detail": {"world_name": "Test World", "core_concept": "Concept"},
            "detailed_plot_data": [{"chapter_number": 1, "title": "Chapter 1 Plot", "key_events_and_plot_progression": "Plot for Ch1", "characters_present": ["Test Character"]}],
            "characters": [{"character_id": 1, "name": "Test Character", "description": "A hero"}],
            "lore_keeper_initialized": True,
            "current_chapter_number": 1,
            "total_chapters_to_generate": 1,
            "generated_chapters": [],
            "loop_iteration_count": 0,
            "max_loop_iterations": 10, # Allow some loops
            "execution_count": 0,
            "current_chapter_retry_count": 0,
            "max_chapter_retries": 1,
            "current_chapter_original_content": None,
            "current_chapter_feedback_for_retry": None,
            "db_name": self.db_name,
        }


    def tearDown(self):
        # Close any open connections by the db_manager if necessary
        # For simple file DBs, removal is often enough
        del self.db_manager # Allow __del__ to close if it has one
        if os.path.exists(self.db_name):
            os.remove(self.db_name)
        if os.path.exists(f"{self.db_name}-journal"):
             os.remove(f"{self.db_name}-journal")

    def _get_minimal_state_for_chapter_loop_start(self, manager: WorkflowManager, user_input_dict: dict) -> NovelWorkflowState:
        """
        Helper to create a state dictionary that is plausible for being at the start of the chapter loop.
        This is a simplified initial state for the workflow's invoke method.
        """
        initial_state = NovelWorkflowState(
            user_input=UserInput(**user_input_dict),
            error_message=None,
            history=["Initial history"],
            novel_id=self.base_initial_state_extras["novel_id"],
            novel_data=Novel(id=1, theme="Test", style_preferences="Test"), # Mock
            narrative_outline_text=self.base_initial_state_extras["narrative_outline_text"],
            all_generated_outlines=None,
            outline_id=self.base_initial_state_extras["outline_id"],
            outline_data=Outline(id=1, novel_id=1, overview_text="Test Outline"), # Mock
            outline_review=None,
            all_generated_worldviews=None,
            selected_worldview_detail=self.base_initial_state_extras["selected_worldview_detail"],
            worldview_id=self.base_initial_state_extras["worldview_id"],
            worldview_data=WorldView(id=1, novel_id=1, description="Test Worldview"), # Mock
            plot_id=self.base_initial_state_extras["plot_id"],
            detailed_plot_data=self.base_initial_state_extras["detailed_plot_data"],
            plot_data=Plot(id=1, novel_id=1, plot_summary="..."), # Mock
            characters=self.base_initial_state_extras["characters"],
            lore_keeper_initialized=self.base_initial_state_extras["lore_keeper_initialized"],
            current_chapter_number=self.base_initial_state_extras["current_chapter_number"],
            total_chapters_to_generate=user_input_dict.get("chapters", 1),
            generated_chapters=list(self.base_initial_state_extras["generated_chapters"]), # mutable, so copy
            active_character_ids_for_chapter=None,
            current_plot_focus_for_chronicler=None,
            chapter_brief=None,
            db_name=self.db_name,
            current_chapter_review=None,
            current_chapter_quality_passed=None,
            current_chapter_conflicts=None,
            auto_decision_engine=manager.auto_decision_engine, # Use the one from the manager
            knowledge_graph_data=None,
            loop_iteration_count=self.base_initial_state_extras["loop_iteration_count"],
            max_loop_iterations=self.base_initial_state_extras["max_loop_iterations"],
            execution_count=self.base_initial_state_extras["execution_count"],
            current_chapter_retry_count=self.base_initial_state_extras["current_chapter_retry_count"],
            max_chapter_retries=user_input_dict.get("max_chapter_retries", self.base_initial_state_extras["max_chapter_retries"]),
            current_chapter_original_content=self.base_initial_state_extras["current_chapter_original_content"],
            current_chapter_feedback_for_retry=self.base_initial_state_extras["current_chapter_feedback_for_retry"]
        )
        return initial_state

    @patch('src.orchestration.workflow_manager.LoreKeeperAgent')
    @patch('src.orchestration.workflow_manager.ChapterChroniclerAgent')
    @patch('src.orchestration.workflow_manager.ContextSynthesizerAgent')
    @patch('src.orchestration.workflow_manager.ContentIntegrityAgent')
    def test_auto_mode_chapter_retry_successful_on_first_retry(self, MockContentIntegrity, MockContextSynthesizer, MockChapterChronicler, MockLoreKeeper):
        # --- Mocks Setup ---
        # ContentIntegrityAgent: Fail first, pass second
        mock_integrity_agent = MockContentIntegrity.return_value
        mock_integrity_agent.review_content.side_effect = [
            {"overall_score": 5.0, "justification": "Initial fail", "scores": {}}, # First call (fail)
            {"overall_score": 9.0, "justification": "Retry success", "scores": {}}  # Second call (pass)
        ]

        # ContextSynthesizerAgent: Return a basic brief
        mock_context_agent = MockContextSynthesizer.return_value
        mock_context_agent.generate_chapter_brief.return_value = "Chapter brief text."

        # ChapterChroniclerAgent: Return a mock chapter
        mock_chronicler_agent = MockChapterChronicler.return_value
        mock_chronicler_agent.generate_and_save_chapter.return_value = Chapter(id=1, novel_id=1, chapter_number=1, title="Test Chapter 1", content="Content", summary="Summary")

        # LoreKeeperAgent: Mock methods if they are called and matter
        mock_lore_keeper = MockLoreKeeper.return_value
        mock_lore_keeper.update_knowledge_base_with_chapter.return_value = None


        # --- Workflow Setup ---
        self.user_input_data["auto_mode"] = True
        self.user_input_data["chapters"] = 1
        # max_chapter_retries is 1 by default in initial_state

        manager = WorkflowManager(db_name=self.db_name, mode="auto")
        initial_state_dict = self._get_minimal_state_for_chapter_loop_start(manager, self.user_input_data)

        # --- Execute Segment of Workflow ---
        # We are interested in the chapter generation loop part
        # For simplicity, we'll manually call the relevant sequence of nodes
        # This avoids mocking the entire workflow graph and its conditions before the loop.

        # 1. context_synthesizer
        state_after_context1 = manager.workflow.nodes["context_synthesizer"]['callable'](initial_state_dict)
        # 2. chapter_chronicler
        state_after_chronicler1 = manager.workflow.nodes["chapter_chronicler"]['callable'](state_after_context1)
        # 3. content_integrity_review
        state_after_integrity1 = manager.workflow.nodes["content_integrity_review"]['callable'](state_after_chronicler1)
        # 4. should_retry_chapter
        retry_decision1 = manager.workflow.nodes["should_retry_chapter"]['callable'](state_after_integrity1)
        self.assertEqual(retry_decision1, "retry_chapter")
        self.assertEqual(state_after_integrity1["current_chapter_retry_count"], 1)
        self.assertIsNotNone(state_after_integrity1["current_chapter_original_content"])
        self.assertIsNotNone(state_after_integrity1["current_chapter_feedback_for_retry"])


        # Retry Attempt
        # 5. context_synthesizer (again for retry)
        state_after_context2 = manager.workflow.nodes["context_synthesizer"]['callable'](state_after_integrity1) # Pass state from decision
        # 6. chapter_chronicler (again for retry)
        state_after_chronicler2 = manager.workflow.nodes["chapter_chronicler"]['callable'](state_after_context2)
        # 7. content_integrity_review (again for retry)
        state_after_integrity2 = manager.workflow.nodes["content_integrity_review"]['callable'](state_after_chronicler2)
        # 8. should_retry_chapter (again for retry)
        retry_decision2 = manager.workflow.nodes["should_retry_chapter"]['callable'](state_after_integrity2)


        # --- Assertions ---
        self.assertEqual(retry_decision2, "proceed_to_kb_update") # Should pass now
        self.assertTrue(state_after_integrity2["current_chapter_quality_passed"])
        self.assertEqual(state_after_integrity2["current_chapter_retry_count"], 0) # Reset after proceeding

        # Check if ContextSynthesizerAgent was called with feedback on the second attempt
        # The feedback is appended to the brief.
        calls_to_context_brief = mock_context_agent.generate_chapter_brief.call_args_list
        self.assertEqual(len(calls_to_context_brief), 2)
        # The first call's brief should be simple. The second brief is based on state_after_integrity1, which now has feedback.
        # The test for execute_context_synthesizer_agent already checks if feedback is appended.
        # Here we check that the state passed to the second call to context_synthesizer had the feedback.
        self.assertIn("Initial fail", state_after_integrity1.get("current_chapter_feedback_for_retry",""))


        # Check if ChapterChroniclerAgent was called twice for the first chapter
        self.assertEqual(mock_chronicler_agent.generate_and_save_chapter.call_count, 2)

        # Check if the chapter that initially failed is eventually added
        # This would typically happen after lore_keeper_update_kb and increment_chapter_number
        # For this test, state_after_integrity2 should have the successful chapter in generated_chapters
        self.assertEqual(len(state_after_integrity2["generated_chapters"]), 1)
        self.assertEqual(state_after_integrity2["generated_chapters"][0]["title"], "Test Chapter 1")

    @patch('src.orchestration.workflow_manager.LoreKeeperAgent')
    @patch('src.orchestration.workflow_manager.ChapterChroniclerAgent')
    @patch('src.orchestration.workflow_manager.ContextSynthesizerAgent')
    @patch('src.orchestration.workflow_manager.ContentIntegrityAgent')
    def test_auto_mode_chapter_retry_exhausted(self, MockContentIntegrity, MockContextSynthesizer, MockChapterChronicler, MockLoreKeeper):
        mock_integrity_agent = MockContentIntegrity.return_value
        mock_integrity_agent.review_content.return_value = {"overall_score": 4.0, "justification": "Consistent fail", "scores": {}} # Always fail

        mock_context_agent = MockContextSynthesizer.return_value
        mock_context_agent.generate_chapter_brief.return_value = "Chapter brief text."

        mock_chronicler_agent = MockChapterChronicler.return_value
        # Let's say each attempt generates a slightly different chapter object for realism if needed, but same content for simplicity
        mock_chronicler_agent.generate_and_save_chapter.side_effect = [
            Chapter(id=1, novel_id=1, chapter_number=1, title="Test Chapter 1 v1", content="Content v1", summary="Summary v1"),
            Chapter(id=2, novel_id=1, chapter_number=1, title="Test Chapter 1 v2", content="Content v2", summary="Summary v2")
        ]

        self.user_input_data["auto_mode"] = True
        self.user_input_data["chapters"] = 1
        max_retries_val = 1 # Test with 1 max retry

        manager = WorkflowManager(db_name=self.db_name, mode="auto")
        initial_state_dict = self._get_minimal_state_for_chapter_loop_start(manager, self.user_input_data)
        initial_state_dict["max_chapter_retries"] = max_retries_val


        # Attempt 1 (Original)
        state = manager.workflow.nodes["context_synthesizer"]['callable'](initial_state_dict)
        state = manager.workflow.nodes["chapter_chronicler"]['callable'](state)
        state = manager.workflow.nodes["content_integrity_review"]['callable'](state)
        retry_decision = manager.workflow.nodes["should_retry_chapter"]['callable'](state) # current_retry_count becomes 1

        self.assertEqual(retry_decision, "retry_chapter")
        self.assertEqual(state["current_chapter_retry_count"], 1)

        # Attempt 2 (Retry 1)
        state = manager.workflow.nodes["context_synthesizer"]['callable'](state)
        state = manager.workflow.nodes["chapter_chronicler"]['callable'](state)
        state = manager.workflow.nodes["content_integrity_review"]['callable'](state)
        retry_decision = manager.workflow.nodes["should_retry_chapter"]['callable'](state) # current_retry_count was 1, max is 1

        self.assertEqual(retry_decision, "proceed_to_kb_update") # Max retries reached
        self.assertEqual(state["current_chapter_retry_count"], 0) # Reset for next chapter
        self.assertFalse(state["current_chapter_quality_passed"])

        # Assertions
        self.assertEqual(mock_chronicler_agent.generate_and_save_chapter.call_count, max_retries_val + 1)
        self.assertEqual(len(state["generated_chapters"]), 1) # Still adds the last failed one
        self.assertEqual(state["generated_chapters"][0]["title"], "Test Chapter 1 v2") # The last attempted version

        # Check for log message (this is now in _should_retry_chapter)
        history_str = " ".join(state["history"])
        self.assertIn(f"Chapter failed quality, but max retries ({max_retries_val}) reached.", history_str)


    @patch('src.orchestration.workflow_manager.ChapterChroniclerAgent')
    @patch('src.orchestration.workflow_manager.ContextSynthesizerAgent')
    @patch('src.orchestration.workflow_manager.ContentIntegrityAgent')
    def test_human_mode_no_chapter_retry(self, MockContentIntegrity, MockContextSynthesizer, MockChapterChronicler):
        mock_integrity_agent = MockContentIntegrity.return_value
        mock_integrity_agent.review_content.return_value = {"overall_score": 3.0, "justification": "Fail in human mode", "scores": {}}

        mock_context_agent = MockContextSynthesizer.return_value
        mock_context_agent.generate_chapter_brief.return_value = "Chapter brief text."

        mock_chronicler_agent = MockChapterChronicler.return_value
        mock_chronicler_agent.generate_and_save_chapter.return_value = Chapter(id=1, novel_id=1, chapter_number=1, title="Test Chapter 1", content="Content", summary="Summary")

        self.user_input_data["auto_mode"] = False # Human mode
        self.user_input_data["chapters"] = 1

        manager = WorkflowManager(db_name=self.db_name, mode="human")
        initial_state_dict = self._get_minimal_state_for_chapter_loop_start(manager, self.user_input_data)

        # Run through the sequence
        state = manager.workflow.nodes["context_synthesizer"]['callable'](initial_state_dict)
        state = manager.workflow.nodes["chapter_chronicler"]['callable'](state)
        state = manager.workflow.nodes["content_integrity_review"]['callable'](state)
        retry_decision = manager.workflow.nodes["should_retry_chapter"]['callable'](state)

        # Assertions
        self.assertEqual(retry_decision, "proceed_to_kb_update") # No retry in human mode by default
        self.assertEqual(mock_chronicler_agent.generate_and_save_chapter.call_count, 1)
        self.assertFalse(state["current_chapter_quality_passed"])
        self.assertEqual(state["current_chapter_retry_count"], 0) # Should remain 0 or be reset to 0
        history_str = " ".join(state["history"])
        self.assertIn("Chapter failed quality, but not in auto_mode. Proceeding without retry.", history_str)

    @patch('src.orchestration.workflow_manager.ConflictDetectionAgent')
    def test_auto_mode_conflict_detection_logging(self, MockConflictDetection):
        mock_conflict_agent = MockConflictDetection.return_value
        mock_conflict_agent.detect_conflicts.return_value = [{"type": "Continuity", "description": "Test conflict"}]

        self.user_input_data["auto_mode"] = True
        manager = WorkflowManager(db_name=self.db_name, mode="auto")
        initial_state_dict = self._get_minimal_state_for_chapter_loop_start(manager, self.user_input_data)
        # Assume a chapter has been generated
        initial_state_dict["generated_chapters"] = [Chapter(id=1, novel_id=1, chapter_number=1, title="C1", content="text", summary="s1")]


        state_after_conflict_detection = manager.workflow.nodes["conflict_detection"]['callable'](initial_state_dict)

        history_str = " ".join(state_after_conflict_detection["history"])
        self.assertIn("INFO: Auto-Mode: 1 conflicts detected. Placeholder for auto-resolution attempt.", history_str)

    @patch('src.orchestration.workflow_manager.ConflictDetectionAgent')
    def test_human_mode_conflict_detection_logging(self, MockConflictDetection):
        mock_conflict_agent = MockConflictDetection.return_value
        mock_conflict_agent.detect_conflicts.return_value = [{"type": "Continuity", "description": "Test conflict"}]

        self.user_input_data["auto_mode"] = False # Human mode
        manager = WorkflowManager(db_name=self.db_name, mode="human")
        initial_state_dict = self._get_minimal_state_for_chapter_loop_start(manager, self.user_input_data)
        initial_state_dict["generated_chapters"] = [Chapter(id=1, novel_id=1, chapter_number=1, title="C1", content="text", summary="s1")]

        state_after_conflict_detection = manager.workflow.nodes["conflict_detection"]['callable'](initial_state_dict)

        history_str = " ".join(state_after_conflict_detection["history"])
        self.assertIn("INFO: Human-Mode: 1 conflicts detected. Placeholder: User would be prompted for review and resolution options.", history_str)

    @patch('src.orchestration.workflow_manager.ConflictDetectionAgent')
    def test_no_conflict_logging(self, MockConflictDetection):
        mock_conflict_agent = MockConflictDetection.return_value
        mock_conflict_agent.detect_conflicts.return_value = [] # No conflicts

        manager = WorkflowManager(db_name=self.db_name, mode="auto") # Mode doesn't matter here
        initial_state_dict = self._get_minimal_state_for_chapter_loop_start(manager, self.user_input_data)
        initial_state_dict["generated_chapters"] = [Chapter(id=1, novel_id=1, chapter_number=1, title="C1", content="text", summary="s1")]

        state_after_conflict_detection = manager.workflow.nodes["conflict_detection"]['callable'](initial_state_dict)

        history_str = " ".join(state_after_conflict_detection["history"])
        self.assertIn("No conflicts detected in chapter.", history_str)


if __name__ == '__main__':
    unittest.main()

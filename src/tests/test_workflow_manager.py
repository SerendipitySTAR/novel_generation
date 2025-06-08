import unittest
from unittest.mock import patch, MagicMock, call
import os
import json

from src.orchestration.workflow_manager import WorkflowManager, NovelWorkflowState, UserInput, _should_retry_chapter
from src.persistence.database_manager import DatabaseManager
from src.core.auto_decision_engine import AutoDecisionEngine # Added for isinstance check
# It's good practice to mock the actual classes you intend to mock later
from src.agents.content_integrity_agent import ContentIntegrityAgent
from src.agents.conflict_detection_agent import ConflictDetectionAgent
from src.agents.conflict_resolution_agent import ConflictResolutionAgent # New import
from src.agents.context_synthesizer_agent import ContextSynthesizerAgent
from src.agents.chapter_chronicler_agent import ChapterChroniclerAgent
from src.agents.lore_keeper_agent import LoreKeeperAgent
from src.core.models import Chapter, PlotChapterDetail, Character, Outline, WorldView, Plot, Novel
# Import the specific functions to be tested directly if they are module-level
from src.orchestration.workflow_manager import (_decide_after_conflict_detection,
                                                execute_conflict_resolution_auto,
                                                prepare_conflict_review_for_api,
                                                present_outlines_for_selection_cli,
                                                present_worldviews_for_selection_cli)


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
            "novel_id": "novel1", # Changed to string for consistency with helper
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
        if hasattr(self, 'db_manager') and self.db_manager:
            del self.db_manager
        if os.path.exists(self.db_name):
            os.remove(self.db_name)
        if os.path.exists(f"{self.db_name}-journal"):
             os.remove(f"{self.db_name}-journal")

    def _get_minimal_state_for_api_decision_pause(self, decision_type: str) -> NovelWorkflowState:
        # Using a dictionary that NovelWorkflowState can unpack
        state_dict = {
            "novel_id": "novel1",
            "db_name": self.db_name,
            "history": [],
            "user_input": UserInput(interaction_mode="api", auto_mode=False, theme="Test Theme", style_preferences="Test Style", chapters=1, words_per_chapter=50),
            "all_generated_outlines": ["Outline 1", "Outline 2"] if decision_type == "outline_selection" else None,
            "all_generated_worldviews": [{"world_name": "WV1", "core_concept": "Concept1"}, {"world_name": "WV2", "core_concept": "Concept2"}] if decision_type == "worldview_selection" else None,
            "workflow_status": "running",
            "current_chapter_number": 1,
            "total_chapters_to_generate": 1,
            "error_message": None, "novel_data": None, "outline_id": None, "outline_data": None, "outline_review": None,
            "worldview_id": None, "worldview_data": None, "plot_id": None, "detailed_plot_data": None, "plot_data": None,
            "characters": None, "lore_keeper_initialized": False, "generated_chapters": [],
            "active_character_ids_for_chapter": None, "current_plot_focus_for_chronicler": None, "chapter_brief": None,
            "current_chapter_review": None, "current_chapter_quality_passed": None, "current_chapter_conflicts": None,
            "auto_decision_engine": None, "knowledge_graph_data": None, "current_chapter_retry_count": 0,
            "max_chapter_retries": 1, "current_chapter_original_content": None, "current_chapter_feedback_for_retry": None,
            "pending_decision_type": None, "pending_decision_options": None, "pending_decision_prompt": None,
            "user_made_decision_payload": None, "original_chapter_content_for_conflict_review": None,
            "loop_iteration_count": 0, "max_loop_iterations": 10, "execution_count": 0,
            # Specific for testing: Ensure these are distinct for worldview if needed by tests
            "narrative_outline_text": "Some default outline" if decision_type == "worldview_selection" else None,
            "selected_worldview_detail": None,
        }
        return NovelWorkflowState(**state_dict) # type: ignore

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
            current_chapter_feedback_for_retry=self.base_initial_state_extras["current_chapter_feedback_for_retry"],
            # Fields for conflict review and API pause
            workflow_status = "running", # Default initial status
            pending_decision_type = None,
            pending_decision_options = None,
            pending_decision_prompt = None,
            user_made_decision_payload = None,
            original_chapter_content_for_conflict_review = None
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

    # --- Tests for _decide_after_conflict_detection ---
    def test_decide_after_conflict_detection_auto_resolve(self):
        state = {
            "current_chapter_conflicts": [{"id": "c1", "description": "A conflict"}],
            "user_input": {"auto_mode": True, "interaction_mode": "cli"}, # interaction_mode doesn't matter if auto_mode is True
            "history": []
        }
        decision = _decide_after_conflict_detection(state)
        self.assertEqual(decision, "resolve_conflicts_auto")
        self.assertIn("Auto-Mode: Routing to auto-conflict resolution.", " ".join(state["history"]))

    def test_decide_after_conflict_detection_human_api_pending(self):
        state = {
            "current_chapter_conflicts": [{"id": "c1", "description": "A conflict"}],
            "user_input": {"auto_mode": False, "interaction_mode": "api"},
            "history": []
        }
        decision = _decide_after_conflict_detection(state)
        self.assertEqual(decision, "human_api_conflict_pending")
        self.assertIn("Human-Mode (API): Routing for API-based conflict review preparation.", " ".join(state["history"]))

    def test_decide_after_conflict_detection_proceed_no_conflicts(self):
        state = {
            "current_chapter_conflicts": [],
            "user_input": {"auto_mode": False, "interaction_mode": "cli"},
            "history": []
        }
        decision = _decide_after_conflict_detection(state)
        self.assertEqual(decision, "proceed_to_increment")
        self.assertIn("Decision: No conflicts found.", " ".join(state["history"]))

    def test_decide_after_conflict_detection_proceed_cli_with_conflicts(self):
        state = {
            "current_chapter_conflicts": [{"id": "c1", "description": "A conflict"}],
            "user_input": {"auto_mode": False, "interaction_mode": "cli"},
            "history": []
        }
        decision = _decide_after_conflict_detection(state)
        self.assertEqual(decision, "proceed_to_increment")
        self.assertIn("Human-Mode (CLI): Conflicts detected.", " ".join(state["history"]))

    # --- Tests for execute_conflict_resolution_auto ---
    @patch('src.orchestration.workflow_manager.ConflictResolutionAgent')
    def test_execute_conflict_resolution_auto_no_change(self, MockConflictResolutionAgent):
        mock_resolver_instance = MockConflictResolutionAgent.return_value
        original_text = "Chapter content with conflict."
        # Functional agent returns original text if no change, or None if error (which node handles by keeping original)
        mock_resolver_instance.attempt_auto_resolve.return_value = original_text

        state = NovelWorkflowState(
            novel_id=1, current_chapter_number=1, db_name=self.db_name, history=[],
            generated_chapters=[Chapter(id=1, novel_id=1, chapter_number=1, title="Ch1", content=original_text, summary="S1")],
            current_chapter_conflicts=[{"id": "c1", "description": "A conflict"}],
            user_input=UserInput(theme="t", style_preferences="s", chapters=1, words_per_chapter=10, auto_mode=True, interaction_mode="cli")
        )
        returned_state = execute_conflict_resolution_auto(state)

        self.assertEqual(returned_state["generated_chapters"][-1]["content"], original_text)
        self.assertIn("no changes made to chapter text", " ".join(returned_state["history"]))
        self.assertTrue(returned_state["current_chapter_conflicts"]) # Not cleared

    @patch('src.orchestration.workflow_manager.ConflictResolutionAgent')
    def test_execute_conflict_resolution_auto_text_changed(self, MockConflictResolutionAgent):
        mock_resolver_instance = MockConflictResolutionAgent.return_value
        original_text = "Chapter content with conflict."
        revised_text = "Revised chapter content."
        mock_resolver_instance.attempt_auto_resolve.return_value = revised_text # Functional agent returns new text

        state = NovelWorkflowState(
            novel_id=1, current_chapter_number=1, db_name=self.db_name, history=[],
            generated_chapters=[Chapter(id=1, novel_id=1, chapter_number=1, title="Ch1", content=original_text, summary="S1")],
            current_chapter_conflicts=[{"id": "c1", "description": "A conflict"}],
            user_input=UserInput(theme="t", style_preferences="s", chapters=1, words_per_chapter=10, auto_mode=True, interaction_mode="cli")
        )
        returned_state = execute_conflict_resolution_auto(state)

        self.assertEqual(returned_state["generated_chapters"][-1]["content"], revised_text)
        self.assertEqual(returned_state["generated_chapters"][-1]["summary"], "Summary needs regeneration after auto-resolution.")
        self.assertIn("text was modified", " ".join(returned_state["history"]))
        self.assertEqual(returned_state["current_chapter_conflicts"], []) # Cleared

    # --- Tests for prepare_conflict_review_for_api (Pausing Path) ---
    @patch('src.orchestration.workflow_manager.DatabaseManager')
    @patch('src.orchestration.workflow_manager.ConflictResolutionAgent')
    def test_prepare_conflict_review_for_api_pauses_correctly(self, MockConflictResolutionAgent, MockDatabaseManager):
        mock_resolver_instance = MockConflictResolutionAgent.return_value
        mock_db_instance = MockDatabaseManager.return_value

        # Functional agent now returns conflicts with 'llm_suggestions'
        augmented_conflict_list = [
            {"conflict_id": "c1", "description": "Conflict 1", "type": "Plot", "severity": "High", "llm_suggestions": ["Suggestion A for C1"]}
        ]
        mock_resolver_instance.suggest_revisions_for_human_review.return_value = augmented_conflict_list

        state = NovelWorkflowState(
            novel_id=1, current_chapter_number=1, db_name=self.db_name, history=[],
            generated_chapters=[Chapter(id=1, novel_id=1, chapter_number=1, title="Ch1", content="Text with issues", summary="S1")],
            current_chapter_conflicts=sample_conflict_list, # Original conflicts
            user_input=UserInput(theme="t", style_preferences="s", chapters=1, words_per_chapter=10, auto_mode=False, interaction_mode="api"),
            user_made_decision_payload=None # Crucial: no prior decision means we pause
        )
        returned_state = prepare_conflict_review_for_api(state)

        self.assertEqual(returned_state["pending_decision_type"], "conflict_review")
        # Check options structure
        self.assertEqual(len(returned_state["pending_decision_options"]), 1)
        api_option = returned_state["pending_decision_options"][0]
        self.assertEqual(api_option["id"], "c1")
        self.assertIn("Conflict Type: Plot", api_option["text_summary"])
        self.assertEqual(api_option["full_data"]["conflict_id"], "c1") # full_data is the conflict dict
        self.assertEqual(api_option["full_data"]["llm_suggestions"], ["Suggestion A for C1"])

        self.assertTrue(returned_state["workflow_status"].startswith("paused_for_conflict_review_ch_1"))
        self.assertEqual(returned_state["original_chapter_content_for_conflict_review"], "Text with issues")

        mock_db_instance.update_novel_pause_state.assert_called_once()
        args, _ = mock_db_instance.update_novel_pause_state.call_args
        self.assertEqual(args[0], 1) # novel_id
        self.assertTrue(args[1].startswith("paused_for_conflict_review_ch_1")) # workflow_status
        self.assertEqual(args[2], "conflict_review") # pending_decision_type
        self.assertIsInstance(args[3], str) # options_json
        self.assertTrue(args[4].startswith("Conflicts (1) detected")) # pending_decision_prompt
        self.assertIsInstance(args[5], str) # full_state_json

    # --- Test for prepare_conflict_review_for_api (Resuming Path) ---
    def test_prepare_conflict_review_for_api_resuming_path(self):
        state = NovelWorkflowState(
            novel_id=1, current_chapter_number=1, db_name=self.db_name, history=[],
            generated_chapters=[Chapter(id=1, novel_id=1, chapter_number=1, title="Ch1", content="Text", summary="S1")],
            current_chapter_conflicts=[], # Conflicts might be cleared by resume_workflow or still there
            user_input=UserInput(theme="t", style_preferences="s", chapters=1, words_per_chapter=10, auto_mode=False, interaction_mode="api"),
            user_made_decision_payload={"source_decision_type": "conflict_review", "action": "proceed_as_is"} # Decision made
        )
        returned_state = prepare_conflict_review_for_api(state)
        self.assertTrue(returned_state["workflow_status"].startswith("running_after_conflict_review_decision"))
        self.assertIsNone(returned_state.get("user_made_decision_payload"))
        self.assertIsNone(returned_state.get("pending_decision_type"))

    # --- Tests for resume_workflow (Conflict Review Path) ---
    @patch.object(WorkflowManager, '_build_graph')
    @patch('src.orchestration.workflow_manager.DatabaseManager')
    @patch('src.orchestration.workflow_manager.ConflictResolutionAgent')
    def test_resume_workflow_conflict_apply_suggestion(self, MockConflictResolutionAgent, MockDatabaseManager, mock_build_graph_ignored):
        mock_db_instance = MockDatabaseManager.return_value
        # Note: ConflictResolutionAgent is not directly used by resume_workflow for "apply_suggestion" itself,
        # but its output (suggestions) would have been in the paused state.

        original_chapter_content = "Chapter with conflict: old excerpt here."
        conflict_id_to_apply = "c1"
        suggestion_to_apply = "new excerpt text"

        # This is what was saved when prepare_conflict_review_for_api paused
        paused_state_dict = {
            "novel_id": 1, "current_chapter_number": 1, "db_name": self.db_name, "history": ["paused for conflict"],
            "generated_chapters": [{"id":1, "novel_id":1, "chapter_number":1, "title":"Ch1", "content":original_chapter_content, "summary":"S1"}],
            "original_chapter_content_for_conflict_review": original_chapter_content,
            "pending_decision_type": "conflict_review", # This should be set at pause time
            "workflow_status": "paused_for_conflict_review_ch_1",
            "pending_decision_options": [ # This is List[DecisionOption] from API perspective, so full_data holds the conflict
                {"id": "c1", "text_summary": "d1", "full_data": {"conflict_id": "c1", "description": "d1", "excerpt": "old excerpt here", "llm_suggestions": [suggestion_to_apply, "another suggestion"]}},
                {"id": "c2", "text_summary": "d2", "full_data": {"conflict_id": "c2", "description": "d2", "excerpt": "another old excerpt", "llm_suggestions": ["suggestion for c2"]}}
            ],
            "current_chapter_conflicts": [ # Original raw conflicts, might be used by "rewrite_all_auto_remaining"
                 {"conflict_id": "c1", "description": "d1", "excerpt": "old excerpt here"},
                 {"conflict_id": "c2", "description": "d2", "excerpt": "another old excerpt"}
            ],
            "user_input": {"theme":"t", "chapters":1, "auto_mode":False, "interaction_mode":"api"},
            "execution_count": 1
        }
        mock_db_instance.load_workflow_snapshot_and_decision_info.return_value = {
            "full_workflow_state_json": json.dumps(paused_state_dict)
        }

        manager = WorkflowManager(db_name=self.db_name)
        manager.app = MagicMock()
        # We need to mock what app.invoke returns. It will be the state after prepare_conflict_review_for_api runs again.
        # Let's assume prepare_conflict_review_for_api correctly re-pauses with updated pending_decision_options.
        state_after_prepare_node_runs = paused_state_dict.copy()
        # Simulate that the applied conflict is now marked and text is updated in generated_chapters by resume_workflow
        state_after_prepare_node_runs["generated_chapters"] = [{"id":1, "novel_id":1, "chapter_number":1, "title":"Ch1", "content":"Chapter with conflict: new excerpt text.", "summary":"S1"}]
        updated_pending_options = [
            {"id": "c1", "text_summary": "d1", "full_data": {"conflict_id": "c1", "description": "d1", "excerpt": "old excerpt here", "llm_suggestions": [suggestion_to_apply, "another suggestion"], "resolution_status": "applied_suggestion", "applied_suggestion_text": suggestion_to_apply}},
            {"id": "c2", "text_summary": "d2", "full_data": {"conflict_id": "c2", "description": "d2", "excerpt": "another old excerpt", "llm_suggestions": ["suggestion for c2"]}} # c2 is still unresolved
        ]
        state_after_prepare_node_runs["pending_decision_options"] = updated_pending_options
        state_after_prepare_node_runs["workflow_status"] = "paused_for_conflict_review_ch_1" # Node re-pauses
        manager.app.invoke = MagicMock(return_value=state_after_prepare_node_runs)

        decision_payload = {"action": "apply_suggestion", "conflict_id": conflict_id_to_apply, "suggestion_index": 0}
        final_state = manager.resume_workflow(1, "conflict_review", decision_payload)

        # Verify state passed to invoke by resume_workflow
        invoked_state_arg = manager.app.invoke.call_args[0][0]
        self.assertEqual(invoked_state_arg["generated_chapters"][-1]["content"], "Chapter with conflict: new excerpt text.")
        res_conflict_option = next(opt for opt in invoked_state_arg["pending_decision_options"] if opt["id"] == conflict_id_to_apply)
        self.assertEqual(res_conflict_option["full_data"]["resolution_status"], "applied_suggestion")
        self.assertEqual(res_conflict_option["full_data"]["applied_suggestion_text"], suggestion_to_apply)
        self.assertTrue(invoked_state_arg["workflow_status"].startswith("paused_for_conflict_review_ch_"))
        self.assertEqual(invoked_state_arg["user_made_decision_payload"]["action_taken_in_resume"], "apply_suggestion")

        # Since it re-paused, update_novel_pause_state should be called by prepare_conflict_review_for_api,
        # not update_novel_status_after_resume by resume_workflow's final block.
        # This means the final_status in resume_workflow will start with "paused_for_"
        mock_db_instance.update_novel_status_after_resume.assert_not_called()


    @patch.object(WorkflowManager, '_build_graph')
    @patch('src.orchestration.workflow_manager.DatabaseManager')
    @patch('src.orchestration.workflow_manager.ConflictResolutionAgent')
    def test_resume_workflow_conflict_ignore_conflict(self, MockConflictResolutionAgent, MockDatabaseManager, mock_build_graph):
        mock_db_instance = MockDatabaseManager.return_value
        original_content = "Chapter content with conflict: old excerpt here."
        conflict_id_to_ignore = "c1"

        paused_state_dict = {
            "novel_id": 1, "current_chapter_number": 1, "db_name": self.db_name, "history": ["paused for conflict"],
            "generated_chapters": [{"id":1, "novel_id":1, "chapter_number":1, "title":"Ch1", "content":original_content, "summary":"S1"}],
            "original_chapter_content_for_conflict_review": original_content,
            "pending_decision_type": "conflict_review",
            "workflow_status": "paused_for_conflict_review_ch_1",
            "pending_decision_options": [
                {"id": "c1", "text_summary": "d1", "full_data": {"conflict_id": "c1", "description": "d1", "excerpt": "old excerpt here", "llm_suggestions": ["suggestion1"]}},
                {"id": "c2", "text_summary": "d2", "full_data": {"conflict_id": "c2", "description": "d2", "excerpt": "another old excerpt", "llm_suggestions": ["suggestion for c2"]}}
            ],
            "current_chapter_conflicts": [{"conflict_id": "c1", "description": "d1", "excerpt": "old excerpt here"}],
            "user_input": {"theme":"t", "chapters":1, "auto_mode":False, "interaction_mode":"api"},
            "execution_count": 1
        }
        mock_db_instance.load_workflow_snapshot_and_decision_info.return_value = {
            "full_workflow_state_json": json.dumps(paused_state_dict)
        }

        manager = WorkflowManager(db_name=self.db_name)
        manager.app = MagicMock()
        # Simulate state after prepare_conflict_review_for_api re-evaluates and re-pauses
        state_after_prepare_node_runs = paused_state_dict.copy()
        updated_pending_options = [
            {"id": "c1", "text_summary": "d1", "full_data": {"conflict_id": "c1", "description": "d1", "excerpt": "old excerpt here", "llm_suggestions": ["suggestion1"], "resolution_status": "ignored_by_user"}},
            {"id": "c2", "text_summary": "d2", "full_data": {"conflict_id": "c2", "description": "d2", "excerpt": "another old excerpt", "llm_suggestions": ["suggestion for c2"]}}
        ]
        state_after_prepare_node_runs["pending_decision_options"] = updated_pending_options
        state_after_prepare_node_runs["workflow_status"] = "paused_for_conflict_review_ch_1"
        manager.app.invoke = MagicMock(return_value=state_after_prepare_node_runs)

        decision_payload = {"action": "ignore_conflict", "conflict_id": conflict_id_to_ignore}
        final_state = manager.resume_workflow(1, "conflict_review", decision_payload)

        invoked_state_arg = manager.app.invoke.call_args[0][0]
        self.assertEqual(invoked_state_arg["generated_chapters"][0]["content"], original_content) # Unchanged
        res_conflict_option = next(opt for opt in invoked_state_arg["pending_decision_options"] if opt["id"] == conflict_id_to_ignore)
        self.assertEqual(res_conflict_option["full_data"]["resolution_status"], "ignored_by_user")
        self.assertTrue(invoked_state_arg["workflow_status"].startswith("paused_for_conflict_review_ch_"))
        self.assertEqual(invoked_state_arg["user_made_decision_payload"]["action_taken_in_resume"], "ignore_conflict")
        mock_db_instance.update_novel_status_after_resume.assert_not_called()


    @patch.object(WorkflowManager, '_build_graph')
    @patch('src.orchestration.workflow_manager.DatabaseManager')
    @patch('src.orchestration.workflow_manager.ConflictResolutionAgent')
    def test_resume_workflow_conflict_review_attempt_rewrite(self, MockConflictResolutionAgent, MockDatabaseManager, mock_build_graph):
        mock_db_instance = MockDatabaseManager.return_value
        mock_resolver_instance = MockConflictResolutionAgent.return_value

        original_content = "Chapter content with conflict."
        rewritten_text = "Rewritten chapter text."
        mock_resolver_instance.attempt_auto_resolve.return_value = rewritten_text

        paused_state_dict = {
            "novel_id": 1, "current_chapter_number": 1, "db_name": self.db_name, "history": ["paused for conflict"],
            "generated_chapters": [{"id":1, "novel_id":1, "chapter_number":1, "title":"Ch1", "content":original_content, "summary":"S1"}],
            "current_chapter_conflicts": [{"conflict_id": "c1", "description": "A conflict"}], # These are original conflicts
            "pending_decision_options": [ # These are what user saw, potentially with suggestions
                 {"id": "c1", "full_data":{"conflict_id": "c1", "description": "A conflict", "excerpt": "problematic excerpt"}}
            ],
            "original_chapter_content_for_conflict_review": original_content,
            "pending_decision_type": "conflict_review",
            "workflow_status": "paused_for_conflict_review_ch_1",
            "user_input": {"theme":"t", "chapters":1, "auto_mode":False, "interaction_mode":"api"},
            "execution_count": 1
        }
        mock_db_instance.load_workflow_snapshot_and_decision_info.return_value = {
            "full_workflow_state_json": json.dumps(paused_state_dict)
        }

        manager = WorkflowManager(db_name=self.db_name)
        manager.app = MagicMock()
        # Simulate invoke leads to a state where prepare_conflict_review_for_api decides all resolved
        state_after_invoke_and_prepare_node = paused_state_dict.copy()
        state_after_invoke_and_prepare_node["workflow_status"] = "running_after_conflict_review_all_resolved_or_ignored"
        state_after_invoke_and_prepare_node["generated_chapters"] = [{"id":1, "novel_id":1, "chapter_number":1, "title":"Ch1", "content":rewritten_text, "summary":"S1"}]
        state_after_invoke_and_prepare_node["current_chapter_conflicts"] = []
        state_after_invoke_and_prepare_node["pending_decision_type"] = None
        state_after_invoke_and_prepare_node["pending_decision_options"] = None
        manager.app.invoke = MagicMock(return_value=state_after_invoke_and_prepare_node)

        decision_payload = {"action": "rewrite_all_auto_remaining"} # Action comes directly now
        final_state = manager.resume_workflow(1, "conflict_review", decision_payload)

        # Check call to agent
        # The conflicts passed to agent should be from pending_decision_options[...]['full_data']
        # and only those that are unresolved.
        unresolved_in_options = [opt["full_data"] for opt in paused_state_dict["pending_decision_options"] if not opt.get("full_data",{}).get("resolution_status")]
        mock_resolver_instance.attempt_auto_resolve.assert_called_once_with(
            1, original_content, unresolved_in_options,
            novel_context=paused_state_dict["user_input"]
        )

        # Check state passed to invoke by resume_workflow
        invoked_state_arg = manager.app.invoke.call_args[0][0]
        self.assertEqual(invoked_state_arg["generated_chapters"][0]["content"], rewritten_text)
        self.assertEqual(invoked_state_arg["current_chapter_conflicts"], []) # Cleared by resume_workflow
        self.assertIsNone(invoked_state_arg["original_chapter_content_for_conflict_review"])
        self.assertEqual(invoked_state_arg["user_made_decision_payload"]["action_taken_in_resume"], "rewrite_all_auto_remaining")

        # Check final DB update by resume_workflow
        mock_db_instance.update_novel_status_after_resume.assert_called_once()
        args_db_update = mock_db_instance.update_novel_status_after_resume.call_args[0]
        self.assertEqual(args_db_update[0], 1) # novel_id
        self.assertEqual(args_db_update[1], "running_after_conflict_review_all_resolved_or_ignored") # final status
        self.assertIn(rewritten_text, args_db_update[2]) # final_snapshot_json
        self.assertIsNone(invoked_state_arg["pending_decision_type"])
        self.assertIsNone(invoked_state_arg["pending_decision_options"])

    # --- New Tests for resume_workflow (Outline/Worldview Selection) ---
    @patch.object(WorkflowManager, '_build_graph')
    @patch('src.orchestration.workflow_manager.DatabaseManager')
    def test_resume_workflow_outline_selection(self, MockDatabaseManager, mock_build_graph_ignored):
        mock_db_instance = MockDatabaseManager.return_value

        paused_state_snapshot = self._get_minimal_state_for_api_decision_pause(decision_type="outline_selection")
        # Set auto_mode to True in the user_input of the snapshot for this test
        paused_state_snapshot['user_input']['auto_mode'] = True

        paused_state_snapshot.update({
            "all_generated_outlines": ["Outline 1 text", "Outline 2 text", "Outline 3 text"],
            "pending_decision_type": "outline_selection",
            "workflow_status": "paused_for_outline_selection",
            "execution_count": 1,
        })

        mock_db_instance.load_workflow_snapshot_and_decision_info.return_value = {
            "full_workflow_state_json": json.dumps(paused_state_snapshot)
        }

        # Instantiate manager in "auto" mode so it has its own self.auto_decision_engine
        manager = WorkflowManager(db_name=self.db_name, mode="auto")
        self.assertIsNotNone(manager.auto_decision_engine, "Manager should have an ADE instance in auto mode")

        manager.app = MagicMock()
        manager.app.invoke.side_effect = lambda state, config: state

        decision_payload = {"selected_id": "1"} # API sends 0-based index "1" (meaning second item)

        final_state = manager.resume_workflow(paused_state_snapshot["novel_id"], "outline_selection", decision_payload)

        manager.app.invoke.assert_called_once()
        state_passed_to_invoke = manager.app.invoke.call_args[0][0]

        self.assertEqual(state_passed_to_invoke.get("narrative_outline_text"), "Outline 2 text")
        self.assertEqual(state_passed_to_invoke.get("workflow_status"), "running_after_outline_decision")
        self.assertIsNone(state_passed_to_invoke.get("pending_decision_type"))
        self.assertIsNotNone(state_passed_to_invoke.get("user_made_decision_payload"))
        # resume_workflow sets selected_option_id as 1-based for node consumption
        self.assertEqual(state_passed_to_invoke["user_made_decision_payload"]["selected_option_id"], "2")
        self.assertEqual(state_passed_to_invoke["user_made_decision_payload"]["source_decision_type"], "outline_selection")
        self.assertEqual(state_passed_to_invoke["execution_count"], 2)

        # Assertions for auto_decision_engine re-initialization
        # Given paused_state_snapshot['user_input']['auto_mode'] = True and manager was init in "auto" mode
        self.assertIsNotNone(state_passed_to_invoke.get("auto_decision_engine"),
                             "auto_decision_engine should be re-initialized in state if auto_mode is True.")
        self.assertEqual(state_passed_to_invoke.get("auto_decision_engine"), manager.auto_decision_engine,
                             "auto_decision_engine in state should be the same instance as manager's ADE when manager is in auto_mode.")

        mock_db_instance.update_novel_status_after_resume.assert_called_once()
        args_db_update = mock_db_instance.update_novel_status_after_resume.call_args[0]
        self.assertEqual(args_db_update[0], paused_state_snapshot["novel_id"])
        self.assertEqual(args_db_update[1], "running_after_outline_decision")
        resumed_state_json = json.loads(args_db_update[2])
        self.assertEqual(resumed_state_json["narrative_outline_text"], "Outline 2 text")

    @patch.object(WorkflowManager, '_build_graph')
    @patch('src.orchestration.workflow_manager.DatabaseManager')
    def test_resume_workflow_worldview_selection(self, MockDatabaseManager, mock_build_graph_ignored):
        mock_db_instance = MockDatabaseManager.return_value

        all_worldviews_data = [{"world_name": "WV1", "core_concept": "Concept1"}, {"world_name": "WV2", "core_concept": "Concept2"}]
        paused_state_snapshot = self._get_minimal_state_for_api_decision_pause(decision_type="worldview_selection")
        paused_state_snapshot.update({
            "all_generated_worldviews": all_worldviews_data,
            "pending_decision_type": "worldview_selection",
            "workflow_status": "paused_for_worldview_selection",
            "execution_count": 1
        })

        mock_db_instance.load_workflow_snapshot_and_decision_info.return_value = {
            "full_workflow_state_json": json.dumps(paused_state_snapshot)
        }

        manager = WorkflowManager(db_name=self.db_name)
        manager.app = MagicMock()
        manager.app.invoke.side_effect = lambda state, config: state

        decision_payload = {"selected_id": "0"} # User selects WV1 (0-based index)

        final_state = manager.resume_workflow(paused_state_snapshot["novel_id"], "worldview_selection", decision_payload)

        manager.app.invoke.assert_called_once()
        state_passed_to_invoke = manager.app.invoke.call_args[0][0]

        self.assertEqual(state_passed_to_invoke.get("selected_worldview_detail"), all_worldviews_data[0])
        self.assertEqual(state_passed_to_invoke.get("workflow_status"), "running_after_worldview_decision")
        self.assertIsNone(state_passed_to_invoke.get("pending_decision_type"))
        self.assertIsNotNone(state_passed_to_invoke.get("user_made_decision_payload"))
        self.assertEqual(state_passed_to_invoke["user_made_decision_payload"]["selected_option_id"], "1") # 1-based for node
        self.assertEqual(state_passed_to_invoke["user_made_decision_payload"]["source_decision_type"], "worldview_selection")
        self.assertEqual(state_passed_to_invoke["execution_count"], 2)

        mock_db_instance.update_novel_status_after_resume.assert_called_once()
        args_db_update = mock_db_instance.update_novel_status_after_resume.call_args[0]
        self.assertEqual(args_db_update[0], paused_state_snapshot["novel_id"])
        self.assertEqual(args_db_update[1], "running_after_worldview_decision")
        resumed_state_json = json.loads(args_db_update[2])
        self.assertEqual(resumed_state_json["selected_worldview_detail"]["world_name"], "WV1")

    # --- Tests for present_outlines_for_selection_cli (API Mode) ---
    @patch('src.orchestration.workflow_manager.DatabaseManager')
    def test_present_outlines_api_mode_pauses_correctly(self, MockDatabaseManager):
        mock_db_instance = MockDatabaseManager.return_value
        outlines = ["Outline A", "Outline B Is Longer"]
        initial_state = self._get_minimal_state_for_api_decision_pause("outline_selection")
        initial_state.update({ # Ensure these are correctly set for the test
            "all_generated_outlines": outlines,
            "novel_id": "novel1", # from helper
            "db_name": self.db_name, # from helper
            "user_input": UserInput(interaction_mode="api", auto_mode=False, theme="Test", style_preferences="", chapters=1, words_per_chapter=50),
        })

        returned_state = present_outlines_for_selection_cli(initial_state)

        self.assertEqual(returned_state["workflow_status"], "paused_for_outline_selection")
        self.assertEqual(returned_state["pending_decision_type"], "outline_selection")
        self.assertEqual(returned_state["pending_decision_prompt"], "Please select a narrative outline for the novel.")

        expected_options = [
            {"id": "0", "text_summary": "Outline A"[:150]+"...", "full_data": "Outline A"},
            {"id": "1", "text_summary": "Outline B Is Longer"[:150]+"...", "full_data": "Outline B Is Longer"}
        ]
        self.assertEqual(returned_state["pending_decision_options"], expected_options)

        mock_db_instance.update_novel_pause_state.assert_called_once()
        call_args = mock_db_instance.update_novel_pause_state.call_args[0]
        self.assertEqual(call_args[0], initial_state["novel_id"])
        self.assertEqual(call_args[1], "paused_for_outline_selection")
        self.assertEqual(call_args[2], "outline_selection")
        self.assertEqual(json.loads(call_args[3]), expected_options)

    def test_present_outlines_api_mode_resumes_correctly(self):
        all_outlines_data = ["Outline X", "Outline Y"]
        state = self._get_minimal_state_for_api_decision_pause("outline_selection")
        state.update({
            "all_generated_outlines": all_outlines_data,
            # resume_workflow sets 'selected_option_id' as 1-based string for the node
            "user_made_decision_payload": {"source_decision_type": "outline_selection", "selected_option_id": "2"} # User selected "Outline Y" (index 1)
        })
        # user_input for API mode is already set by the helper

        returned_state = present_outlines_for_selection_cli(state)

        self.assertEqual(returned_state.get("narrative_outline_text"), all_outlines_data[1])
        self.assertIsNone(returned_state.get("user_made_decision_payload"))
        self.assertEqual(returned_state.get("workflow_status"), "running")
        self.assertIsNone(returned_state.get("error_message"))
        self.assertIn("API Human-Mode: Outline 2", "".join(returned_state.get("history", [])))

    # --- Tests for present_worldviews_for_selection_cli (API Mode) ---
    @patch('src.orchestration.workflow_manager.DatabaseManager')
    def test_present_worldviews_api_mode_pauses_correctly(self, MockDatabaseManager):
        mock_db_instance = MockDatabaseManager.return_value
        worldviews_data = [
            {"world_name": "WV One", "core_concept": "Concept Alpha", "key_elements":["elemA"], "atmosphere":"Atmo A"},
            {"world_name": "WV Two", "core_concept": "Concept Beta", "key_elements":["elemB"], "atmosphere":"Atmo B"}
        ]

        initial_state = self._get_minimal_state_for_api_decision_pause("worldview_selection")
        initial_state.update({
            "all_generated_worldviews": worldviews_data, # Already set by helper, but explicit here for clarity
            "user_input": UserInput(interaction_mode="api", auto_mode=False, theme="Test", style_preferences="", chapters=1, words_per_chapter=50),
        })

        returned_state = present_worldviews_for_selection_cli(initial_state)

        self.assertEqual(returned_state["workflow_status"], "paused_for_worldview_selection")
        self.assertEqual(returned_state["pending_decision_type"], "worldview_selection")
        self.assertEqual(returned_state["pending_decision_prompt"], "Please select a worldview for the novel.")

        expected_options = [
            {"id": "0", "text_summary": "WV One: Concept Alpha"[:100]+"...", "full_data": worldviews_data[0]},
            {"id": "1", "text_summary": "WV Two: Concept Beta"[:100]+"...", "full_data": worldviews_data[1]}
        ]

        self.assertEqual(len(returned_state["pending_decision_options"]), len(expected_options))
        for i, opt in enumerate(returned_state["pending_decision_options"]):
            self.assertEqual(opt["id"], expected_options[i]["id"])
            # Check summary construction (name + core_concept)
            expected_summary_start = f"{worldviews_data[i]['world_name']}: {worldviews_data[i]['core_concept']}"
            self.assertTrue(opt["text_summary"].startswith(expected_summary_start[:100]))
            self.assertEqual(opt["full_data"], expected_options[i]["full_data"])

        mock_db_instance.update_novel_pause_state.assert_called_once()

    def test_present_worldviews_api_mode_resumes_correctly(self):
        worldviews_as_dicts = [
            {"world_name": "WV One", "core_concept": "Concept Alpha"},
            {"world_name": "WV Two", "core_concept": "Concept Beta"}
        ]

        state = self._get_minimal_state_for_api_decision_pause("worldview_selection")
        state.update({
            "all_generated_worldviews": worldviews_as_dicts,
            # resume_workflow sets 'selected_option_id' as 1-based string for the node
            "user_made_decision_payload": {"source_decision_type": "worldview_selection", "selected_option_id": "1"} # User selected WV One (index 0)
        })

        returned_state = present_worldviews_for_selection_cli(state)

        self.assertEqual(returned_state.get("selected_worldview_detail"), worldviews_as_dicts[0])
        self.assertIsNone(returned_state.get("user_made_decision_payload"))
        self.assertEqual(returned_state.get("workflow_status"), "running")
        self.assertIsNone(returned_state.get("error_message"))
        self.assertIn("API Human-Mode: Worldview 'WV One' selected via API.", "".join(returned_state.get("history", [])))

if __name__ == '__main__':
    unittest.main()

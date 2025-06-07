import unittest
from unittest.mock import patch, MagicMock, call
import os
import json

from src.orchestration.workflow_manager import WorkflowManager, NovelWorkflowState, UserInput, _should_retry_chapter
from src.persistence.database_manager import DatabaseManager
# It's good practice to mock the actual classes you intend to mock later
from src.agents.content_integrity_agent import ContentIntegrityAgent
from src.agents.conflict_detection_agent import ConflictDetectionAgent
from src.agents.conflict_resolution_agent import ConflictResolutionAgent # New import
from src.agents.context_synthesizer_agent import ContextSynthesizerAgent
from src.agents.chapter_chronicler_agent import ChapterChroniclerAgent
from src.agents.lore_keeper_agent import LoreKeeperAgent
from src.core.models import Chapter, PlotChapterDetail, Character, Outline, WorldView, Plot, Novel
# Import the specific functions to be tested directly if they are module-level
from src.orchestration.workflow_manager import _decide_after_conflict_detection, execute_conflict_resolution_auto, prepare_conflict_review_for_api


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
        mock_resolver_instance.attempt_auto_resolve.return_value = original_text # No change

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
        mock_resolver_instance.attempt_auto_resolve.return_value = revised_text

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

        sample_conflict_list = [{"conflict_id": "c1", "description": "Conflict 1", "type": "Plot", "severity": "High"}]
        mock_resolver_instance.suggest_revisions_for_human_review.return_value = sample_conflict_list

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
        self.assertEqual(returned_state["pending_decision_options"][0]["id"], "c1")
        self.assertIn("Conflict Type: Plot", returned_state["pending_decision_options"][0]["text_summary"])
        self.assertEqual(returned_state["pending_decision_options"][0]["full_data"], sample_conflict_list[0])

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
    @patch.object(WorkflowManager, '_build_graph') # Prevent graph compilation in test
    @patch('src.orchestration.workflow_manager.DatabaseManager')
    @patch('src.orchestration.workflow_manager.ConflictResolutionAgent')
    def test_resume_workflow_conflict_review_proceed_as_is(self, MockConflictResolutionAgent, MockDatabaseManager, mock_build_graph):
        mock_db_instance = MockDatabaseManager.return_value
        mock_resolver_instance = MockConflictResolutionAgent.return_value

        original_content = "Chapter content with conflict."
        paused_state_dict = {
            "novel_id": 1, "current_chapter_number": 1, "db_name": self.db_name, "history": ["paused for conflict"],
            "generated_chapters": [{"id":1, "novel_id":1, "chapter_number":1, "title":"Ch1", "content":original_content, "summary":"S1"}],
            "current_chapter_conflicts": [{"id": "c1", "description": "A conflict"}],
            "original_chapter_content_for_conflict_review": original_content,
            "pending_decision_type": "conflict_review", # This would be NULL in DB if record_user_decision cleared it
            "workflow_status": "paused_for_conflict_review_ch_1",
            "user_input": {"theme":"t", "chapters":1, "auto_mode":False, "interaction_mode":"api"},
            "execution_count": 1
        }
        mock_db_instance.load_workflow_snapshot_and_decision_info.return_value = {
            "full_workflow_state_json": json.dumps(paused_state_dict),
            # user_made_decision_payload_json is set by record_user_decision, not directly used by resume_workflow logic here
        }

        manager = WorkflowManager(db_name=self.db_name)
        manager.app = MagicMock() # Mock the compiled LangGraph app
        manager.app.invoke = MagicMock(return_value=paused_state_dict) # invoke returns a state

        decision_payload = {"custom_data": {"action": "proceed_as_is"}}
        final_state = manager.resume_workflow(1, "conflict_review", decision_payload)

        mock_resolver_instance.attempt_auto_resolve.assert_not_called()

        # Check the state passed to invoke
        invoked_state_arg = manager.app.invoke.call_args[0][0]
        self.assertEqual(invoked_state_arg["user_made_decision_payload"]["action"], "proceed_as_is")
        self.assertEqual(invoked_state_arg["generated_chapters"][0]["content"], original_content) # Should be original
        self.assertIsNone(invoked_state_arg["original_chapter_content_for_conflict_review"]) # Cleared
        mock_db_instance.update_novel_status_after_resume.assert_called()


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
            "current_chapter_conflicts": [{"id": "c1", "description": "A conflict"}],
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
        # Simulate invoke returns a state where status might be "running" or "completed"
        # For this test, the crucial part is what happens *before* invoke
        state_after_invoke = paused_state_dict.copy()
        state_after_invoke["workflow_status"] = "completed"
        manager.app.invoke = MagicMock(return_value=state_after_invoke)

        decision_payload = {"custom_data": {"action": "attempt_generic_rewrite_all_conflicts"}}
        final_state = manager.resume_workflow(1, "conflict_review", decision_payload)

        mock_resolver_instance.attempt_auto_resolve.assert_called_once_with(
            1, original_content, paused_state_dict["current_chapter_conflicts"],
            novel_context=paused_state_dict["user_input"]
        )

        invoked_state_arg = manager.app.invoke.call_args[0][0]
        self.assertEqual(invoked_state_arg["generated_chapters"][0]["content"], rewritten_text)
        self.assertEqual(invoked_state_arg["current_chapter_conflicts"], []) # Should be cleared
        self.assertIsNone(invoked_state_arg["original_chapter_content_for_conflict_review"]) # Cleared
        mock_db_instance.update_novel_status_after_resume.assert_called()


if __name__ == '__main__':
    unittest.main()

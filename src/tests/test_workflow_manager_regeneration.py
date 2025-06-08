import unittest
from unittest.mock import patch, MagicMock
from typing import Dict, Any, List, Optional

# Attempt to import actual classes; provide fallbacks for standalone testing
try:
    from src.core.models import PlotChapterDetail, UserInput, NovelWorkflowState, Chapter
    from src.orchestration.workflow_manager import (
        apply_selected_plot_twist,
        apply_selected_plot_branch,
        _check_if_plot_regeneration_needed,
        execute_plot_regeneration_node,
        prepare_for_chapter_loop,
        _log_and_update_history # Import for patching if needed, or direct use if safe
    )
    # We will mock PlotRegeneratorAgent, so we don't need its actual implementation here for tests
    # from src.agents.plot_regenerator_agent import PlotRegeneratorAgent
except ImportError as e:
    print(f"TestWorkflowManagerRegeneration: Error importing module: {e}. Using placeholder definitions.")
    # Simplified placeholders if imports fail (e.g., running test file directly without proper PYTHONPATH)
    PlotChapterDetail = Dict[str, Any]
    UserInput = Dict[str, Any]
    NovelWorkflowState = Dict[str, Any]
    Chapter = Dict[str, Any]

    def _log_and_update_history(current_history: List[str], message: str, error: bool = False) -> List[str]:
        return current_history + [message]

    def apply_selected_plot_twist(state: NovelWorkflowState) -> Dict[str, Any]: return state
    def apply_selected_plot_branch(state: NovelWorkflowState) -> Dict[str, Any]: return state
    def _check_if_plot_regeneration_needed(state: NovelWorkflowState) -> str: return "skip_regeneration"
    def execute_plot_regeneration_node(state: NovelWorkflowState) -> Dict[str, Any]: return state
    def prepare_for_chapter_loop(state: NovelWorkflowState) -> Dict[str, Any]: return state


# --- Mock Classes and Helpers ---

class MockPlotRegeneratorAgent:
    def __init__(self, db_name: Optional[str] = None, llm_client=None): # Match expected signature
        self.db_name = db_name
        self.llm_client = llm_client
        self.regenerate_plot_segment_called_with: Optional[Dict[str, Any]] = None
        self.plot_to_return: List[PlotChapterDetail] = []

    def regenerate_plot_segment(self, narrative_outline: str, worldview_data: str,
                                preceding_plot_details: List[PlotChapterDetail],
                                regeneration_start_chapter: int, desired_total_chapters: int) -> List[PlotChapterDetail]:
        self.regenerate_plot_segment_called_with = {
            "narrative_outline": narrative_outline, "worldview_data": worldview_data,
            "preceding_plot_details": preceding_plot_details,
            "regeneration_start_chapter": regeneration_start_chapter,
            "desired_total_chapters": desired_total_chapters
        }
        num_to_gen = desired_total_chapters - regeneration_start_chapter + 1
        if num_to_gen <= 0:
            return []

        if self.plot_to_return:
            return_segment: List[PlotChapterDetail] = []
            for i, chap_detail_template in enumerate(self.plot_to_return):
                if i < num_to_gen: # Only return up to the number expected for the segment
                    chap_detail = {**chap_detail_template} # Make a copy from TypedDict/Dict
                    chap_detail["chapter_number"] = regeneration_start_chapter + i
                    return_segment.append(chap_detail)
            return return_segment

        # Default mock behavior if plot_to_return is not set
        return [
            create_chapter_detail(regeneration_start_chapter + i, title_prefix=f"Regen Chapter")
            for i in range(num_to_gen)
        ]

def create_chapter_detail(num: int, title_prefix: str = "Chapter") -> PlotChapterDetail:
    # Cast to PlotChapterDetail for type consistency if using real models
    return PlotChapterDetail(
        chapter_number=num,
        title=f"{title_prefix} {num}",
        core_scene_summary=f"Summary for {title_prefix} {num}",
        characters_present=[f"CharA_Ch{num}", f"CharB_Ch{num}"],
        key_events_and_plot_progression=f"Events for {title_prefix} {num}",
        setting_and_atmosphere_description="A standard setting.",
        character_development_notes="Standard dev.",
        plot_points_to_resolve_from_previous=[],
        new_plot_points_or_mysteries_introduced=[],
        estimated_words=1000,
        raw_llm_output_for_chapter=f"Raw output for {title_prefix} {num}"
    )

# --- Test Class ---

# Mock _log_and_update_history globally for all tests in this class if it's not essential to test its specific output here
# This avoids printing to console during tests unless specifically desired for a test.
@patch('src.orchestration.workflow_manager._log_and_update_history', side_effect=lambda hist, msg, error=False: hist + [msg])
class TestWorkflowManagerRegeneration(unittest.TestCase):

    def get_initial_state(self) -> NovelWorkflowState:
        # Provides a fresh, minimal state for each test
        return NovelWorkflowState(
            user_input=UserInput(theme="Test Theme", style_preferences="Test Style", chapters=5, words_per_chapter=1000, auto_mode=True, interaction_mode="cli"),
            error_message=None, history=[], novel_id=1, novel_data=None,
            narrative_outline_text="Test outline", all_generated_outlines=None,
            outline_id=1, outline_data=None, outline_review=None,
            all_generated_worldviews=None,
            selected_worldview_detail={"world_name": "Test World", "core_concept": "Test Concept", "key_elements": [], "atmosphere": "Test atmosphere", "raw_llm_output_for_worldview": "Test Concept raw"},
            worldview_id=1, worldview_data=None, plot_id=1,
            detailed_plot_data=[create_chapter_detail(i+1) for i in range(5)], # Default 5 chapters
            plot_data=None, all_generated_character_options=None, selected_detailed_character_profiles=None,
            saved_characters_db_model=None, lore_keeper_initialized=False,
            current_chapter_number=0, # Typically 0 before prepare_for_chapter_loop
            total_chapters_to_generate=5, # Matches detailed_plot_data length
            generated_chapters=[], # Content
            active_character_ids_for_chapter=None, current_chapter_plot_summary=None,
            current_plot_focus_for_chronicler=None, chapter_brief=None, db_name="test_novel_db.db",
            current_chapter_review=None, current_chapter_quality_passed=None, current_chapter_conflicts=None,
            auto_decision_engine=None, knowledge_graph_data=None, current_chapter_retry_count=0, max_chapter_retries=1,
            current_chapter_original_content=None, current_chapter_feedback_for_retry=None,
            workflow_status="running", pending_decision_type=None, pending_decision_options=None,
            pending_decision_prompt=None, user_made_decision_payload=None, original_chapter_content_for_conflict_review=None,
            available_plot_twist_options=None, selected_plot_twist_option=None, chapter_number_for_twist=None,
            available_plot_branch_options=None, selected_plot_branch_path=None, chapter_number_for_branching=None,
            needs_plot_regeneration=False, regeneration_start_chapter_number=None, plot_modified_at_chapter=None,
            chapter_pending_manual_review_id=None, chapter_content_for_manual_review=None, chapter_review_feedback_for_manual_review=None,
            loop_iteration_count=0, max_loop_iterations=20, execution_count=0
        )

    def test_apply_selected_plot_twist_sets_flags(self, mock_log_update):
        state = self.get_initial_state()
        twist_chapter_num = 3
        state["chapter_number_for_twist"] = twist_chapter_num
        state["selected_plot_twist_option"] = create_chapter_detail(twist_chapter_num, title_prefix="Twisted Chapter")
        state["detailed_plot_data"] = [create_chapter_detail(i+1) for i in range(5)]

        updated_state = apply_selected_plot_twist(state)

        self.assertTrue(updated_state.get("needs_plot_regeneration"))
        self.assertEqual(updated_state.get("plot_modified_at_chapter"), twist_chapter_num)
        self.assertEqual(updated_state.get("regeneration_start_chapter_number"), twist_chapter_num + 1)
        self.assertIn(f"Plot twist applied to chapter {twist_chapter_num}. Flagging for plot regeneration starting from chapter {twist_chapter_num + 1}.", updated_state["history"])

    def test_apply_selected_plot_branch_sets_flags(self, mock_log_update):
        state = self.get_initial_state()
        branch_point_num = 3
        branch_path = [create_chapter_detail(i + branch_point_num, title_prefix="Branch Ch") for i in range(2)] # Branch of 2 chapters

        state["chapter_number_for_branching"] = branch_point_num
        state["selected_plot_branch_path"] = branch_path
        state["detailed_plot_data"] = [create_chapter_detail(i+1) for i in range(5)]


        updated_state = apply_selected_plot_branch(state)

        self.assertTrue(updated_state.get("needs_plot_regeneration"))
        self.assertEqual(updated_state.get("plot_modified_at_chapter"), branch_point_num)
        expected_regen_start = branch_point_num + len(branch_path)
        self.assertEqual(updated_state.get("regeneration_start_chapter_number"), expected_regen_start)
        self.assertIn(f"Plot branch applied at chapter {branch_point_num}. Flagging for potential plot regeneration or continuation from chapter {expected_regen_start}.", updated_state["history"])


    def test_check_if_plot_regeneration_needed(self, mock_log_update):
        state = self.get_initial_state()
        state["needs_plot_regeneration"] = True
        state["plot_modified_at_chapter"] = 2
        state["regeneration_start_chapter_number"] = 3

        result = _check_if_plot_regeneration_needed(state)
        self.assertEqual(result, "regenerate_plot")
        self.assertIn("Plot regeneration is needed. Modified at chapter 2, starting regeneration from chapter 3.", state["history"])

        state["needs_plot_regeneration"] = False
        result = _check_if_plot_regeneration_needed(state)
        self.assertEqual(result, "skip_regeneration")
        self.assertIn("Plot regeneration is not needed. Proceeding with current plot.", state["history"])

    @patch('src.orchestration.workflow_manager.PlotRegeneratorAgent', new_callable=MockPlotRegeneratorAgent)
    def test_execute_plot_regeneration_node_success(self, MockAgent, mock_log_update):
        state = self.get_initial_state()
        state["needs_plot_regeneration"] = True
        state["plot_modified_at_chapter"] = 3 # Twist/Branch happened at chap 3
        state["regeneration_start_chapter_number"] = 3 # So regen starts AT chap 3
        state["total_chapters_to_generate"] = 5 # Overall novel length

        # Original plot: Ch1, Ch2, Ch3(old), Ch4(old), Ch5(old)
        # Preceding plot for agent: Ch1, Ch2
        # Agent should generate: Ch3(new), Ch4(new), Ch5(new)
        state["detailed_plot_data"] = [create_chapter_detail(i + 1, "Original") for i in range(5)]

        # Content for chapters 1 and 2 already exists
        state["generated_chapters"] = [
            Chapter(id=1, novel_id=1, chapter_number=1, title="Original 1 Content", content="Content 1"),
            Chapter(id=2, novel_id=1, chapter_number=2, title="Original 2 Content", content="Content 2")
        ]

        # Mock agent to return 3 chapters, which will become 3, 4, 5
        mock_agent_instance = MockAgent.return_value # Get the instance patch created
        mock_agent_instance.plot_to_return = [
            create_chapter_detail(0, "Regen"), # Placeholder num, will be overridden by agent logic
            create_chapter_detail(0, "Regen"),
            create_chapter_detail(0, "Regen")
        ]

        updated_state = execute_plot_regeneration_node(state)

        self.assertIsNone(updated_state.get("error_message"))
        self.assertFalse(updated_state.get("needs_plot_regeneration"))
        self.assertIsNone(updated_state.get("regeneration_start_chapter_number"))
        self.assertIsNone(updated_state.get("plot_modified_at_chapter"))

        # Check agent call
        self.assertIsNotNone(mock_agent_instance.regenerate_plot_segment_called_with)
        call_args = mock_agent_instance.regenerate_plot_segment_called_with
        self.assertEqual(len(call_args["preceding_plot_details"]), 2) # Chaps 1, 2
        self.assertEqual(call_args["preceding_plot_details"][0]['chapter_number'], 1)
        self.assertEqual(call_args["preceding_plot_details"][1]['chapter_number'], 2)
        self.assertEqual(call_args["regeneration_start_chapter"], 3)
        self.assertEqual(call_args["desired_total_chapters"], 5)

        # Check final plot
        self.assertEqual(len(updated_state["detailed_plot_data"]), 5)
        self.assertEqual(updated_state["detailed_plot_data"][0]['title'], "Original 1") # Unchanged
        self.assertEqual(updated_state["detailed_plot_data"][1]['title'], "Original 2") # Unchanged
        self.assertEqual(updated_state["detailed_plot_data"][2]['title'], "Regen Chapter 3") # New
        self.assertEqual(updated_state["detailed_plot_data"][3]['title'], "Regen Chapter 4") # New
        self.assertEqual(updated_state["detailed_plot_data"][4]['title'], "Regen Chapter 5") # New

        # Check content generation reset
        self.assertEqual(updated_state["current_chapter_number"], 3) # Should restart from modification point
        self.assertEqual(len(updated_state["generated_chapters"]), 2) # Chaps 1, 2 content preserved
        self.assertIn("Plot regenerated. Content generation will resume/restart from chapter 3. 0 previously generated chapter contents (from chapter 3 onwards) were discarded.", updated_state["history"])


    def test_execute_plot_regeneration_node_edge_case_no_regen_needed(self, mock_log_update):
        state = self.get_initial_state()
        state["needs_plot_regeneration"] = True # Flag is set
        state["plot_modified_at_chapter"] = 5
        state["regeneration_start_chapter_number"] = 6 # Start after total
        state["total_chapters_to_generate"] = 5
        state["detailed_plot_data"] = [create_chapter_detail(i+1) for i in range(5)]

        updated_state = execute_plot_regeneration_node(state)

        self.assertFalse(updated_state.get("needs_plot_regeneration")) # Flag should be cleared
        self.assertEqual(len(updated_state["detailed_plot_data"]), 5) # Plot truncated/kept at 5
        self.assertEqual(updated_state["total_chapters_to_generate"], 5) # Total chapters updated
        self.assertIn("Regeneration start chapter 6 is beyond desired total chapters 5. Plot will be truncated.", updated_state["history"])

    @patch('src.orchestration.workflow_manager.PlotRegeneratorAgent', new_callable=MockPlotRegeneratorAgent)
    def test_execute_plot_regeneration_node_agent_failure(self, MockAgent, mock_log_update):
        state = self.get_initial_state()
        state["needs_plot_regeneration"] = True
        state["plot_modified_at_chapter"] = 3
        state["regeneration_start_chapter_number"] = 3
        state["total_chapters_to_generate"] = 5

        mock_agent_instance = MockAgent.return_value
        mock_agent_instance.plot_to_return = [] # Simulate agent returning empty list

        updated_state = execute_plot_regeneration_node(state)

        self.assertIsNotNone(updated_state.get("error_message"))
        self.assertIn("PlotRegeneratorAgent returned no segment", updated_state.get("error_message", ""))
        self.assertTrue(updated_state.get("needs_plot_regeneration")) # Flag should NOT be cleared

    def test_prepare_for_chapter_loop_initial_run(self, mock_log_update):
        state = self.get_initial_state()
        # Ensure these are typical for a very first run before loop prep
        state["current_chapter_number"] = 0
        state["generated_chapters"] = None # Or []

        updated_state = prepare_for_chapter_loop(state)

        self.assertEqual(updated_state["current_chapter_number"], 1)
        self.assertEqual(updated_state["generated_chapters"], [])
        self.assertEqual(updated_state["total_chapters_to_generate"], 5) # Based on detailed_plot_data in get_initial_state
        self.assertIn("Chapter loop initializing for a new run from Chapter 1.", updated_state["history"])

    def test_prepare_for_chapter_loop_resuming_run(self, mock_log_update):
        state = self.get_initial_state()
        ch1_content = Chapter(id=1, novel_id=1, chapter_number=1, title="Ch1", content="...")
        ch2_content = Chapter(id=2, novel_id=1, chapter_number=2, title="Ch2", content="...")

        state["current_chapter_number"] = 3 # e.g., after plot regen that kept ch1,2 and modified from 3
        state["generated_chapters"] = [ch1_content, ch2_content]
        state["total_chapters_to_generate"] = 5 # Should be determined correctly by the function

        updated_state = prepare_for_chapter_loop(state)

        self.assertEqual(updated_state["current_chapter_number"], 3)
        self.assertEqual(len(updated_state["generated_chapters"]), 2)
        self.assertEqual(updated_state["generated_chapters"][0]["title"], "Ch1")
        # total_chapters_to_generate will be based on detailed_plot_data or user_input.chapters
        # In get_initial_state, detailed_plot_data has 5 chapters, user_input.chapters is 5.
        self.assertEqual(updated_state["total_chapters_to_generate"], 5)
        self.assertIn("Chapter loop continues/resumes. Starting/Next chapter: 3.", updated_state["history"])

if __name__ == '__main__':
    unittest.main()

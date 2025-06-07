# src/tests/test_context_synthesizer_agent.py
import unittest
from unittest.mock import MagicMock, patch
import json # For creating JSON strings for plot data if needed by mocks

# Assuming models are in src.core.models
from src.core.models import Novel, Outline, WorldView, Plot, Character, Chapter, DetailedCharacterProfile
from src.agents.context_synthesizer_agent import ContextSynthesizerAgent
# DatabaseManager and LoreKeeperAgent will be mocked

# Suppress logging from agents during tests
import logging
logging.disable(logging.CRITICAL)

class TestContextSynthesizerAgent(unittest.TestCase):

    def _create_mock_chapter(self, novel_id, chapter_number, title, content, summary) -> Chapter:
        return Chapter(
            id=chapter_number, # Simple ID for mock
            novel_id=novel_id,
            chapter_number=chapter_number,
            title=title,
            content=content,
            summary=summary,
            creation_date="test_date"
        )

    def setUp(self):
        self.db_name = "test_context_synth_agent.db"
        self.chroma_dir = "./test_context_synth_chroma"

        # Mock DatabaseManager instance and its methods
        self.mock_db_manager = MagicMock()
        self.mock_db_manager.get_novel_by_id.return_value = Novel(
            id=1, user_theme="Test Theme", style_preferences="Test Style",
            active_outline_id=1, active_worldview_id=1, active_plot_id=1,
            creation_date="test", last_updated_date="test" ,
            workflow_status='completed', pending_decision_type=None,
            pending_decision_options_json=None, pending_decision_prompt=None,
            full_workflow_state_json=None, user_made_decision_payload_json=None
        )
        self.mock_db_manager.get_outline_by_id.return_value = Outline(
            id=1, novel_id=1, overview_text="Test Outline Overview", creation_date="test"
        )
        self.mock_db_manager.get_worldview_by_id.return_value = WorldView(
            id=1, novel_id=1, description_text="Test Worldview Description", creation_date="test"
        )
        # Mock characters - ContextSynthesizer uses get_characters_for_novel
        self.mock_main_char_profile = DetailedCharacterProfile(
            character_id=1, novel_id=1, name="Main Character", role_in_story="Protagonist",
            personality_traits="Brave", motivations_deep_drive="Save the world", goal_short_term="Find McGuffin",
            creation_date="test_date"
            # other fields can be None or default
        )
        self.mock_db_manager.get_characters_for_novel.return_value = [self.mock_main_char_profile]

        # Mock LoreKeeperAgent instance and its methods
        self.mock_lore_keeper = MagicMock()
        self.mock_lore_keeper.get_context_for_chapter.return_value = "Mocked RAG context from LoreKeeper."

        # Patch the DatabaseManager and LoreKeeperAgent anD LLMClient where they are instantiated in ContextSynthesizerAgent
        self.patcher_db = patch('src.agents.context_synthesizer_agent.DatabaseManager', return_value=self.mock_db_manager)
        self.patcher_lk = patch('src.agents.context_synthesizer_agent.LoreKeeperAgent', return_value=self.mock_lore_keeper)

        self.MockDatabaseManager = self.patcher_db.start()
        self.MockLoreKeeperAgent = self.patcher_lk.start()

        self.agent = ContextSynthesizerAgent(db_name=self.db_name, chroma_db_directory=self.chroma_dir)

    def tearDown(self):
        self.patcher_db.stop()
        self.patcher_lk.stop()
        # pass # No actual DB files created by mocks

    def test_generate_brief_first_chapter(self):
        # Test when current_chapter_number is 1 (no previous chapters)
        self.mock_db_manager.get_chapters_for_novel.return_value = [] # No previous chapters

        brief = self.agent.generate_chapter_brief(
            novel_id=1, current_chapter_number=1,
            current_chapter_plot_summary_for_brief="Plot for chapter 1.",
            active_character_ids=[1]
        )

        self.assertIn("Test Theme", brief)
        self.assertIn("Test Outline Overview", brief)
        self.assertIn("Test Worldview Description", brief)
        self.assertIn("Main Character", brief)
        self.assertIn("Plot for chapter 1.", brief)
        self.assertIn("Mocked RAG context from LoreKeeper.", brief)
        self.assertIn("(This is the first chapter, no preceding chapter context).", brief)
        self.assertNotIn("Immediately Preceding Chapter(s)", brief) # Check for section header more generally
        self.assertNotIn("Recent Past Chapters (Summaries):", brief)
        self.assertNotIn("Earlier Chapter Mentions (Titles):", brief)

    def test_generate_brief_one_previous_chapter_full_text(self):
        # Current chapter is 2, one previous chapter (ch 1)
        prev_ch1 = self._create_mock_chapter(1, 1, "Prev Ch1 Title", "Full content of Ch1. " * 5, "Summary of Ch1.")
        self.mock_db_manager.get_chapters_for_novel.return_value = [prev_ch1]

        brief = self.agent.generate_chapter_brief(
            novel_id=1, current_chapter_number=2,
            current_chapter_plot_summary_for_brief="Plot for chapter 2.",
            active_character_ids=[1]
        )
        self.assertIn("**Immediately Preceding Chapter(s) (Full Text/Detailed Snippet):**", brief)
        self.assertIn("Chapter 1: Prev Ch1 Title (Full Text Snippet", brief)
        self.assertIn("Full content of Ch1.", brief) # Check for actual content
        self.assertNotIn("Recent Past Chapters (Summaries):", brief)
        self.assertNotIn("Earlier Chapter Mentions (Titles):", brief)

    def test_generate_brief_two_previous_chapters(self):
        # Based on NUM_FULL_TEXT_PREVIOUS = 1, NUM_SUMMARY_PREVIOUS = 3
        # If current_chapter_number = 3:
        #   Chapter 2 (N-1) -> Full text
        #   Chapter 1 (N-2) -> Summary

        ch1 = self._create_mock_chapter(1, 1, "Ch1 Title", "Full content of Ch1. " * 5, "Summary of Ch1.")
        ch2 = self._create_mock_chapter(1, 2, "Ch2 Title", "Full content of Ch2. " * 5, "Summary of Ch2.")
        self.mock_db_manager.get_chapters_for_novel.return_value = [ch1, ch2]

        brief = self.agent.generate_chapter_brief(
            novel_id=1, current_chapter_number=3,
            current_chapter_plot_summary_for_brief="Plot for chapter 3.",
            active_character_ids=[1]
        )

        self.assertIn("**Immediately Preceding Chapter(s) (Full Text/Detailed Snippet):**", brief)
        self.assertIn("Chapter 2: Ch2 Title (Full Text Snippet", brief)
        self.assertIn("Full content of Ch2.", brief)

        self.assertIn("**Recent Past Chapters (Summaries):**", brief)
        self.assertIn("Chapter 1 (Ch1 Title) Summary: Summary of Ch1.", brief)

        self.assertNotIn("Earlier Chapter Mentions (Titles):", brief)

    def test_generate_brief_five_previous_chapters(self):
        # Current chapter is 6.
        # Ch5 (N-1) -> Full text (NUM_FULL_TEXT_PREVIOUS = 1)
        # Ch4 (N-2), Ch3 (N-3), Ch2 (N-4) -> Summaries (NUM_SUMMARY_PREVIOUS = 3)
        # Ch1 (N-5) -> Title only

        chapters = [
            self._create_mock_chapter(1, 1, "Ch1 Title", "Content Ch1", "Summary Ch1"),
            self._create_mock_chapter(1, 2, "Ch2 Title", "Content Ch2", "Summary Ch2"),
            self._create_mock_chapter(1, 3, "Ch3 Title", "Content Ch3", "Summary Ch3"),
            self._create_mock_chapter(1, 4, "Ch4 Title", "Content Ch4", "Summary Ch4"),
            self._create_mock_chapter(1, 5, "Ch5 Title", "Full content of Ch5. " * 5, "Summary Ch5"),
        ]
        self.mock_db_manager.get_chapters_for_novel.return_value = chapters

        brief = self.agent.generate_chapter_brief(
            novel_id=1, current_chapter_number=6,
            current_chapter_plot_summary_for_brief="Plot for chapter 6.",
            active_character_ids=[1]
        )

        # Full text section
        self.assertIn("**Immediately Preceding Chapter(s) (Full Text/Detailed Snippet):**", brief)
        self.assertIn("Chapter 5: Ch5 Title (Full Text Snippet", brief)
        self.assertIn("Full content of Ch5.", brief)

        # Summaries section
        self.assertIn("**Recent Past Chapters (Summaries):**", brief)
        self.assertIn("Chapter 4 (Ch4 Title) Summary: Summary Ch4", brief)
        self.assertIn("Chapter 3 (Ch3 Title) Summary: Summary Ch3", brief)
        self.assertIn("Chapter 2 (Ch2 Title) Summary: Summary Ch2", brief)

        # Titles only section
        self.assertIn("**Earlier Chapter Mentions (Titles):**", brief)
        self.assertIn("    - Chapter 1: Ch1 Title", brief) # Ensure it's listed under the sub-header

    def test_generate_brief_max_lengths_for_full_text(self):
        # Test that full text snippet is truncated correctly (agent uses [:1500])
        long_content = "A" * 2000
        prev_ch1 = self._create_mock_chapter(1, 1, "LongPrevCh1", long_content, "Summary of LongCh1.")
        self.mock_db_manager.get_chapters_for_novel.return_value = [prev_ch1]

        brief = self.agent.generate_chapter_brief(
            novel_id=1, current_chapter_number=2,
            current_chapter_plot_summary_for_brief="Plot for chapter 2.",
            active_character_ids=[1]
        )
        expected_snippet = "A" * 1500 + "..."
        self.assertIn(expected_snippet, brief)
        self.assertNotIn("A" * 1501, brief) # Check that it's not including more than 1500 'A's before ellipsis


if __name__ == '__main__':
    logging.disable(logging.NOTSET) # Re-enable logging for manual test runs
    logging.basicConfig(level=logging.INFO)
    unittest.main()

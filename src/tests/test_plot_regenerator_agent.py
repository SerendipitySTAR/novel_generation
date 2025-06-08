import unittest
from typing import List, Dict, Any, Optional

# Assuming PlotRegeneratorAgent and PlotChapterDetail will be importable
# For now, let's define placeholder/simplified versions if direct import fails in this environment
try:
    from src.agents.plot_regenerator_agent import PlotRegeneratorAgent
    from src.core.models import PlotChapterDetail
    from src.llm_abstraction.llm_client import LLMClient # For type hinting if PlotRegeneratorAgent expects it
except ImportError:
    # Placeholder definitions for isolated testing if imports fail
    print("Warning: Using placeholder definitions for PlotRegeneratorAgent, PlotChapterDetail, or LLMClient.")

    PlotChapterDetail = Dict[str, Any]

    class LLMClient: # Minimal placeholder for type hinting
        def __init__(self, db_name: Optional[str] = None, api_key: Optional[str] = None):
            pass
        def generate_text(self, prompt: str, model_name: Optional[str] = None, max_tokens: Optional[int] = None, temperature: Optional[float] = None) -> str:
            return ""

    class PlotRegeneratorAgent:
        def __init__(self, llm_client: Optional[LLMClient] = None, db_name: Optional[str] = None):
            self.llm_client = llm_client or LLMClient()
            self.db_name = db_name
            # Add the parsing methods directly here if they are part of the class
            # For this test, we'll assume the real agent has them.
            # If running this standalone, these would need to be copied from the agent.
            print("Placeholder PlotRegeneratorAgent initialized for testing.")

        def _get_field_value(self, field_name_variations: List[str], text_block: str, is_list: bool = False, block_chapter_num_for_logging: Optional[int] = None) -> Optional[Any]:
            # Simplified mock, real agent has complex regex
            key_to_find = field_name_variations[0].lower().replace(" ", "_")
            lines = text_block.splitlines()
            for line in lines:
                if ":" in line:
                    key, value = line.split(":", 1)
                    if key.strip().lower().replace(" ", "_") == key_to_find:
                        if is_list: return [v.strip() for v in value.strip().split(",")]
                        return value.strip()
            return [] if is_list else None

        def _parse_regenerated_chapters_from_llm(self, llm_response: str, num_chapters_to_parse: int, expected_start_chapter_number: int) -> List[PlotChapterDetail]:
            # This is a simplified mock parser for testing the test structure itself.
            # The real agent uses a more complex regex-based parser.
            parsed_chapters: List[PlotChapterDetail] = []
            chapter_blocks = llm_response.split("BEGIN CHAPTER")[1:] # Basic split
            for i, block_content_full in enumerate(chapter_blocks):
                if i >= num_chapters_to_parse: break

                # Remove "END CHAPTER..." part
                block_content = block_content_full.split("END CHAPTER")[0]

                chapter_num_abs = expected_start_chapter_number + i

                # Attempt to extract title (very basic)
                title = f"Test Chapter {chapter_num_abs}"
                title_match = [line for line in block_content.splitlines() if "title:" in line.lower()]
                if title_match:
                    title = title_match[0].split(":",1)[1].strip()

                parsed_chapters.append(PlotChapterDetail(
                    chapter_number=chapter_num_abs,
                    title=title,
                    core_scene_summary=self._get_field_value(["Core Scene Summary"], block_content, block_chapter_num_for_logging=chapter_num_abs) or "Summary",
                    key_events_and_plot_progression=self._get_field_value(["Key Events and Plot Progression"], block_content) or "Events",
                    setting_and_atmosphere_description=self._get_field_value(["Setting and Atmosphere Description"], block_content) or "Setting",
                    characters_present=self._get_field_value(["Characters Present"], block_content, is_list=True) or [],
                    character_development_notes=self._get_field_value(["Character Development Notes"], block_content) or "Dev",
                    plot_points_to_resolve_from_previous=self._get_field_value(["Plot Points to Resolve from Previous"], block_content, is_list=True) or [],
                    new_plot_points_or_mysteries_introduced=self._get_field_value(["New Plot Points or Mysteries Introduced"], block_content, is_list=True) or [],
                    estimated_words=int(self._get_field_value(["Estimated Word Count"], block_content) or "1000"),
                    raw_llm_output_for_chapter=block_content.strip()
                ))
            return parsed_chapters

        def regenerate_plot_segment(self, narrative_outline: str, worldview_data: str, preceding_plot_details: List[PlotChapterDetail], regeneration_start_chapter: int, desired_total_chapters: int) -> List[PlotChapterDetail]:
            print(f"Placeholder Agent: Regenerating from {regeneration_start_chapter} to {desired_total_chapters}")
            num_chapters_to_generate = desired_total_chapters - regeneration_start_chapter + 1
            if num_chapters_to_generate <= 0: return []

            prompt = f"Outline: {narrative_outline}\nWorldview: {worldview_data}\nPreceding: {len(preceding_plot_details)} chaps\nRegen from {regeneration_start_chapter} to {desired_total_chapters}"
            llm_response = self.llm_client.generate_text(prompt, model_name="test_model", max_tokens=100 * num_chapters_to_generate)

            if not llm_response: return []
            return self._parse_regenerated_chapters_from_llm(llm_response, num_chapters_to_generate, regeneration_start_chapter)


class MockLLMClient:
    def __init__(self, expected_responses: Optional[Dict[str, str]] = None):
        self.expected_responses = expected_responses if expected_responses else {}
        self.call_log: List[Dict[str, Any]] = []

    def generate_text(self, prompt: str, model_name: Optional[str]=None, max_tokens: Optional[int]=None, temperature: Optional[float]=None) -> str: # Added Optional for model_name etc.
        self.call_log.append({"prompt": prompt, "model_name": model_name, "max_tokens": max_tokens, "temperature": temperature})
        # Try to find a response based on a keyword in the prompt
        for keyword, response in self.expected_responses.items():
            if keyword in prompt:
                return response
        # Default fallback if no keyword matches
        return "BEGIN CHAPTER 1:\nchapter_number: 1\ntitle: Default Test Chapter\ncore_scene_summary: Default summary.\nkey_events_and_plot_progression: Default events.\nsetting_and_atmosphere_description: Default setting.\ncharacters_present: Character A\ncharacter_development_notes: Default dev.\nplot_points_to_resolve_from_previous: None\nnew_plot_points_or_mysteries_introduced: Default mystery\nestimated_word_count: 1000\nEND CHAPTER 1:"


class TestPlotRegeneratorAgent(unittest.TestCase):
    def setUp(self):
        self.sample_outline = "A grand space opera about a lost colony."
        self.sample_worldview = "Technology is advanced but failing. Society is fragmented."
        self.mock_llm_client = MockLLMClient()
        # Pass db_name=None if your agent's LLMClient init allows it or handles it for testing
        self.agent = PlotRegeneratorAgent(llm_client=self.mock_llm_client)


    def test_regenerate_from_start(self):
        self.mock_llm_client.expected_responses = {
            "Regen from 1 to 3": """
BEGIN CHAPTER 1:
chapter_number: 1
title: Chapter One of Segment
estimated_word_count: 1500
END CHAPTER 1:
BEGIN CHAPTER 2:
chapter_number: 2
title: Chapter Two of Segment
estimated_word_count: 1600
END CHAPTER 2:
BEGIN CHAPTER 3:
chapter_number: 3
title: Chapter Three of Segment
estimated_word_count: 1400
END CHAPTER 3:
            """
        }
        results = self.agent.regenerate_plot_segment(
            narrative_outline=self.sample_outline,
            worldview_data=self.sample_worldview,
            preceding_plot_details=[],
            regeneration_start_chapter=1,
            desired_total_chapters=3
        )
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]['chapter_number'], 1)
        self.assertEqual(results[0]['title'], "Chapter One of Segment")
        self.assertEqual(results[1]['chapter_number'], 2)
        self.assertEqual(results[2]['chapter_number'], 3)

    def test_regenerate_mid_novel(self):
        preceding_plot = [
            PlotChapterDetail(chapter_number=1, title="First Contact", core_scene_summary="..."),
            PlotChapterDetail(chapter_number=2, title="The Warning", core_scene_summary="...")
        ]
        self.mock_llm_client.expected_responses = {
            "Regen from 3 to 4": """
BEGIN CHAPTER 1:
chapter_number: 1
title: The New Threat (Abs Ch 3)
estimated_word_count: 1200
END CHAPTER 1:
BEGIN CHAPTER 2:
chapter_number: 2
title: Alliances Form (Abs Ch 4)
estimated_word_count: 1300
END CHAPTER 2:
            """
        }
        results = self.agent.regenerate_plot_segment(
            narrative_outline=self.sample_outline,
            worldview_data=self.sample_worldview,
            preceding_plot_details=preceding_plot,
            regeneration_start_chapter=3,
            desired_total_chapters=4
        )
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['chapter_number'], 3, "First regenerated chapter should be absolute chapter 3")
        self.assertEqual(results[0]['title'], "The New Threat (Abs Ch 3)")
        self.assertEqual(results[1]['chapter_number'], 4, "Second regenerated chapter should be absolute chapter 4")
        self.assertEqual(results[1]['title'], "Alliances Form (Abs Ch 4)")

    def test_regenerate_single_chapter(self):
        preceding_plot = [PlotChapterDetail(chapter_number=1, title="Old Chapter 1")]
        self.mock_llm_client.expected_responses = {
            "Regen from 2 to 2": """
BEGIN CHAPTER 1:
chapter_number: 1
title: The Only Chapter (Abs Ch 2)
estimated_word_count: 1000
END CHAPTER 1:
            """
        }
        results = self.agent.regenerate_plot_segment(
            self.sample_outline, self.sample_worldview, preceding_plot, 2, 2
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['chapter_number'], 2)
        self.assertEqual(results[0]['title'], "The Only Chapter (Abs Ch 2)")

    def test_prompt_construction(self):
        preceding_plot = [PlotChapterDetail(chapter_number=1, title="The Old Ways", core_scene_summary="Old summary", key_events_and_plot_progression="Old event")]
        # No specific response needed, just checking the prompt
        self.agent.regenerate_plot_segment(
            "Test Outline", "Test Worldview", preceding_plot, 2, 3
        )
        self.assertEqual(len(self.mock_llm_client.call_log), 1)
        prompt = self.mock_llm_client.call_log[0]['prompt']
        self.assertIn("Test Outline", prompt)
        self.assertIn("Test Worldview", prompt)
        self.assertIn("Chapter 1: The Old Ways", prompt) # Preceding summary
        self.assertIn("Summary: Old summary", prompt)
        self.assertIn("Key Events: Old event", prompt)
        self.assertIn("generate detailed plot points for 2 new chapter(s)", prompt) # 3-2+1 = 2
        self.assertIn("Chapters 2 through 3 of the novel", prompt)
        self.assertIn("BEGIN CHAPTER 1", prompt) # Example for LLM should be relative
        self.assertIn("END CHAPTER 1", prompt)


    def test_parsing_and_chapter_numbering(self):
        mock_response = """
BEGIN CHAPTER 1:
title: First Regenerated Chapter
chapter_number: 1
core_scene_summary: Summary for 1st reg.
key_events_and_plot_progression: Event A, Event B
setting_and_atmosphere_description: Dark and stormy
characters_present: Alice, Bob
character_development_notes: Alice becomes brave.
plot_points_to_resolve_from_previous: Mystery X
new_plot_points_or_mysteries_introduced: Mystery Y
estimated_word_count: 1500
END CHAPTER 1:

BEGIN CHAPTER 2:
title: Second Regenerated Chapter
chapter_number: 2
core_scene_summary: Summary for 2nd reg.
key_events_and_plot_progression: Event C leads to D
setting_and_atmosphere_description: Bright and hopeful
characters_present: Alice, Charles
character_development_notes: Bob is missing.
plot_points_to_resolve_from_previous: Mystery Y
new_plot_points_or_mysteries_introduced: Mystery Z, Question W
estimated_word_count: 1200
END CHAPTER 2:
        """
        self.mock_llm_client.expected_responses = {"Regen from 5 to 6": mock_response}

        results = self.agent.regenerate_plot_segment(
            self.sample_outline, self.sample_worldview,
            [PlotChapterDetail(chapter_number=i, title=f"Chap {i}") for i in range(1,5)], # Dummy 4 preceding chapters
            regeneration_start_chapter=5,
            desired_total_chapters=6
        )
        self.assertEqual(len(results), 2)

        # Chapter 1 of segment (Absolute Chapter 5)
        self.assertEqual(results[0]['chapter_number'], 5)
        self.assertEqual(results[0]['title'], "First Regenerated Chapter")
        self.assertIn("Alice", results[0]['characters_present'])
        self.assertIn("Mystery Y", results[0]['new_plot_points_or_mysteries_introduced'])
        self.assertEqual(results[0]['estimated_words'], 1500)

        # Chapter 2 of segment (Absolute Chapter 6)
        self.assertEqual(results[1]['chapter_number'], 6)
        self.assertEqual(results[1]['title'], "Second Regenerated Chapter")
        self.assertIn("Charles", results[1]['characters_present'])
        self.assertIn("Mystery Z", results[1]['new_plot_points_or_mysteries_introduced'])
        self.assertEqual(results[1]['estimated_words'], 1200)


    def test_llm_failure_empty_response(self):
        self.mock_llm_client.expected_responses = {"Regen from 1 to 1": ""}
        results = self.agent.regenerate_plot_segment(
            self.sample_outline, self.sample_worldview, [], 1, 1
        )
        self.assertEqual(len(results), 0, "Should return empty list on empty LLM response")

    def test_llm_failure_malformed_response(self):
        # This response lacks clear BEGIN/END CHAPTER or field structures
        malformed_response = "This is just a random string of text, not a chapter."
        self.mock_llm_client.expected_responses = {"Regen from 1 to 1": malformed_response}

        # The current mock parser in the test file might extract something basic.
        # The real agent's parser is more robust; this test checks if it falls back gracefully.
        # If the real parser (copied into the placeholder for testing) is robust, it might still create a default.
        # If the placeholder parser used here is very basic, it might return empty or error.
        # Let's assume the agent's _parse_regenerated_chapters_from_llm handles this by returning empty or a single error-like chapter.
        results = self.agent.regenerate_plot_segment(
            self.sample_outline, self.sample_worldview, [], 1, 1
        )

        if results: # If the parser created a fallback
            self.assertEqual(len(results), 1)
            self.assertIn("Parsing Failed", results[0]['title'], "Title should indicate parsing failure if fallback is created")
            self.assertIn("malformed", results[0]['core_scene_summary'].lower(), "Summary should indicate issue if fallback is created")
        else: # If parser returns empty on malformed
            self.assertEqual(len(results), 0, "Should return empty list or specific error placeholder on malformed response if parser cannot handle it")


if __name__ == '__main__':
    unittest.main()

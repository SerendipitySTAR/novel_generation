import re
from typing import List, Optional, Dict, Any
from src.llm_abstraction.llm_client import LLMClient
from src.core.models import PlotChapterDetail
import json # For parsing if needed, and for placeholder output

class PlotRegeneratorAgent:
    """
    Agent responsible for regenerating a segment of the plot based on preceding events
    and a new direction or requirement.
    """
    def __init__(self, llm_client: Optional[LLMClient] = None):
        """
        Initializes the PlotRegeneratorAgent.

        Args:
            llm_client: An instance of LLMClient. If None, a new one will be created.
        """
        self.llm_client = llm_client if llm_client else LLMClient()
        print("PlotRegeneratorAgent initialized.")

    def _get_field_value(
        self,
        field_name_variations: List[str],
        text_block: str,
        is_list: bool = False,
        block_chapter_num_for_logging: Optional[int] = None # Renamed for clarity
    ) -> Optional[Any]:
        """
        Helper function to extract a field value using a flexible regex pattern.
        Looks for the field name and captures content until the next field name or end of block.
        """
        # Construct a more flexible regex pattern for field variations.
        pattern_str = r"(?:^|\n)\s*(?:" + "|".join(re.escape(variation) for variation in field_name_variations) + r")\s*[:：]\s*(.*?)(?=\n\s*\w[\w\s()\-]*\s*[:：]|$)"
        match = re.search(pattern_str, text_block, re.IGNORECASE | re.MULTILINE | re.DOTALL)
        field_display_name = field_name_variations[0]

        if match:
            value = match.group(1).strip()
            if not value:
                print(f"PlotRegeneratorAgent: Warning (Ch {block_chapter_num_for_logging}) - Field '{field_display_name}' found but content is empty.")
                return None if not is_list else []
            if is_list:
                if value.lower() in ["none", "n/a"]: return []
                items = [s.strip() for s in value.split(',') if s.strip()]
                if len(items) == 1 and '\n' in items[0]:
                    print(f"PlotRegeneratorAgent: Info (Ch {block_chapter_num_for_logging}) - Field '{field_display_name}' has single comma-item with newlines, trying newline split.")
                    newline_items = [re.sub(r"^\s*[-*\d]+\.?\s*", "", li.strip()) for li in items[0].split('\n') if re.sub(r"^\s*[-*\d]+\.?\s*", "", li.strip())]
                    return newline_items if newline_items else (items if items[0] else [])
                return items
            return value
        return None

    def _parse_regenerated_chapters_from_llm(
        self,
        llm_response: str,
        num_chapters_to_parse: int,
        expected_start_chapter_number: int
    ) -> List[PlotChapterDetail]:
        """
        Parses the LLM response to extract detailed plot structures for regenerated chapters.
        Ensures correct chapter numbering for the regenerated segment.
        """
        chapters_details: List[PlotChapterDetail] = []

        # Use similar block parsing as PlotArchitectAgent
        # Prefer strict BEGIN/END, then fallback to BEGIN only
        chapter_blocks_info = []
        strict_block_regex = r"BEGIN CHAPTER\s*(\d+):\s*(.*?)\s*END CHAPTER\s*\1:" # LLM might output relative chapter numbers for the segment
        strict_matches = list(re.finditer(strict_block_regex, llm_response, re.IGNORECASE | re.DOTALL))

        if strict_matches:
            print(f"PlotRegeneratorAgent: Found {len(strict_matches)} chapter blocks using strict BEGIN/END pattern.")
            for match_idx, match in enumerate(strict_matches):
                # The chapter number from LLM (match.group(1)) is relative to the segment.
                # We will override it with absolute numbering.
                chapter_blocks_info.append({
                    "text": match.group(2).strip(),
                    "source": "strict",
                    "segment_index": match_idx # Index within the regenerated segment
                })
        else:
            print(f"PlotRegeneratorAgent: Info - Strict BEGIN/END pattern found no blocks. Trying fallback: split by 'BEGIN CHAPTER'.")
            fallback_block_regex = r"BEGIN CHAPTER\s*(\d+):\s*(.*?)(?=(?:BEGIN CHAPTER\s*\d+:)|$)"
            fallback_matches = list(re.finditer(fallback_block_regex, llm_response, re.IGNORECASE | re.DOTALL))
            if fallback_matches:
                print(f"PlotRegeneratorAgent: Found {len(fallback_matches)} chapter blocks using fallback BEGIN pattern.")
                for match_idx, match in enumerate(fallback_matches):
                    chapter_blocks_info.append({
                        "text": match.group(2).strip(),
                        "source": "fallback_begin_only",
                        "segment_index": match_idx
                    })
            else:
                print(f"PlotRegeneratorAgent: Error - No chapter blocks found using either strict or fallback BEGIN/END patterns.")
                return []


        parsed_chapters_count = 0
        for block_info in chapter_blocks_info:
            if parsed_chapters_count >= num_chapters_to_parse:
                print(f"PlotRegeneratorAgent: Warning - Parsed requested {num_chapters_to_parse} chapters, but more blocks found. Ignoring extras.")
                break

            # Key change: Determine absolute chapter number
            current_absolute_chapter_number = expected_start_chapter_number + block_info["segment_index"]
            block_text = block_info["text"]

            # Define field variations for parsing, similar to PlotArchitectAgent
            # These are the fields expected in PlotChapterDetail from the prompt
            field_parsers = {
                'title': (["Title"], False),
                'core_scene_summary': (["Core Scene Summary", "Main Scene", "Scene Summary", "Chapter Summary"], False),
                'key_events_and_plot_progression': (["Key Events and Plot Progression", "Key Events", "Events", "Plot Progression", "Plot Development"], False),
                'setting_and_atmosphere_description': (["Setting and Atmosphere Description", "Setting", "Atmosphere"], False),
                'characters_present': (["Characters Present", "Characters", "Appearing Characters"], True),
                'character_development_notes': (["Character Development Notes", "Character Arcs", "Development Notes"], False),
                'plot_points_to_resolve_from_previous': (["Plot Points to Resolve from Previous", "Resolve Plot Points", "Resolved Points"], True),
                'new_plot_points_or_mysteries_introduced': (["New Plot Points or Mysteries Introduced", "New Mysteries", "Introduced Plot Points"], True),
                'estimated_word_count_str': (["Estimated Word Count", "Est. Words", "Word Count", "Approximate Words"], False)
            }

            parsed_content: Dict[str, Any] = {}
            for field_key, (variations, is_list_type) in field_parsers.items():
                parsed_value = self._get_field_value(variations, block_text, is_list_type, current_absolute_chapter_number)
                parsed_content[field_key] = parsed_value
                if parsed_value is None and not (is_list_type and parsed_value == []):
                     print(f"PlotRegeneratorAgent: Warning (Abs Ch {current_absolute_chapter_number}) - Field '{variations[0]}' not found or empty. Block snippet: '{block_text[:100]}...'")

            # Construct PlotChapterDetail, ensuring chapter_number is correctly set
            detail = PlotChapterDetail(
                chapter_number=current_absolute_chapter_number, # Critical: Use absolute chapter number
                title=parsed_content.get('title') or f"Regenerated Chapter {current_absolute_chapter_number} (Title TBD)",
                core_scene_summary=parsed_content.get('core_scene_summary') or "Scene summary to be determined.",
                key_events_and_plot_progression=parsed_content.get('key_events_and_plot_progression') or "Plot progression to be determined.",
                setting_and_atmosphere_description=parsed_content.get('setting_and_atmosphere_description') or "Setting to be determined.",
                characters_present=parsed_content.get('characters_present') if parsed_content.get('characters_present') is not None else [],
                character_development_notes=parsed_content.get('character_development_notes') or "Character development notes to be determined.",
                plot_points_to_resolve_from_previous=parsed_content.get('plot_points_to_resolve_from_previous') if parsed_content.get('plot_points_to_resolve_from_previous') is not None else [],
                new_plot_points_or_mysteries_introduced=parsed_content.get('new_plot_points_or_mysteries_introduced') if parsed_content.get('new_plot_points_or_mysteries_introduced') is not None else [],
                estimated_words=1000, # Default, will be updated
                raw_llm_output_for_chapter=block_text
            )

            if parsed_content.get('estimated_word_count_str'):
                num_match = re.search(r'\d+', parsed_content['estimated_word_count_str'])
                if num_match:
                    try: detail['estimated_words'] = int(num_match.group(0))
                    except ValueError: print(f"PlotRegeneratorAgent: Warning (Abs Ch {current_absolute_chapter_number}) - Could not convert estimated_words '{parsed_content['estimated_word_count_str']}' to int.")
                else:
                    print(f"PlotRegeneratorAgent: Warning (Abs Ch {current_absolute_chapter_number}) - No number found in estimated_words string: '{parsed_content['estimated_word_count_str']}'.")

            chapters_details.append(detail)
            parsed_chapters_count += 1

        if not chapters_details and llm_response.strip():
            print(f"PlotRegeneratorAgent: Error - No chapter blocks parsed even with fallbacks. Treating response as single raw block for chapter {expected_start_chapter_number}.")
            # Create a minimal default chapter detail if all parsing fails
            default_chapter_detail = PlotChapterDetail(
                chapter_number=expected_start_chapter_number,
                title=f"Regenerated Chapter {expected_start_chapter_number} (Parsing Failed)",
                raw_llm_output_for_chapter=llm_response.strip(),
                core_scene_summary="Scene details to be determined - parsing failed.",
                key_events_and_plot_progression="Plot progression to be determined - parsing failed.",
                setting_and_atmosphere_description="N/A", characters_present=[], character_development_notes="N/A",
                plot_points_to_resolve_from_previous=[], new_plot_points_or_mysteries_introduced=[],
                estimated_words=1000
            )
            chapters_details.append(default_chapter_detail)
        elif len(chapters_details) < num_chapters_to_parse:
             print(f"PlotRegeneratorAgent: Warning - Expected {num_chapters_to_parse} chapters, but only parsed {len(chapters_details)} structured blocks successfully.")

        if chapters_details:
             print(f"PlotRegeneratorAgent: Successfully parsed {len(chapters_details)} regenerated chapter structures from {len(chapter_blocks_info)} detected blocks.")
        else:
            print(f"PlotRegeneratorAgent: Error - No regenerated plot summaries could be parsed even with fallbacks.")

        return chapters_details

    def regenerate_plot_segment(
        self,
        narrative_outline: str,
        worldview_data: str, # Assuming this is a string summary of worldview
        preceding_plot_details: List[PlotChapterDetail],
        regeneration_start_chapter: int,
        desired_total_chapters: int
    ) -> List[PlotChapterDetail]:
        print("\n--- PlotRegeneratorAgent: regenerate_plot_segment called ---")
        # (Debug prints for arguments remain as they were)
        print(f"Narrative Outline (snippet): {narrative_outline[:100]}...")
        print(f"Worldview Data (snippet): {worldview_data[:100]}...")
        print(f"Number of preceding plot details: {len(preceding_plot_details)}")
        if preceding_plot_details:
            print(f"Last preceding chapter title: {preceding_plot_details[-1].get('title', 'N/A')}")
        print(f"Regeneration Start Chapter: {regeneration_start_chapter}")
        print(f"Desired Total Chapters: {desired_total_chapters}")

        num_chapters_to_generate_in_segment = desired_total_chapters - regeneration_start_chapter + 1

        if num_chapters_to_generate_in_segment <= 0:
            print("Warning: No new chapters to generate based on start and desired total chapters.")
            return []

        preceding_summary = "\n".join(
            [
                f"Chapter {p.get('chapter_number', 'N/A')}: {p.get('title', 'Untitled')}\n"
                f"Summary: {p.get('core_scene_summary', 'N/A')}\n"
                f"Key Events: {p.get('key_events_and_plot_progression', 'N/A')}\n"
                for p in preceding_plot_details
            ]
        )
        if not preceding_plot_details:
            preceding_summary = "This is the beginning of the novel, or the preceding plot is not provided."

        prompt = f"""
You are a master storyteller and plot architect. Your task is to regenerate a segment of a novel's plot.
The novel is based on the following overall narrative outline and worldview:

Narrative Outline:
{narrative_outline}

Worldview:
{worldview_data}

The plot up to the point of regeneration is summarized as follows:
--- BEGIN PRECEDING PLOT SUMMARY ---
{preceding_summary}
--- END PRECEDING PLOT SUMMARY ---

Now, you need to generate detailed plot points for {num_chapters_to_generate_in_segment} new chapter(s), which will be Chapters {regeneration_start_chapter} through {desired_total_chapters} of the novel.
Ensure the new plot segment logically follows from the preceding summary and aligns with the overall narrative outline and worldview.
The output must be in the same format as the PlotArchitectAgent, using 'BEGIN CHAPTER X' and 'END CHAPTER X' markers for each chapter.
IMPORTANT: The chapter numbers (X) in your "BEGIN CHAPTER X" and "END CHAPTER X" markers should be relative to the segment you are generating (e.g., start with "BEGIN CHAPTER 1", then "BEGIN CHAPTER 2", etc., if you are generating multiple chapters for this segment). The absolute chapter numbering will be handled by the system.

For each chapter, provide the following details in a structured format:
- chapter_number: int (The RELATIVE chapter number within this generated segment, e.g., 1, 2, ...)
- title: str
- core_scene_summary: str
- key_events_and_plot_progression: str
- setting_and_atmosphere_description: str
- characters_present: List[str]
- character_development_notes: str
- plot_points_to_resolve_from_previous: List[str] (Refer to events/points from the PRECEDING PLOT SUMMARY or earlier chapters in THIS segment)
- new_plot_points_or_mysteries_introduced: List[str]
- estimated_word_count: int

Example for the first chapter of the segment you generate:
BEGIN CHAPTER 1
chapter_number: 1
title: "A New Direction"
core_scene_summary: "The protagonist reacts to the last event of the preceding plot and decides on a new course."
key_events_and_plot_progression: "Event Alpha happens, leading to Character Omega doing Action Gamma."
setting_and_atmosphere_description: "A vibrant market, full of sounds and smells, yet with an undercurrent of tension."
characters_present: ["Protagonist A", "New Character D"]
character_development_notes: "Protagonist A shows resilience."
plot_points_to_resolve_from_previous: ["The cliffhanger from the last preceding chapter."]
new_plot_points_or_mysteries_introduced: ["A mysterious note is found."]
estimated_word_count: 1600
END CHAPTER 1

Generate all {num_chapters_to_generate_in_segment} chapters for this segment now.
"""
        print("\n--- Generated Prompt for LLM (snippet) ---")
        print(prompt[:500] + "...")
        print("--- End of Prompt Snippet ---")

        try:
            # Consider dynamic token calculation based on num_chapters_to_generate_in_segment
            max_tokens_for_regeneration = (1000 * num_chapters_to_generate_in_segment) + 500 # Rough estimate
            raw_llm_response = self.llm_client.generate_text(prompt, max_tokens=max_tokens_for_regeneration)
            if not raw_llm_response:
                print("Error: LLM returned an empty response for plot regeneration.")
                return []
            print("\n--- Raw LLM Response for Regeneration (snippet) ---")
            print(raw_llm_response[:500] + "...")
            print("--- End of LLM Response Snippet ---")
        except Exception as e:
            print(f"Error during LLM call for plot regeneration: {e}")
            return []

        regenerated_plot_details = self._parse_regenerated_chapters_from_llm(
            llm_response=raw_llm_response,
            num_chapters_to_parse=num_chapters_to_generate_in_segment,
            expected_start_chapter_number=regeneration_start_chapter
        )

        print(f"\n--- Regenerated Plot Segment Details (Count: {len(regenerated_plot_details)}) ---")
        for i, detail in enumerate(regenerated_plot_details):
            print(f"  Parsed Segment Chapter {i+1} (Absolute Novel Chapter {detail.get('chapter_number', 'N/A')}): {detail.get('title', 'N/A')} (Word Count: {detail.get('estimated_word_count', 0)})")
            if i == 0 and len(regenerated_plot_details) > 1 : print("  ...")
            elif i > 0 : break

        return regenerated_plot_details

if __name__ == "__main__":
    print("--- PlotRegeneratorAgent Test ---")
    # This test setup assumes LLMClient can be instantiated,
    # potentially requiring OPENAI_API_KEY environment variable.
    try:
        # Mock LLMClient for testing without actual API calls
        class MockLLMClient(LLMClient):
            def __init__(self, api_key: Optional[str] = None):
                super().__init__(api_key="sk-dummykeyformock") # Ensure it can init
                print("MockLLMClient initialized for PlotRegeneratorAgent test.")

            def generate_text(self, prompt: str, model_name: Optional[str] = None, max_tokens: Optional[int] = None, temperature: Optional[float] = None) -> str:
                print(f"MockLLMClient.generate_text called. Max tokens: {max_tokens}")
                # Simulate LLM response based on prompt for regeneration
                # This response should contain 2 chapters for the sample call below.
                # It uses relative chapter numbering (1 and 2 for the segment).
                return """
BEGIN CHAPTER 1:
chapter_number: 1
title: "The Altered Path"
core_scene_summary: "Following the discovery, Hero A finds the world subtly changed."
key_events_and_plot_progression: "Hero A revisits the library, finds Librarian B acting strangely. A clue from the map leads to a hidden district."
setting_and_atmosphere_description: "The once familiar library now feels alien. The hidden district is dark and foreboding."
characters_present: ["Hero A", "Librarian B"]
character_development_notes: "Hero A becomes more suspicious and determined."
plot_points_to_resolve_from_previous: ["What does the map lead to?"]
new_plot_points_or_mysteries_introduced: ["Why is Librarian B different?", "What is the nature of the hidden district?"]
estimated_word_count: 1200
END CHAPTER 1:

BEGIN CHAPTER 2:
chapter_number: 2
title: "Echoes in the Dark"
core_scene_summary: "Hero A explores the hidden district and encounters a new challenge."
key_events_and_plot_progression: "Hero A navigates the treacherous paths of the district, evades a patrol of Silencers (first encounter), and finds a hidden message."
setting_and_atmosphere_description: "Oppressive darkness, sounds of unknown origin, constant sense of being watched."
characters_present: ["Hero A", "Silencer Patrol (briefly)"]
character_development_notes: "Hero A learns to be more cautious and resourceful."
plot_points_to_resolve_from_previous: ["What is the nature of the hidden district?"]
new_plot_points_or_mysteries_introduced: ["Who are the Silencers?", "What does the hidden message mean?"]
estimated_word_count: 1300
END CHAPTER 2:
                """

        mock_llm = MockLLMClient()
        regenerator = PlotRegeneratorAgent(llm_client=mock_llm)

        sample_outline = "A hero discovers a conspiracy in a magical kingdom."
        sample_worldview = "Magic is fading, and technology is on the rise, causing social unrest."
        sample_preceding_plot = [
            PlotChapterDetail(
                chapter_number=1, title="The Discovery", core_scene_summary="Hero finds artifact.",
                key_events_and_plot_progression="Map found.", setting_and_atmosphere_description="Library.",
                characters_present=["Hero A"], character_development_notes="Curious.",
                plot_points_to_resolve_from_previous=[], new_plot_points_or_mysteries_introduced=["Map's purpose?"],
                estimated_words=1000
            )
        ]
        start_regen_chap = 2
        total_chaps = 3 # Regen chapters 2 and 3 (2 chapters in segment)

        print(f"\nCalling regenerate_plot_segment for chapters {start_regen_chap}-{total_chaps}...")
        regenerated_segment = regenerator.regenerate_plot_segment(
            narrative_outline=sample_outline, worldview_data=sample_worldview,
            preceding_plot_details=sample_preceding_plot,
            regeneration_start_chapter=start_regen_chap, desired_total_chapters=total_chaps
        )

        if regenerated_segment:
            print(f"\nSuccessfully regenerated and parsed {len(regenerated_segment)} chapter(s):")
            for chapter_detail in regenerated_segment:
                print(f"  Novel Chapter {chapter_detail.get('chapter_number')}: {chapter_detail.get('title')}")
                assert isinstance(chapter_detail.get('chapter_number'), int), \
                    f"Chapter number {chapter_detail.get('chapter_number')} is not an int!"
                assert chapter_detail.get('chapter_number') >= start_regen_chap, \
                    f"Absolute chapter number {chapter_detail.get('chapter_number')} is less than expected start {start_regen_chap}"

            # Check specific chapter numbers
            if len(regenerated_segment) == 2:
                assert regenerated_segment[0].get('chapter_number') == 2, f"First regenerated chapter number is {regenerated_segment[0].get('chapter_number')}, expected 2"
                assert regenerated_segment[1].get('chapter_number') == 3, f"Second regenerated chapter number is {regenerated_segment[1].get('chapter_number')}, expected 3"
                print("Chapter numbering seems correct for the regenerated segment.")
        else:
            print("\nPlot segment regeneration returned no chapters or failed parsing with mock.")

    except Exception as e:
        print(f"An error occurred during the test: {e}")
        import traceback
        traceback.print_exc()

    print("\n--- PlotRegeneratorAgent Test Finished ---")

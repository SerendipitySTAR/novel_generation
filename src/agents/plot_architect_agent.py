import re
from typing import List, Optional, Dict, Any # Added Dict, Any
from src.llm_abstraction.llm_client import LLMClient
from src.core.models import PlotChapterDetail
import os
import json
import traceback
from dotenv import load_dotenv
import openai

class PlotArchitectAgent:
    """
    Generates a detailed chapter-by-chapter plot structure for a novel,
    based on a narrative outline and worldview. Each chapter's plot includes
    fields like title, scene summaries, key events, characters, tone, etc.
    (defined in PlotChapterDetail TypedDict).
    """
    def __init__(self):
        try:
            self.llm_client = LLMClient()
        except ValueError as e:
            print(f"PlotArchitectAgent Error: LLMClient initialization failed. {e}")
            print("Please ensure OPENAI_API_KEY is set in your environment or .env file.")
            raise
        except Exception as e:
            print(f"PlotArchitectAgent Error: An unexpected error occurred during LLMClient initialization: {e}")
            raise

    def _construct_prompt(self, narrative_outline: str, worldview_data: str, num_chapters: int = 3) -> str:
        # Prompt designed to elicit detailed structured information for each chapter,
        # using "BEGIN CHAPTER X:" and "END CHAPTER X:" as primary delimiters.
        chapter_prompts_text = []
        for i in range(1, num_chapters + 1):
            chapter_template = f"""BEGIN CHAPTER {i}:
Title: [Compelling Title for this Chapter]
Estimated Words: [Approximate word count, e.g., 1200]
Core Scene Summary: [1-3 sentences describing the main scene(s) or setting of this chapter.]
Characters Present: [Comma-separated list of significant character names appearing in this chapter. If none, write "None".]
Key Events and Plot Progression: [Bulleted list or paragraph detailing the key events, character actions, and how the plot advances in this chapter.]
Goal and Conflict: [Describe the main goal for the protagonist(s) in this chapter and the primary conflict they face.]
Turning Point: [Describe any significant turning point or revelation within this chapter. If none, write "None".]
Tone and Style Notes: [Brief notes on the desired tone, mood, or narrative style for this chapter, e.g., "Suspenseful, fast-paced action", "Introspective, melancholic".]
Suspense or Hook: [Describe any cliffhanger, foreshadowing, or hook leading to the next chapter. If none, write "None".]
END CHAPTER {i}:"""
            chapter_prompts_text.append(chapter_template)

        all_chapter_structures_string = "\n\n".join(chapter_prompts_text)

        prompt = f"""You are a meticulous Plot Architect, tasked with creating a detailed plot structure for a novel.
Based on the provided Narrative Outline and Worldview Data, generate detailed information for EXACTLY {num_chapters} chapters.

For EACH chapter, you MUST provide the following fields, using the exact headings as shown, each on a new line:

{all_chapter_structures_string}

Do not add any commentary or text outside of this structure for each chapter.
Ensure there is a blank line after "END CHAPTER X:" before the next "BEGIN CHAPTER X+1:" (if applicable for {num_chapters} > 1).

# General Guidance for Content Quality - Added to improve creative output and coherence.
General Guidance for Content Quality:
- For each chapter's "Key Events and Plot Progression": Ensure these events create a clear cause-and-effect chain and build towards the chapter's Turning Point or the main Goal.
- For "Goal and Conflict": Make the conflict tangible and specific to this chapter. What obstacles must be overcome related to the goal?
- For "Turning Point": This should be a significant shift or revelation. If it's a minor chapter, it could be a smaller realization or decision.
- For "Suspense or Hook": Craft a compelling reason for the reader to engage with the next chapter. This could be an unanswered question, a new threat, or a character left in a precarious situation.
- Aim for unique and engaging ideas for each chapter that fit the overall Narrative Outline and Worldview. Avoid overly generic plot devices unless they serve a specific, creative purpose.
- Ensure details across chapters show a progression and do not contradict each other unless intentional (e.g. a misleading clue).

---
Narrative Outline:
{narrative_outline}
---
Worldview Data:
{worldview_data}
---

Please generate the detailed plot for {num_chapters} chapters now, following the specified format strictly and adhering to the content quality guidance.
"""
        return prompt

    def _parse_llm_response_to_list(self, llm_response: str, num_chapters: int) -> List[PlotChapterDetail]:
        # Primary parsing strategy:
        # 1. Split the entire LLM response into major blocks, one for each chapter,
        #    using "BEGIN CHAPTER X:" and "END CHAPTER X:" as delimiters.
        # 2. For each chapter block, attempt to parse individual fields (Title, Estimated Words, etc.)
        #    using regex tailored for each field, looking for "FieldName: value" patterns.
        #    These field regexes use a lookahead to capture multi-line content.
        # 3. Store the raw text of each chapter's block in 'raw_llm_output_for_chapter' for debugging.
        # 4. Implement fallbacks if primary parsing fails.
        chapters_details: List[PlotChapterDetail] = []

        # Helper function to extract a field value using a more flexible regex pattern
        # that looks for the field name and captures content until the next field name or end of block.
        def get_field_value(
            field_name_variations: List[str],
            text_block: str,
            is_list: bool = False,
            block_chapter_num: Optional[int] = None # For logging
            ) -> Optional[Any]:

            # Construct a regex pattern for field variations.
            # Example: (?:Title|Chapter Title|Header):
            # Captures content until the next potential field heading or end of string.
            # The lookahead `(?=\n\s*\w[\w\s()]*:|$)` tries to stop before a line that looks like "AnotherField: ..."
            # or end of string if no such line is found.
            pattern_str = r"^(?:" + "|".join(re.escape(variation) for variation in field_name_variations) + r"):\s*(.*?)(?=\n\s*\w[\w\s()\-]*:|$)"

            match = re.search(pattern_str, text_block, re.IGNORECASE | re.MULTILINE | re.DOTALL)

            field_display_name = field_name_variations[0] # For logging

            if match:
                value = match.group(1).strip()
                if not value: # If value is empty string after strip.
                    print(f"PlotArchitectAgent: Warning (Ch {block_chapter_num}) - Field '{field_display_name}' found but content is empty.")
                    return None if not is_list else []

                if is_list:
                    # Handle "None", "N/A", or empty string for lists
                    if value.lower() in ["none", "n/a"]:
                        return []

                    # Try splitting by comma first
                    items = [s.strip() for s in value.split(',') if s.strip()]

                    # If comma splitting results in a single item that contains newlines,
                    # it might be a bulleted or numbered list.
                    if len(items) == 1 and '\n' in items[0]:
                        print(f"PlotArchitectAgent: Info (Ch {block_chapter_num}) - Field '{field_display_name}' has single comma-item with newlines, trying newline split.")
                        # Split by newline, then strip common list markers (bullets, numbers)
                        newline_items = []
                        for line_item in items[0].split('\n'):
                            line_item_stripped = line_item.strip()
                            # Remove leading bullets/numbers like "*- ", "1. ", "- " etc.
                            line_item_cleaned = re.sub(r"^\s*[-*\d]+\.?\s*", "", line_item_stripped)
                            if line_item_cleaned: # Add if not empty after cleaning
                                newline_items.append(line_item_cleaned)
                        if newline_items: # If newline splitting yielded results
                            return newline_items
                        else: # If newline splitting also failed to yield multiple items, return original single item list
                            print(f"PlotArchitectAgent: Warning (Ch {block_chapter_num}) - Field '{field_display_name}' newline split for list resulted in no items. Original: '{items[0]}'")
                            return items if items[0] else [] # return the original single item if it's not empty, else empty list
                    return items
                return value
            else:
                # This print warning is now part of the main loop for clarity
                # print(f"PlotArchitectAgent: Warning (Ch {block_chapter_num}) - Field '{field_display_name}' not found in chapter block.")
                pass
            return None

        # --- Main Parsing Logic ---
        # Attempt 1: Strict BEGIN CHAPTER X: ... END CHAPTER X:
        chapter_blocks = []
        strict_block_regex = r"BEGIN CHAPTER\s*(\d+):\s*(.*?)\s*END CHAPTER\s*\1:"
        strict_matches = list(re.finditer(strict_block_regex, llm_response, re.IGNORECASE | re.DOTALL))

        if strict_matches:
            print(f"PlotArchitectAgent: Found {len(strict_matches)} chapter blocks using strict BEGIN/END pattern.")
            for match in strict_matches:
                chapter_blocks.append({
                    "number_str": match.group(1).strip(),
                    "text": match.group(2).strip(),
                    "source": "strict"
                })
        else:
            # Attempt 2: Fallback - Split by "BEGIN CHAPTER X:"
            print(f"PlotArchitectAgent: Info - Strict BEGIN/END pattern found no blocks. Trying fallback: split by 'BEGIN CHAPTER'.")
            # Regex to find "BEGIN CHAPTER X:" and capture X and the text following it.
            # The text following is captured non-greedily (.*?) up to the next "BEGIN CHAPTER" or end of string.
            fallback_block_regex = r"BEGIN CHAPTER\s*(\d+):\s*(.*?)(?=(?:BEGIN CHAPTER\s*\d+:)|$)"
            fallback_matches = list(re.finditer(fallback_block_regex, llm_response, re.IGNORECASE | re.DOTALL))

            if fallback_matches:
                print(f"PlotArchitectAgent: Found {len(fallback_matches)} chapter blocks using fallback BEGIN pattern.")
                for match in fallback_matches:
                    chapter_blocks.append({
                        "number_str": match.group(1).strip(),
                        "text": match.group(2).strip(), # Content until next BEGIN or EOS
                        "source": "fallback_begin_only"
                    })
            else:
                print(f"PlotArchitectAgent: Error - No chapter blocks found using either strict or fallback BEGIN/END patterns.")


        parsed_chapters_count = 0
        for block_info in chapter_blocks:
            if parsed_chapters_count >= num_chapters:
                print(f"PlotArchitectAgent: Warning - Parsed requested {num_chapters} chapters, but more blocks found ({block_info['source']} source). Ignoring extras.")
                break

            try:
                chapter_num_from_block = int(block_info["number_str"])
            except ValueError:
                print(f"PlotArchitectAgent: Warning - Could not parse chapter number '{block_info['number_str']}' from block. Skipping block.")
                continue

            block_text = block_info["text"]

            details = PlotChapterDetail(
                chapter_number=chapter_num_from_block,
                title=None, estimated_words=None, core_scene_summary=None,
                characters_present=None, key_events_and_plot_progression=None,
                goal_and_conflict=None, turning_point=None, tone_and_style_notes=None,
                suspense_or_hook=None, raw_llm_output_for_chapter=block_text
            )

            field_parsers = {
                'title': (["Title"], False),
                'estimated_words_str': (["Estimated Words", "Est. Words", "Word Count", "Approximate Words"], False),
                'core_scene_summary': (["Core Scene Summary", "Main Scene", "Scene Summary", "Chapter Summary"], False),
                'characters_present': (["Characters Present", "Characters", "Appearing Characters"], True),
                'key_events_and_plot_progression': (["Key Events and Plot Progression", "Key Events", "Events", "Plot Progression", "Plot Development"], False),
                'goal_and_conflict': (["Goal and Conflict", "Goal & Conflict", "Goal/Conflict", "Chapter Goal", "Main Conflict"], False),
                'turning_point': (["Turning Point", "Turning Points", "Key Revelation"], False),
                'tone_and_style_notes': (["Tone and Style Notes", "Tone & Style", "Tone", "Style Notes", "Narrative Style"], False),
                'suspense_or_hook': (["Suspense or Hook", "Suspense/Hook", "Hook", "Cliffhanger", "Next Chapter Hook"], False)
            }

            parsed_values = {}
            for field_key, (variations, is_list_type) in field_parsers.items():
                parsed_values[field_key] = get_field_value(variations, block_text, is_list_type, chapter_num_from_block)
                if parsed_values[field_key] is None and not (is_list_type and parsed_values[field_key] == []): # Check for None, not empty list
                    print(f"PlotArchitectAgent: Warning (Ch {chapter_num_from_block}) - Field '{variations[0]}' not found or empty in chapter block. Block snippet: '{block_text[:100]}...'")


            details['title'] = parsed_values['title'] or f"Chapter {chapter_num_from_block} (Title TBD)"

            if parsed_values['estimated_words_str']:
                num_match = re.search(r'\d+', parsed_values['estimated_words_str'])
                if num_match:
                    try: details['estimated_words'] = int(num_match.group(0))
                    except ValueError: print(f"PlotArchitectAgent: Warning (Ch {chapter_num_from_block}) - Could not convert estimated_words '{parsed_values['estimated_words_str']}' to int.")
                else:
                    print(f"PlotArchitectAgent: Warning (Ch {chapter_num_from_block}) - No number found in estimated_words string: '{parsed_values['estimated_words_str']}'.")

            details['core_scene_summary'] = parsed_values['core_scene_summary']
            details['characters_present'] = parsed_values['characters_present'] if parsed_values['characters_present'] is not None else []
            details['key_events_and_plot_progression'] = parsed_values['key_events_and_plot_progression']
            details['goal_and_conflict'] = parsed_values['goal_and_conflict']
            details['turning_point'] = parsed_values['turning_point']
            details['tone_and_style_notes'] = parsed_values['tone_and_style_notes']
            details['suspense_or_hook'] = parsed_values['suspense_or_hook']

            chapters_details.append(details)
            parsed_chapters_count += 1

        if not chapters_details and llm_response.strip():
            # This case is less likely now with the fallback BEGIN CHAPTER split, but kept as a final safety net.
            print(f"PlotArchitectAgent: Error - No chapter blocks parsed even with fallbacks. Treating response as single raw block for chapter 1. Response: {llm_response[:500]}")
            # Create a default chapter detail if all parsing fails but there's content
            default_chapter_detail = PlotChapterDetail(
                chapter_number=1,
                title="Chapter 1 (Global Parsing Error)",
                raw_llm_output_for_chapter=llm_response.strip(),
                estimated_words=None, core_scene_summary=None, characters_present=[],
                key_events_and_plot_progression=None, goal_and_conflict=None,
                turning_point=None, tone_and_style_notes=None, suspense_or_hook=None
            )
            chapters_details.append(default_chapter_detail)

        elif len(chapters_details) < num_chapters:
            print(f"PlotArchitectAgent: Warning - Expected {num_chapters} chapters, but only parsed {len(chapters_details)} structured blocks successfully.")

        if chapters_details:
             print(f"PlotArchitectAgent: Successfully parsed {len(chapters_details)} chapter structures from {len(chapter_blocks)} detected blocks.")
        else:
            print(f"PlotArchitectAgent: Error - No plot summaries could be parsed even with fallbacks.")

        return chapters_details

    def generate_plot_points(self, narrative_outline: str, worldview_data: str, num_chapters: int = 3) -> List[PlotChapterDetail]:
        if not narrative_outline: raise ValueError("Narrative outline cannot be empty.")
        if not worldview_data: raise ValueError("Worldview data cannot be empty.")
        if num_chapters <= 0: raise ValueError("Number of chapters must be positive.")

        prompt = self._construct_prompt(narrative_outline, worldview_data, num_chapters)
        print(f"PlotArchitectAgent: Sending prompt for {num_chapters} detailed chapter structures to LLM.")

        # max_tokens needs to be substantial to accommodate detailed output for multiple chapters.
        # Estimate tokens: Each field might be 50-100 words. ~9 fields = 450-900 words per chapter.
        # 900 words * 1.33 tokens/word = ~1200 tokens per chapter.
        # For 3 chapters: ~3600 tokens. Add prompt and buffer.
        estimated_tokens_per_detailed_chapter = 1200
        total_max_tokens = (estimated_tokens_per_detailed_chapter * num_chapters) + 600

        try:
            llm_response_text = self.llm_client.generate_text(
                prompt=prompt, model_name="gpt-3.5-turbo", max_tokens=total_max_tokens
            )
            print("PlotArchitectAgent: Received detailed chapter structures text from LLM.")
            parsed_chapter_details = self._parse_llm_response_to_list(llm_response_text, num_chapters)
            if not parsed_chapter_details:
                 print(f"PlotArchitectAgent: No detailed chapter structures were parsed. LLM response might have been empty or unparsable. Snippet: {llm_response_text[:300]}")
                 return [] # Return empty list if nothing usable parsed
            print(f"PlotArchitectAgent: Parsed {len(parsed_chapter_details)} detailed chapter structures.")
            return parsed_chapter_details
        except Exception as e:
            print(f"PlotArchitectAgent: Error during LLM call or parsing - {e}")
            raise

if __name__ == "__main__":
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")

    print("--- Testing PlotArchitectAgent (Live LLM Call for Detailed Chapter Structures) ---")
    print("IMPORTANT: This test requires a valid OPENAI_API_KEY set in your environment or .env file.")
    if not api_key or api_key == "your_openai_api_key_here" or "dummykey" in api_key.lower() :
        print("----------------------------------------------------------------------")
        print("WARNING: Valid OPENAI_API_KEY not found or is a placeholder/dummy.")
        print("LLM call will be skipped. To test fully, set a real API key.")
        print("----------------------------------------------------------------------")

    sample_narrative_outline = (
        "A young librarian in a city where books can whisper secrets discovers that "
        "a shadowy organization is stealing unique books to silence them. "
        "She must team up with a skeptical detective to uncover the plot before all "
        "knowledge is controlled."
    )
    sample_worldview_data = (
        "The city of Aethelburg, a technologically advanced metropolis that coexists with ancient libraries "
        "and guilds. Books are sentient to varying degrees; some only whisper emotions, others can hold "
        "full conversations. The 'Silencers' are a clandestine group believing uncontrolled knowledge leads to chaos."
    )
    num_chapters_to_generate = 2

    print(f"\nTarget Chapters: {num_chapters_to_generate}")
    print(f"Outline: {sample_narrative_outline}")
    print(f"Worldview: {sample_worldview_data}\n")

    agent = PlotArchitectAgent()

    try:
        print("Attempting to generate detailed plot structures...")

        prompt_for_llm = agent._construct_prompt(
            sample_narrative_outline,
            sample_worldview_data,
            num_chapters_to_generate
        )
        print("--- Generated Prompt for LLM (first 500 chars) ---")
        print(prompt_for_llm[:500] + "...")
        print("--------------------------------------------------\n")

        # Only proceed with LLM call if a potentially valid key is present
        if api_key and api_key != "your_openai_api_key_here" and "dummykey" not in api_key.lower():
            configured_max_tokens = (1200 * num_chapters_to_generate) + 600
            print(f"Agent is configured to use max_tokens={configured_max_tokens} for the actual call in generate_plot_points.")

            raw_llm_response = agent.llm_client.generate_text(
                prompt=prompt_for_llm,
                max_tokens=configured_max_tokens
            )
            print("--- Raw LLM Response ---")
            print(raw_llm_response) # Print the full raw response for debugging
            print("------------------------\n")

            print("--- Parsing LLM Response (using agent's _parse_llm_response_to_list) ---")
            parsed_plot_details = agent._parse_llm_response_to_list(raw_llm_response, num_chapters_to_generate)

            print("\n--- Parsed PlotChapterDetail Objects ---")
            if parsed_plot_details:
                print(json.dumps(parsed_plot_details, indent=2))
            else:
                print("No plot details were parsed from the raw response.")
        else:
            print("SKIPPED live LLM call due to missing or dummy API key.")
            print("To test parsing, you would manually paste an LLM response into the parser method or use the full generate_plot_points() method.")

    except openai.APIError as e:
        print(f"\n!!! OpenAI API Error: {e} !!!")
        print("This usually means an issue with your API key, organization, or network.")
    except ValueError as ve:
        print(f"\n!!! Configuration Error: {ve} !!!")
    except Exception as e:
        print(f"\n!!! An unexpected error occurred: {e} !!!")
        traceback.print_exc()

    print("\n--- PlotArchitectAgent Test Finished ---")

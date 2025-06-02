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

---
Narrative Outline:
{narrative_outline}
---
Worldview Data:
{worldview_data}
---

Please generate the detailed plot for {num_chapters} chapters now, following the specified format strictly.
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

        # Helper function to extract a field value
        def get_field_value(pattern: str, text_block: str, is_list: bool = False) -> Optional[Any]:
            # Use re.MULTILINE to ensure ^ matches the start of each line within the block
            match = re.search(pattern, text_block, re.IGNORECASE | re.MULTILINE | re.DOTALL)
            if match:
                value = match.group(1).strip()
                if is_list:
                    if value.lower() in ["none", "n/a", ""]:
                        return [] # Return empty list for "None" or empty
                    return [s.strip() for s in value.split(',') if s.strip()]
                return value
            return None

        chapter_block_regex = r"BEGIN CHAPTER\s*(\d+):\s*(.*?)\s*END CHAPTER\s*\1:"
        matches = re.finditer(chapter_block_regex, llm_response, re.IGNORECASE | re.DOTALL)

        parsed_chapters_count = 0
        for match in matches:
            if parsed_chapters_count >= num_chapters:
                print(f"PlotArchitectAgent: Warning - Parsed requested {num_chapters} chapters, but more BEGIN/END blocks found. Ignoring extras.")
                break

            chapter_num_from_block = int(match.group(1).strip())
            block_text = match.group(2).strip()

            details = PlotChapterDetail(
                chapter_number=chapter_num_from_block,
                title=None, estimated_words=None, core_scene_summary=None,
                characters_present=None, key_events_and_plot_progression=None,
                goal_and_conflict=None, turning_point=None, tone_and_style_notes=None,
                suspense_or_hook=None, raw_llm_output_for_chapter=block_text
            )

            details['title'] = get_field_value(r"^Title:\s*(.*)", block_text) or f"Chapter {chapter_num_from_block} (Title TBD)"

            est_words_str = get_field_value(r"^(?:Estimated Words|Est\. Words|Word Count):\s*(.*)", block_text)
            if est_words_str:
                num_match = re.search(r'\d+', est_words_str)
                if num_match:
                    try: details['estimated_words'] = int(num_match.group(0))
                    except ValueError: print(f"PlotArchitectAgent: Warning - Could not convert estimated_words '{est_words_str}' to int for chapter {chapter_num_from_block}.")

            details['core_scene_summary'] = get_field_value(r"^(?:Core Scene Summary|Main Scene|Scene Summary):\s*(.*)", block_text)
            details['characters_present'] = get_field_value(r"^(?:Characters Present|Characters):\s*(.*)", block_text, is_list=True)
            details['key_events_and_plot_progression'] = get_field_value(r"^(?:Key Events and Plot Progression|Key Events|Events|Plot Progression):\s*(.*)", block_text)
            details['goal_and_conflict'] = get_field_value(r"^(?:Goal and Conflict|Goal & Conflict|Goal/Conflict):\s*(.*)", block_text)
            details['turning_point'] = get_field_value(r"^(?:Turning Point|Turning Points):\s*(.*)", block_text)
            details['tone_and_style_notes'] = get_field_value(r"^(?:Tone and Style Notes|Tone & Style|Tone|Style Notes):\s*(.*)", block_text)
            details['suspense_or_hook'] = get_field_value(r"^(?:Suspense or Hook|Suspense/Hook|Hook|Cliffhanger):\s*(.*)", block_text)

            chapters_details.append(details)
            parsed_chapters_count += 1

        if not chapters_details and llm_response.strip(): # Fallback if BEGIN/END structure failed entirely
            print(f"PlotArchitectAgent: Error - No chapter blocks parsed with BEGIN/END markers. Treating response as single raw block for chapter 1. Response: {llm_response[:500]}")
            chapters_details.append(PlotChapterDetail(
                chapter_number=1, title="Chapter 1 (Global Parsing Error)", raw_llm_output_for_chapter=llm_response.strip(),
                estimated_words=None, core_scene_summary=None, characters_present=None, key_events_and_plot_progression=None,
                goal_and_conflict=None, turning_point=None, tone_and_style_notes=None, suspense_or_hook=None
            ))
        elif len(chapters_details) < num_chapters:
            print(f"PlotArchitectAgent: Warning - Expected {num_chapters} chapters, but only parsed {len(chapters_details)} structured blocks.")

        if chapters_details:
             print(f"PlotArchitectAgent: Successfully parsed {len(chapters_details)} chapter structures.")
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

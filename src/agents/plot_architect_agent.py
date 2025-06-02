import re
from typing import List, Optional
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
        # Iteratively create the structure for each chapter to be included in the prompt
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

        all_chapter_structures_string = "\n\n".join(chapter_prompts_text) # Ensure a blank line between chapter structures

        prompt = f"""You are a meticulous Plot Architect, tasked with creating a detailed plot structure for a novel.
Based on the provided Narrative Outline and Worldview Data, generate detailed information for EXACTLY {num_chapters} chapters.

For EACH chapter, you MUST provide the following fields, using the exact headings as shown, each on a new line.
Follow the structure provided below for each chapter:

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
        chapters_details: List[PlotChapterDetail] = []

        # Primary parsing strategy:
        # 1. Split the entire LLM response into major blocks, one for each chapter,
        #    using "BEGIN CHAPTER X:" and "END CHAPTER X:" as delimiters.
        #    The regex captures the chapter number (group 1) and the content within (group 2).
        # 2. For each chapter block, attempt to parse individual fields (Title, Estimated Words, etc.)
        #    using regex tailored for each field, looking for "FieldName: value" patterns.
        #    These field regexes use a lookahead `(?=\n\s*\w+:|$)` to ensure they capture content
        #    up to the next field label or the end of the block, to handle multi-line values.
        # 3. Store the raw text of each chapter's block in 'raw_llm_output_for_chapter' for debugging.
        # 4. Implement fallbacks if primary parsing (e.g., BEGIN/END blocks) fails.

        # Attempt to find blocks for each chapter based on "BEGIN CHAPTER X:" and "END CHAPTER X:"
        # (?i) for case-insensitivity, re.DOTALL so '.' matches newlines.
        chapter_block_regex = r"(?i)BEGIN CHAPTER\s*(\d+):\s*(.*?)\s*END CHAPTER\s*\1:"

        matches = re.finditer(chapter_block_regex, llm_response, re.DOTALL)

        parsed_chapters_count = 0
        for match in matches:
            if parsed_chapters_count >= num_chapters:
                print(f"PlotArchitectAgent: Warning - Parsed requested {num_chapters} chapters, but more BEGIN/END blocks found in LLM response. Ignoring extras.")
                break

            chapter_num_from_block = int(match.group(1).strip())
            block_text = match.group(2).strip() # This is the content between BEGIN CHAPTER X: and END CHAPTER X:

            details = PlotChapterDetail(
                chapter_number=chapter_num_from_block,
                title=f"Chapter {chapter_num_from_block} (Title TBD)",
                estimated_words=None, core_scene_summary=None, characters_present=None,
                key_events_and_plot_progression=None, goal_and_conflict=None, turning_point=None,
                tone_and_style_notes=None, suspense_or_hook=None,
                raw_llm_output_for_chapter=block_text
            )

            # Regex for field extraction: "FieldName:\s*(.*?)(?=\n\s*\w+:|$)"
            # This means: FieldName, optional whitespace, capture content (.*?),
            # then lookahead for a newline followed by (optional whitespace, word, colon) OR end of string.
            # This helps capture multi-line content for a field.
            title_match = re.search(r"Title:\s*(.*?)(?=\n\s*\w+:|$)", block_text, re.IGNORECASE | re.DOTALL)
            if title_match: details['title'] = title_match.group(1).strip()

            words_match = re.search(r"Estimated Words:\s*(\d+)", block_text, re.IGNORECASE) # Specific to digits
            if words_match:
                try:
                    details['estimated_words'] = int(words_match.group(1).strip())
                except ValueError:
                    print(f"PlotArchitectAgent: Warning - Could not parse Estimated Words for Ch {chapter_num_from_block} as integer: {words_match.group(1)}")

            css_match = re.search(r"Core Scene Summary:\s*(.*?)(?=\n\s*\w+:|$)", block_text, re.IGNORECASE | re.DOTALL)
            if css_match: details['core_scene_summary'] = css_match.group(1).strip()

            cp_match = re.search(r"Characters Present:\s*(.*?)(?=\n\s*\w+:|$)", block_text, re.IGNORECASE | re.DOTALL)
            if cp_match:
                raw_chars = cp_match.group(1).strip()
                if raw_chars.lower() == "none":
                    details['characters_present'] = []
                else:
                    details['characters_present'] = [cp.strip() for cp in raw_chars.split(',') if cp.strip()]

            kep_match = re.search(r"Key Events and Plot Progression:\s*(.*?)(?=\n\s*\w+:|$)", block_text, re.IGNORECASE | re.DOTALL)
            if kep_match: details['key_events_and_plot_progression'] = kep_match.group(1).strip()

            gc_match = re.search(r"Goal and Conflict:\s*(.*?)(?=\n\s*\w+:|$)", block_text, re.IGNORECASE | re.DOTALL)
            if gc_match: details['goal_and_conflict'] = gc_match.group(1).strip()

            tp_match = re.search(r"Turning Point:\s*(.*?)(?=\n\s*\w+:|$)", block_text, re.IGNORECASE | re.DOTALL)
            if tp_match: details['turning_point'] = tp_match.group(1).strip()

            tsn_match = re.search(r"Tone and Style Notes:\s*(.*?)(?=\n\s*\w+:|$)", block_text, re.IGNORECASE | re.DOTALL)
            if tsn_match: details['tone_and_style_notes'] = tsn_match.group(1).strip()

            # Suspense or Hook is often the last field, so its regex can be a bit more greedy towards the end of the block.
            sh_match = re.search(r"Suspense or Hook:\s*(.*)", block_text, re.IGNORECASE | re.DOTALL)
            if sh_match: details['suspense_or_hook'] = sh_match.group(1).strip()

            chapters_details.append(details)
            parsed_chapters_count += 1

        if not chapters_details:
            print(f"PlotArchitectAgent: Error - No detailed chapter plots could be parsed using BEGIN/END CHAPTER markers. Review LLM output. Response (first 500 chars):\n{llm_response[:500]}...")
            if llm_response.strip():
                print("PlotArchitectAgent: Warning - Treating entire response as raw output for a single chapter due to parsing failure.")
                details = PlotChapterDetail(
                    chapter_number=1, title="Chapter 1 (Global Parsing Error)",
                    estimated_words=None, core_scene_summary=None, characters_present=None,
                    key_events_and_plot_progression=None, goal_and_conflict=None, turning_point=None,
                    tone_and_style_notes=None, suspense_or_hook=None,
                    raw_llm_output_for_chapter=llm_response.strip()
                )
                chapters_details.append(details)
        elif len(chapters_details) < num_chapters:
            print(f"PlotArchitectAgent: Warning - Expected {num_chapters} chapters, but only parsed {len(chapters_details)}.")
        else:
            print(f"PlotArchitectAgent: Successfully parsed details for {len(chapters_details)} chapters.")

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
        total_max_tokens = (estimated_tokens_per_detailed_chapter * num_chapters) + 600 # Buffer for prompt and formatting

        try:
            llm_response_text = self.llm_client.generate_text(
                prompt=prompt, model_name="gpt-3.5-turbo", max_tokens=total_max_tokens
            )
            print("PlotArchitectAgent: Received detailed chapter structures text from LLM.")
            parsed_chapter_details = self._parse_llm_response_to_list(llm_response_text, num_chapters)
            if not parsed_chapter_details:
                 print(f"PlotArchitectAgent: No detailed chapter structures were parsed. LLM response might have been empty or unparsable. Snippet: {llm_response_text[:300]}")
                 return []
            print(f"PlotArchitectAgent: Parsed {len(parsed_chapter_details)} detailed chapter structures.")
            return parsed_chapter_details
        except Exception as e:
            print(f"PlotArchitectAgent: Error during LLM call or parsing - {e}")
            raise

if __name__ == "__main__":
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key or api_key == "your_openai_api_key_here" or "dummykey" in api_key.lower() :
        print("----------------------------------------------------------------------")
        print("WARNING: Valid OPENAI_API_KEY not found or is a placeholder/dummy.")
        print("This test script for PlotArchitectAgent requires a real API key")
        print("to interact with the LLM and test prompt/parsing effectiveness.")
        print("Please set it in your .env file.")
        print("----------------------------------------------------------------------")

    print("--- Testing PlotArchitectAgent (Live LLM Call for Detailed Chapter Structures) ---")

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

    print(f"Target Chapters: {num_chapters_to_generate}")
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
        print("--- Generated Prompt for LLM ---")
        print(prompt_for_llm)
        print("---------------------------------\n")

        configured_max_tokens = (1200 * num_chapters_to_generate) + 600 # Matching agent's calculation
        print(f"Agent is configured to use max_tokens={configured_max_tokens} for the actual call in generate_plot_points.")

        if not agent.llm_client.api_key or "dummykey" in agent.llm_client.api_key.lower() or agent.llm_client.api_key == "your_openai_api_key_here":
             print("SKIPPING live LLM call in test due to dummy or placeholder API key.")
        else:
            raw_llm_response = agent.llm_client.generate_text(
                prompt=prompt_for_llm,
                max_tokens=configured_max_tokens
            )
            print("--- Raw LLM Response ---")
            print(raw_llm_response)
            print("------------------------\n")

            print("--- Parsing LLM Response (using agent's _parse_llm_response_to_list) ---")
            parsed_plot_details = agent._parse_llm_response_to_list(raw_llm_response, num_chapters_to_generate)

            print("\n--- Parsed PlotChapterDetail Objects ---")
            if parsed_plot_details:
                print(json.dumps(parsed_plot_details, indent=2))
            else:
                print("No plot details were parsed from the raw response.")

    except openai.APIError as e:
        print(f"\n!!! OpenAI API Error: {e} !!!")
        print("This usually means an issue with your API key, organization, or network.")
    except ValueError as ve:
        print(f"\n!!! Configuration Error: {ve} !!!")
    except Exception as e:
        print(f"\n!!! An unexpected error occurred: {e} !!!")
        traceback.print_exc()

    print("\n--- PlotArchitectAgent Test Finished ---")

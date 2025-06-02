import re
from typing import List, Optional # Added Optional for PlotChapterDetail
from src.llm_abstraction.llm_client import LLMClient
from src.core.models import PlotChapterDetail # Import the new TypedDict
import os

class PlotArchitectAgent:
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
        # This prompt requests a detailed structure for each chapter.
        chapter_structure_template = """
Chapter {chapter_num}:
  Title: [Chapter Title]
  Estimated Words: [Number, e.g., 1000]
  Core Scene Summary: [1-2 sentences describing the main scene(s)]
  Characters Present: [Comma-separated list of character names]
  Key Events and Plot Progression: [Bulleted or paragraph describing key events and how the plot advances]
  Goal and Conflict: [Main goal for protagonists in this chapter and the primary conflict they face]
  Turning Point: [Specific turning point, if any]
  Tone and Style Notes: [Brief notes, e.g., "fast-paced, action", "introspective, somber"]
  Suspense or Hook: [Any cliffhanger or hook for the next chapter]
"""
        all_chapter_prompts = "\n".join([chapter_structure_template.format(chapter_num=i+1) for i in range(num_chapters)])

        prompt = f"""You are a master storyteller and detailed plot architect.
Your task is to generate EXACTLY {num_chapters} detailed plot structures, one for each chapter of a short novel.
YOU MUST FOLLOW THIS FORMAT STRICTLY FOR EACH CHAPTER. EACH CHAPTER'S DETAILS MUST START ON A NEW LINE EXACTLY AS "Chapter X:" followed by its fields.

{all_chapter_prompts}

Do not include any other text before the first "Chapter 1:" or after the final chapter's details.
Each chapter's detailed structure should be self-contained.

Base these chapter structures on the following narrative outline and worldview:

Narrative Outline:
---
{narrative_outline}
---

Worldview Data:
---
{worldview_data}
---

Generate the {num_chapters} detailed chapter structures now:
"""
        return prompt

    def _parse_llm_response_to_list(self, llm_response: str, num_chapters: int) -> List[PlotChapterDetail]:
        chapters_details: List[PlotChapterDetail] = []

        # Split the entire response by "Chapter X:" to get blocks for each chapter.
        # This regex looks for "Chapter ", optional whitespace, digits, optional whitespace, and a colon.
        # The (?=...) is a positive lookahead to ensure we split correctly.
        chapter_blocks = re.split(r"Chapter\s*\d+\s*:", llm_response, flags=re.IGNORECASE)

        # The first element of chapter_blocks might be empty if the response starts with "Chapter 1:", so filter it.
        actual_chapter_content_blocks = [block.strip() for block in chapter_blocks if block.strip()]

        if not actual_chapter_content_blocks:
            print(f"PlotArchitectAgent: Error - Could not split LLM response into chapter blocks. Response: {llm_response[:500]}")
            if llm_response.strip(): # If there was content but no blocks, treat as one raw block for one chapter
                 print("PlotArchitectAgent: Warning - Treating entire response as raw output for a single chapter.")
                 details = PlotChapterDetail(
                    chapter_number=1,
                    title=f"Chapter 1 (Parsing Error)",
                    estimated_words=None, core_scene_summary=None, characters_present=None,
                    key_events_and_plot_progression=None, goal_and_conflict=None, turning_point=None,
                    tone_and_style_notes=None, suspense_or_hook=None,
                    raw_llm_output_for_chapter=llm_response.strip()
                 )
                 chapters_details.append(details)
            return chapters_details

        for i, block_text in enumerate(actual_chapter_content_blocks):
            chapter_num_from_block = i + 1 # Assume order or try to parse from block if available

            # Try to find a "Chapter X:" heading at the start of the original block to confirm chapter number
            # This requires looking at the raw splits before stripping, or a more complex regex for blocks.
            # For simplicity now, we'll use loop index 'i' + 1.

            details = PlotChapterDetail(
                chapter_number=chapter_num_from_block,
                title=f"Chapter {chapter_num_from_block} (Title TBD)", # Default
                estimated_words=None, core_scene_summary=None, characters_present=None,
                key_events_and_plot_progression=None, goal_and_conflict=None, turning_point=None,
                tone_and_style_notes=None, suspense_or_hook=None,
                raw_llm_output_for_chapter=block_text
            )

            title_match = re.search(r"Title:\s*(.*)", block_text, re.IGNORECASE)
            if title_match: details['title'] = title_match.group(1).strip()

            words_match = re.search(r"Estimated Words:\s*(\d+)", block_text, re.IGNORECASE)
            if words_match:
                try:
                    details['estimated_words'] = int(words_match.group(1).strip())
                except ValueError:
                    print(f"PlotArchitectAgent: Warning - Could not parse Estimated Words for Ch {chapter_num_from_block} as integer: {words_match.group(1)}")

            css_match = re.search(r"Core Scene Summary:\s*(.*)", block_text, re.IGNORECASE)
            if css_match: details['core_scene_summary'] = css_match.group(1).strip()

            cp_match = re.search(r"Characters Present:\s*(.*)", block_text, re.IGNORECASE)
            if cp_match:
                details['characters_present'] = [cp.strip() for cp in cp_match.group(1).split(',') if cp.strip()]

            kep_match = re.search(r"Key Events and Plot Progression:\s*(.*)", block_text, re.IGNORECASE)
            if kep_match: details['key_events_and_plot_progression'] = kep_match.group(1).strip()

            gc_match = re.search(r"Goal and Conflict:\s*(.*)", block_text, re.IGNORECASE)
            if gc_match: details['goal_and_conflict'] = gc_match.group(1).strip()

            tp_match = re.search(r"Turning Point:\s*(.*)", block_text, re.IGNORECASE)
            if tp_match: details['turning_point'] = tp_match.group(1).strip()

            tsn_match = re.search(r"Tone and Style Notes:\s*(.*)", block_text, re.IGNORECASE)
            if tsn_match: details['tone_and_style_notes'] = tsn_match.group(1).strip()

            sh_match = re.search(r"Suspense or Hook:\s*(.*)", block_text, re.IGNORECASE)
            if sh_match: details['suspense_or_hook'] = sh_match.group(1).strip()

            chapters_details.append(details)

            # Cap at num_chapters if LLM provides more for some reason
            if len(chapters_details) == num_chapters:
                break

        if not chapters_details:
            print(f"PlotArchitectAgent: Error - No detailed chapter plots could be parsed. Review LLM output. Response (first 500 chars):\n{llm_response[:500]}...")
        else:
            print(f"PlotArchitectAgent: Successfully parsed details for {len(chapters_details)} chapters.")
            if len(chapters_details) < num_chapters:
                 print(f"PlotArchitectAgent: Warning - Expected {num_chapters} chapters, but only parsed {len(chapters_details)}.")


        return chapters_details

    def generate_plot_points(self, narrative_outline: str, worldview_data: str, num_chapters: int = 3) -> List[PlotChapterDetail]:
        """
        Generates a list of detailed plot structures for each chapter.
        """
        if not narrative_outline:
            raise ValueError("Narrative outline cannot be empty.")
        if not worldview_data:
            raise ValueError("Worldview data cannot be empty.")
        if num_chapters <= 0:
            raise ValueError("Number of chapters must be positive.")

        prompt = self._construct_prompt(narrative_outline, worldview_data, num_chapters)

        print(f"PlotArchitectAgent: Sending prompt for {num_chapters} detailed chapter structures to LLM.")

        # Estimate tokens: Each field might be 50-100 words. 8 fields = 400-800 words.
        # 800 words * 1.33 tokens/word = ~1064 tokens per chapter.
        # For 3 chapters: ~3200 tokens. Add prompt and buffer.
        estimated_tokens_per_detailed_chapter = 1100
        total_max_tokens = (estimated_tokens_per_detailed_chapter * num_chapters) + 500 # Buffer for prompt and formatting

        try:
            llm_response_text = self.llm_client.generate_text(
                prompt=prompt,
                model_name="gpt-3.5-turbo",
                max_tokens=total_max_tokens
            )
            print("PlotArchitectAgent: Received detailed chapter structures text from LLM.")

            parsed_chapter_details = self._parse_llm_response_to_list(llm_response_text, num_chapters)

            if not parsed_chapter_details:
                 print(f"PlotArchitectAgent: No detailed chapter structures were parsed. LLM response might have been empty or unparsable. Snippet: {llm_response_text[:300]}")
                 # Potentially return a list with one item containing the raw response for debugging if needed
                 return []

            print(f"PlotArchitectAgent: Parsed {len(parsed_chapter_details)} detailed chapter structures.")
            return parsed_chapter_details

        except Exception as e:
            print(f"PlotArchitectAgent: Error during LLM call or parsing - {e}")
            raise

if __name__ == "__main__":
    print("--- Testing PlotArchitectAgent (Detailed Chapter Structures Generation) ---")

    from dotenv import load_dotenv
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY") or "dummy" in os.getenv("OPENAI_API_KEY", "").lower():
        print("WARNING: A valid OpenAI API key is required for this test to properly interact with the LLM.")
        if "dummy" in os.getenv("OPENAI_API_KEY","").lower() : # More generic dummy check
             print("ERROR: Test cannot reliably proceed with a known dummy key pattern. Please set a real API key for live testing.")
             exit(1)

    sample_outline = "A detective in a futuristic city, haunted by his past, takes on a case involving a mysterious new street drug that causes vivid, shared hallucinations. He must navigate the city's corrupt underbelly and his own demons to find the source."
    sample_worldview = "The city is Neo-Veridia, a sprawling megalopolis in 2242, characterized by towering skyscrapers, constant rain, and extreme social stratification. Advanced bio-enhancements are common, but heavily regulated. The mood is noirish and cynical, with an undercurrent of digital surrealism due to pervasive AR."
    num_chapters_to_generate = 2 # Test with 2 chapters for brevity

    try:
        agent = PlotArchitectAgent()
        print("PlotArchitectAgent initialized.")

        print(f"Generating {num_chapters_to_generate} detailed chapter structures for sample outline and worldview...")
        chapter_details_list = agent.generate_plot_points(
            narrative_outline=sample_outline,
            worldview_data=sample_worldview,
            num_chapters=num_chapters_to_generate
        )

        print(f"\nGenerated {len(chapter_details_list)} Detailed Chapter Structures:")
        if chapter_details_list:
            for i, details in enumerate(chapter_details_list):
                print(f"\n--- Chapter {details.get('chapter_number', i+1)} Details ---")
                print(f"  Title: {details.get('title')}")
                print(f"  Estimated Words: {details.get('estimated_words')}")
                print(f"  Core Scene Summary: {details.get('core_scene_summary')}")
                print(f"  Characters Present: {details.get('characters_present')}")
                print(f"  Key Events: {details.get('key_events_and_plot_progression')}")
                print(f"  Goal & Conflict: {details.get('goal_and_conflict')}")
                print(f"  Turning Point: {details.get('turning_point')}")
                print(f"  Tone/Style Notes: {details.get('tone_and_style_notes')}")
                print(f"  Suspense/Hook: {details.get('suspense_or_hook')}")
                # print(f"  Raw LLM Output: {details.get('raw_llm_output_for_chapter')}") # Potentially very verbose
        else:
            print("No detailed chapter structures were generated or parsed.")
            if os.getenv("OPENAI_API_KEY") and "dummy" in os.getenv("OPENAI_API_KEY","").lower():
                 print("This might be due to using a dummy API key.")

    except ValueError as ve:
        print(f"Configuration or Input Error: {ve}")
    except Exception as e:
        print(f"An error occurred during agent testing: {e}")
        print("Ensure your OPENAI_API_KEY is correctly set in your environment or .env file.")

    print("\n--- PlotArchitectAgent Test Finished ---")

import re
from typing import List
from src.llm_abstraction.llm_client import LLMClient
import os # For API key check in test block

class PlotArchitectAgent:
    def __init__(self):
        try:
            self.llm_client = LLMClient()
        except ValueError as e: # This is raised by LLMClient if API key is missing
            print(f"PlotArchitectAgent Error: LLMClient initialization failed. {e}")
            print("Please ensure OPENAI_API_KEY is set in your environment or .env file.")
            raise # Re-raise to prevent agent usage without a functional LLMClient
        except Exception as e:
            print(f"PlotArchitectAgent Error: An unexpected error occurred during LLMClient initialization: {e}")
            raise

    def _construct_prompt(self, narrative_outline: str, worldview_data: str, num_chapters: int = 3) -> str:
        prompt = f"""You are a master storyteller and plot architect.
        Your task is to generate EXACTLY {num_chapters} plot summaries, one for each chapter of a short novel.
        YOU MUST FOLLOW THIS FORMAT STRICTLY FOR EACH CHAPTER SUMMARY. EACH SUMMARY MUST START ON A NEW LINE EXACTLY AS SHOWN:

        Chapter 1 Summary:
        [Detailed summary for chapter 1, focusing on key events, character actions, and plot progression for this specific chapter. Aim for 1-2 paragraphs.]

        Chapter 2 Summary:
        [Detailed summary for chapter 2, similar focus and length.]

        Chapter {num_chapters} Summary:
        [Detailed summary for chapter {num_chapters}, similar focus and length.]

        Do not include any other text, numbering, or explanations before the first "Chapter 1 Summary:" or after the final summary for Chapter {num_chapters}.
        Each summary should be self-contained for that chapter.

        Base these summaries on the following narrative outline and worldview:

        Narrative Outline:
        ---
        {narrative_outline}
        ---

        Worldview Data:
        ---
        {worldview_data}
        ---

        Generate {num_chapters} chapter summaries now:
        """
        return prompt

    def _parse_llm_response_to_list(self, llm_response: str) -> List[str]:
        """Parses a string of chapter summaries into a list of strings."""
        if not llm_response:
            return []

        summaries = []
        # Main regex: Captures text after "Chapter X Summary:" until the next "Chapter X Summary:" or end of string.
        # It's case-insensitive for "Chapter X Summary:".
        matches = re.finditer(r"Chapter\s*\d+\s*Summary:\s*(.*?)(?=(Chapter\s*\d+\s*Summary:|$))", llm_response, re.DOTALL | re.IGNORECASE)
        for match in matches:
            summary_text = match.group(1).strip()
            if summary_text:
                summaries.append(summary_text)

        # Fallback 1: If no matches with the primary regex, try splitting by the delimiter.
        # This might be useful if the LLM uses the delimiter but the overall structure isn't perfectly captured by regex.
        if not summaries and llm_response.strip():
            print("PlotArchitectAgent: Primary regex parsing failed. Attempting fallback split by 'Chapter X Summary:'.")
            potential_summaries = re.split(r"Chapter\s*\d+\s*Summary:", llm_response, flags=re.IGNORECASE)
            for potential_summary in potential_summaries:
                cleaned_summary = potential_summary.strip()
                if cleaned_summary: # Add if not empty
                    summaries.append(cleaned_summary)
            # Remove empty first element if the split produced it because the string started with the delimiter.
            if summaries and not summaries[0] and len(potential_summaries) > 1:
                summaries.pop(0)

        # Fallback 2: If still no summaries, and there's content, treat lines as potential summaries.
        # This is a last resort and assumes content might be present without clear delimiters.
        if not summaries and llm_response.strip():
            print("PlotArchitectAgent: Fallback split also failed. Attempting to treat distinct blocks of text as summaries.")
            # Split by two or more newlines, then filter out any empty strings
            potential_summaries = [s.strip() for s in re.split(r'\n\n+', llm_response.strip()) if s.strip()]
            if potential_summaries:
                summaries = potential_summaries

        if not summaries:
             print(f"PlotArchitectAgent: Error - No plot summaries could be parsed even with fallbacks. Review LLM output. Response (first 500 chars):\n{llm_response[:500]}...")
        else:
             print(f"PlotArchitectAgent: Successfully parsed {len(summaries)} plot summaries.")

        return summaries


    def generate_plot_points(self, narrative_outline: str, worldview_data: str, num_chapters: int = 3) -> List[str]:
        """
        Generates a list of chapter-by-chapter plot summaries.
        """
        if not narrative_outline:
            raise ValueError("Narrative outline cannot be empty.")
        if not worldview_data:
            raise ValueError("Worldview data cannot be empty.")
        if num_chapters <= 0:
            raise ValueError("Number of chapters must be positive.")

        prompt = self._construct_prompt(narrative_outline, worldview_data, num_chapters)

        print(f"PlotArchitectAgent: Sending prompt for {num_chapters} chapter summaries to LLM.")
        # print(f"PlotArchitectAgent: Prompt content snippet:\n{prompt[:500]}...") # For debugging

        try:
            llm_response_text = self.llm_client.generate_text(
                prompt=prompt,
                model_name="gpt-3.5-turbo",
                max_tokens=1500  # Increased for multiple chapter summaries
            )
            print("PlotArchitectAgent: Received chapter summaries text from LLM.")

            parsed_chapter_summaries = self._parse_llm_response_to_list(llm_response_text)

            if not parsed_chapter_summaries and llm_response_text: # If parsing returns empty list but there was response
                print(f"PlotArchitectAgent: Warning - LLM responded but no chapter summaries were parsed by any method. LLM raw response (first 300 chars): {llm_response_text[:300]}...")
                # Decide if to return raw text as a single item or empty. For now, empty if unparsable.
                return []

            if not parsed_chapter_summaries: # If response was empty or parsing yielded nothing
                 print("PlotArchitectAgent: No chapter summaries were generated or parsed. LLM response might have been empty or unparsable.")
                 return []


            print(f"PlotArchitectAgent: Parsed {len(parsed_chapter_summaries)} chapter summaries.")
            return parsed_chapter_summaries

        except Exception as e:
            print(f"PlotArchitectAgent: Error during LLM call or parsing - {e}")
            raise

if __name__ == "__main__":
    print("--- Testing PlotArchitectAgent (Chapter Summaries Generation) ---")

    from dotenv import load_dotenv
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY") or "dummy" in os.getenv("OPENAI_API_KEY", "").lower():
        print("WARNING: A valid OpenAI API key is required for this test to properly interact with the LLM.")
        print("Attempting to run with potentially dummy/invalid key. LLM calls may fail.")

    sample_outline = "A young mage discovers an ancient artifact that grants immense power but also corrupts its wielder. She must learn to control it or be consumed, all while a shadowy organization hunts her for the artifact."
    sample_worldview = "The world of Aerthos is one where magic is common, governed by strict councils. Ancient ruins dot the landscape, hinting at forgotten eras of powerful, uncontrolled magic. The 'Obsidian Hand' is a clandestine group seeking to restore this chaotic magic."
    num_chapters_to_generate = 3

    try:
        agent = PlotArchitectAgent()
        print("PlotArchitectAgent initialized.")

        print(f"Generating {num_chapters_to_generate} chapter summaries for sample outline and worldview...")
        chapter_summaries = agent.generate_plot_points(
            narrative_outline=sample_outline,
            worldview_data=sample_worldview,
            num_chapters=num_chapters_to_generate
        )

        print(f"\nGenerated {len(chapter_summaries)} Chapter Summaries:")
        if chapter_summaries:
            for i, summary in enumerate(chapter_summaries):
                print(f"\nChapter {i+1} Summary:\n{summary}")
        else:
            print("No chapter summaries were generated or parsed.")
            if os.getenv("OPENAI_API_KEY") and "dummy" in os.getenv("OPENAI_API_KEY","").lower():
                 print("This might be due to using a dummy API key.")

    except ValueError as ve:
        print(f"Configuration or Input Error: {ve}")
    except Exception as e:
        print(f"An error occurred during agent testing: {e}")
        print("Ensure your OPENAI_API_KEY is correctly set in your environment or .env file.")

    print("\n--- PlotArchitectAgent Test Finished ---")

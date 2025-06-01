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
Based on the following narrative outline and worldview, generate a list of plot summaries, one for each of the {num_chapters} chapters of a short novel.
Each plot summary should be a concise paragraph outlining the key events, character actions, and plot progression for that specific chapter.
Please output these chapter summaries clearly delineated, using the exact format "Chapter X Summary:" for each, where X is the chapter number. For example:

Chapter 1 Summary:
[Detailed summary for chapter 1...]

Chapter 2 Summary:
[Detailed summary for chapter 2...]

Chapter {num_chapters} Summary:
[Detailed summary for chapter {num_chapters}...]

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
        # Using re.DOTALL is equivalent to (?s)
        # Ensure re is imported: import re
        matches = re.finditer(r"Chapter \d+ Summary:\s*(.*?)(?=(Chapter \d+ Summary:|$))", llm_response, re.DOTALL | re.IGNORECASE)
        for match in matches:
            summary_text = match.group(1).strip()
            if summary_text:
                summaries.append(summary_text)

        if not summaries and llm_response.strip():
            print(f"PlotArchitectAgent: Warning - Strict parsing of chapter summaries failed using main regex. LLM Raw Response (first 500 chars):\n{llm_response[:500]}...")
            # Basic fallback: try to split by "Chapter X Summary:" and clean up
            potential_summaries = re.split(r"Chapter \d+ Summary:", llm_response, flags=re.IGNORECASE)
            for potential_summary in potential_summaries:
                cleaned_summary = potential_summary.strip()
                if cleaned_summary:
                    summaries.append(cleaned_summary)

            if summaries and not summaries[0] and len(potential_summaries) > 1: # Remove empty first element if split produced it
                summaries.pop(0)

        if not summaries:
             print(f"PlotArchitectAgent: Error - No plot summaries could be parsed. Review LLM output if this persists.")

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

            if not parsed_chapter_summaries and llm_response_text:
                print(f"PlotArchitectAgent: Warning - LLM responded but no chapter summaries were parsed. LLM raw response: {llm_response_text[:300]}...")
                # Fallback behavior is now handled within _parse_llm_response_to_list
                # If it still returns empty, then it truly couldn't parse.
                return [llm_response_text.strip()] # Return raw as single item if all parsing fails

            if not parsed_chapter_summaries:
                 print("PlotArchitectAgent: No chapter summaries were generated or parsed. LLM response might have been empty.")
                 return []


            print(f"PlotArchitectAgent: Parsed {len(parsed_chapter_summaries)} chapter summaries.")
            return parsed_chapter_summaries

        except Exception as e:
            print(f"PlotArchitectAgent: Error during LLM call or parsing - {e}")
            # Re-raising to make it visible, could be handled more gracefully in a full app
            raise

if __name__ == "__main__":
    print("--- Testing PlotArchitectAgent (Chapter Summaries Generation) ---")
    # This test now requires a valid OPENAI_API_KEY to be set in the environment or a .env file.
    # If a dummy key is used, the LLMClient initialization or the API call will likely fail.

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
        # This will catch errors from LLMClient (e.g., API key issues) or other unexpected errors
        print(f"An error occurred during agent testing: {e}")
        print("Ensure your OPENAI_API_KEY is correctly set in your environment or .env file.")

    print("\n--- PlotArchitectAgent Test Finished ---")

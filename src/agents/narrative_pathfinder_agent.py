import re # Added for parsing
from typing import List # Added for type hinting
from src.llm_abstraction.llm_client import LLMClient
from src.utils.dynamic_token_config import get_dynamic_max_tokens, log_token_usage
import os # For API key check in test block

class NarrativePathfinderAgent:
    def __init__(self):
        try:
            self.llm_client = LLMClient()
        except ValueError as e:
            print(f"NarrativePathfinderAgent Error: LLMClient initialization failed. {e}")
            print("Please ensure OPENAI_API_KEY is set in your environment or .env file.")
            raise
        except Exception as e:
            print(f"NarrativePathfinderAgent Error: An unexpected error occurred during LLMClient initialization: {e}")
            raise

    def _construct_prompt(self, user_theme: str, style_preferences: str, num_outlines: int = 2) -> str:
        prompt = f"""You are a creative novel planner. Your task is to generate {num_outlines} distinct 'core creative overviews' for a new novel.
Each overview should be approximately 200-300 words and represent a unique angle or development of the theme.
Clearly separate each overview using the format "Overview X:" on its own line, where X is the overview number. For example:

Overview 1:
[Text for overview 1, touching upon Core Concept, Main Conflict Hint, Primary Character Type Idea, Story Highlights/Potential, Overall Tone/Style. Ensure this overview is a single, coherent block of text.]

Overview 2:
[Text for overview 2, with the same structure but different ideas. Ensure this overview is a single, coherent block of text.]

User Provided Theme: "{user_theme}"
Style Preferences: "{style_preferences}"

Please generate {num_outlines} distinct core creative overviews now:
"""
        return prompt

    def _parse_multiple_outlines(self, llm_response: str) -> List[str]:
        outlines = []
        # Regex to find "Overview X:" and capture the text until the next "Overview X:" or end of string.
        # re.DOTALL allows . to match newline characters.
        # re.IGNORECASE makes "Overview" case-insensitive if needed, though prompt specifies capitalization.
        matches = re.finditer(r"Overview \d+:\s*(.*?)(?=(Overview \d+:|$))", llm_response, re.DOTALL | re.IGNORECASE)
        for match in matches:
            overview_text = match.group(1).strip()
            if overview_text: # Ensure captured text is not just whitespace
                outlines.append(overview_text)

        # Fallback if the primary regex fails but there's content
        if not outlines and llm_response.strip():
            print("NarrativePathfinderAgent: Warning - Strict parsing of multiple overviews failed using main regex. Attempting fallback by splitting on 'Overview X:'.")
            # Split by "Overview X:" pattern. This will include an empty string at the beginning if response starts with delimiter.
            potential_outlines = re.split(r"Overview \d+:", llm_response, flags=re.IGNORECASE)
            for potential_outline in potential_outlines:
                cleaned_outline = potential_outline.strip()
                if cleaned_outline: # Add if not empty after stripping
                    outlines.append(cleaned_outline)

            if outlines and not outlines[0] and len(potential_outlines) > 1: # If the first element is empty and there was a split
                 outlines.pop(0) # Remove the empty first element that results from splitting on a leading delimiter

        if not outlines and llm_response.strip():
            print(f"NarrativePathfinderAgent: Warning - No distinct overviews could be parsed with delimiters. Returning the whole response as a single outline. LLM Raw Response (first 500 chars):\n{llm_response[:500]}...")
            outlines.append(llm_response.strip())

        if not outlines:
             print(f"NarrativePathfinderAgent: Error - No outlines could be parsed and LLM response was empty or only whitespace.")

        return outlines

    def generate_outline(self, user_theme: str, style_preferences: str = "general fiction", num_outlines: int = 2) -> List[str]:
        """
        Generates a list of narrative outlines (core creative overviews) based on user input.
        """
        if not user_theme:
            raise ValueError("User theme cannot be empty.")
        if num_outlines <= 0:
            raise ValueError("Number of outlines must be positive.")

        prompt = self._construct_prompt(user_theme, style_preferences, num_outlines)

        print(f"NarrativePathfinderAgent: Sending prompt for {num_outlines} outlines for theme '{user_theme}' to LLM.")

        try:
            # Calculate dynamic max_tokens based on content and requirements
            context = {
                "theme": user_theme,
                "style": style_preferences
            }
            max_tokens = get_dynamic_max_tokens("narrative_pathfinder", context)
            log_token_usage("narrative_pathfinder", max_tokens, context)

            llm_response_text = self.llm_client.generate_text(
                prompt=prompt,
                model_name="gpt-4o-2024-08-06",
                max_tokens=max_tokens
            )
            print("NarrativePathfinderAgent: Received outlines from LLM.")

            parsed_outlines = self._parse_multiple_outlines(llm_response_text)

            if not parsed_outlines:
                 print(f"NarrativePathfinderAgent: No outlines were parsed from LLM response. LLM raw response (first 300 chars): {llm_response_text[:300]}...")
                 # Return empty list or handle as error. For now, returning empty list.
                 return []

            print(f"NarrativePathfinderAgent: Parsed {len(parsed_outlines)} outlines.")
            return parsed_outlines
        except Exception as e:
            print(f"NarrativePathfinderAgent: Error during LLM call or parsing - {e}")
            raise

if __name__ == "__main__":
    print("--- Testing NarrativePathfinderAgent (Multiple Outlines) ---")
    # This test REQUIRES a valid OPENAI_API_KEY.
    from dotenv import load_dotenv
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY") or "dummy" in os.getenv("OPENAI_API_KEY", "").lower():
        print("WARNING: A valid OpenAI API key is required for this test to properly interact with the LLM.")
        print("Attempting to run with potentially dummy/invalid key. LLM calls WILL FAIL if key is not valid.")
        if "dummykey" in os.getenv("OPENAI_API_KEY",""):
             print("ERROR: Test cannot reliably proceed with a known dummy key pattern. Please set a real API key for live testing.")
             exit(1)

    try:
        agent = NarrativePathfinderAgent()
        print("NarrativePathfinderAgent initialized.")

        theme1 = "An interstellar historian discovers an artifact that shows visions of a cyclical galactic apocalypse."
        style1 = "epic sci-fi, philosophical, awe-inspiring"
        num_to_generate = 2
        print(f"\nGenerating {num_to_generate} outlines for theme: '{theme1}'")

        outlines = agent.generate_outline(user_theme=theme1, style_preferences=style1, num_outlines=num_to_generate)

        print(f"\nGenerated {len(outlines)} Outlines:")
        if outlines:
            for i, outline_text in enumerate(outlines):
                print(f"\n--- Outline {i+1} ---")
                print(outline_text)
        else:
            print("No outlines were generated or parsed.")
            if os.getenv("OPENAI_API_KEY") and "dummy" in os.getenv("OPENAI_API_KEY","").lower():
                 print("This might be due to using a dummy API key.")


    except ValueError as ve:
        print(f"Configuration or Input Error: {ve}")
    except Exception as e:
        print(f"An error occurred during agent testing: {e}")
        print("Ensure your OPENAI_API_KEY is correctly set in your environment or .env file.")

    print("\n--- NarrativePathfinderAgent Test Finished ---")

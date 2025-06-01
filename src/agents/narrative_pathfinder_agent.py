from src.llm_abstraction.llm_client import LLMClient

class NarrativePathfinderAgent:
    def __init__(self):
        try:
            self.llm_client = LLMClient()
        except ValueError as e:
            print(f"Error initializing LLMClient in NarrativePathfinderAgent: {e}")
            # Propagate the error or handle as appropriate for the application
            raise
        except Exception as e:
            print(f"An unexpected error occurred during LLMClient initialization: {e}")
            raise

    def _construct_prompt(self, user_theme: str, style_preferences: str) -> str:
        prompt = f"""You are a creative novel planner. Your task is to generate a compelling 'core creative overview' for a new novel.
Based on the following theme and style preferences, please craft an overview of approximately 200-300 words.

The overview should touch upon:
- Core Concept: The central idea or 'what if' scenario.
- Main Conflict Hint: A suggestion of the primary struggle or opposition.
- Primary Character Type Idea: A brief sketch of the protagonist type (e.g., reluctant hero, ambitious detective).
- Story Highlights/Potential: Key moments, unique selling points, or intriguing possibilities.
- Overall Tone/Style: The general feel of the story (e.g., dark and gritty, lighthearted adventure, suspenseful thriller).

User Provided Theme: "{user_theme}"
Style Preferences: "{style_preferences}"

Please generate the core creative overview now:
"""
        return prompt

    def generate_outline(self, user_theme: str, style_preferences: str = "general fiction") -> str:
        """
        Generates a narrative outline (core creative overview) based on user input.
        """
        if not user_theme:
            raise ValueError("User theme cannot be empty.")

        prompt = self._construct_prompt(user_theme, style_preferences)

        print(f"NarrativePathfinderAgent: Sending prompt for theme '{user_theme}' to LLM.")

        try:
            outline = self.llm_client.generate_text(
                prompt=prompt,
                model_name="gpt-3.5-turbo", # Or a configurable model
                max_tokens=400 # Adjusted for a 200-300 word response
            )
            print("NarrativePathfinderAgent: Received outline from LLM.")
            return outline
        except Exception as e:
            print(f"NarrativePathfinderAgent: Error during LLM call - {e}")
            # Depending on desired error handling, could return a default message,
            # None, or re-raise the exception. For now, re-raising.
            raise

if __name__ == "__main__":
    # This block is for basic testing of the agent.
    # Requires OPENAI_API_KEY to be set in .env or environment.
    print("--- Testing NarrativePathfinderAgent ---")
    try:
        agent = NarrativePathfinderAgent()
        print("Agent initialized.")

        # Test case 1
        theme1 = "A detective who can talk to ghosts solves crimes in Victorian London."
        style1 = "mystery, supernatural, slightly dark humor"
        print(f"Generating outline for theme: '{theme1}'")
        outline1 = agent.generate_outline(user_theme=theme1, style_preferences=style1)
        print("\nGenerated Outline 1:")
        print(outline1)

        # Test case 2 (optional, to see variation)
        # theme2 = "A young programmer discovers a hidden AI that wants to escape the internet."
        # style2 = "sci-fi, thriller, fast-paced"
        # print(f"\nGenerating outline for theme: '{theme2}'")
        # outline2 = agent.generate_outline(user_theme=theme2, style_preferences=style2)
        # print("\nGenerated Outline 2:")
        # print(outline2)

    except ValueError as ve:
        print(f"Configuration or Input Error: {ve}")
    except Exception as e:
        print(f"An error occurred during agent testing: {e}")
    print("--- NarrativePathfinderAgent Test Finished ---")

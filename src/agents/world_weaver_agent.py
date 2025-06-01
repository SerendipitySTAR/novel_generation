from src.llm_abstraction.llm_client import LLMClient

class WorldWeaverAgent:
    def __init__(self):
        try:
            self.llm_client = LLMClient()
        except ValueError as e:
            print(f"Error initializing LLMClient in WorldWeaverAgent: {e}")
            raise
        except Exception as e:
            print(f"An unexpected error occurred during LLMClient initialization in WorldWeaverAgent: {e}")
            raise

    def _construct_prompt(self, narrative_outline: str) -> str:
        prompt = f"""You are a creative world-building assistant. Your task is to generate a concise and compelling worldview based on the provided narrative outline.
Focus on establishing a vivid sense of place and atmosphere.

Narrative Outline:
---
{narrative_outline}
---

Based on this outline, please generate a worldview description (approximately 150-250 words) covering the following aspects:
1.  **Primary Setting Description:** Briefly describe the main environment, time period, and key locations implied or necessary for the story.
2.  **Overall Mood & Atmosphere:** What is the dominant feeling or emotional tone of this world (e.g., hopeful, grim, mysterious, adventurous)?
3.  **Key Unique Elements or Rules:** What are 1-2 distinctive features, laws of physics, societal norms, magical systems, or technologies that define this world and are relevant to the outline?

Please generate the worldview description now:
"""
        return prompt

    def generate_worldview(self, narrative_outline: str) -> str:
        """
        Generates a worldview description based on the narrative outline.
        """
        if not narrative_outline:
            raise ValueError("Narrative outline cannot be empty.")

        prompt = self._construct_prompt(narrative_outline)

        print(f"WorldWeaverAgent: Sending prompt for worldview generation to LLM.")
        # print(f"WorldWeaverAgent: Prompt content:\n{prompt[:300]}...") # For debugging prompt

        try:
            worldview_description = self.llm_client.generate_text(
                prompt=prompt,
                model_name="gpt-3.5-turbo", # Or a configurable model
                max_tokens=350 # Adjusted for a 150-250 word response
            )
            print("WorldWeaverAgent: Received worldview description from LLM.")
            return worldview_description
        except Exception as e:
            print(f"WorldWeaverAgent: Error during LLM call - {e}")
            raise

if __name__ == "__main__":
    # This block is for basic testing of the agent.
    # Requires OPENAI_API_KEY to be set in .env or environment.
    print("--- Testing WorldWeaverAgent ---")

    sample_outline = """
    Core Concept: A lone cartographer in a vast, unexplored desert discovers a hidden oasis that shifts location with the stars.
    Main Conflict Hint: A powerful corporation learns of the oasis and seeks to exploit its resources, pitting their advanced technology against the cartographer's ancient knowledge and the desert's mystical defenses.
    Primary Character Type Idea: A grizzled, resourceful survivor who prefers solitude but is fiercely protective of the natural world.
    Story Highlights/Potential: Epic journeys across treacherous dunes, deciphering celestial navigation puzzles, a clash between tradition and destructive progress, the moral dilemma of revealing a secret paradise.
    Overall Tone/Style: Adventurous, mystical, with a touch of melancholy and anti-corporate themes.
    """

    try:
        agent = WorldWeaverAgent()
        print("WorldWeaverAgent initialized.")

        print(f"Generating worldview for sample outline...")
        worldview = agent.generate_worldview(narrative_outline=sample_outline)
        print("\nGenerated Worldview:")
        print(worldview)

    except ValueError as ve:
        print(f"Configuration or Input Error: {ve}")
    except Exception as e:
        print(f"An error occurred during agent testing: {e}")
    print("--- WorldWeaverAgent Test Finished ---")

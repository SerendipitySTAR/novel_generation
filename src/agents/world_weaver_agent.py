import re
from typing import List, Optional
from src.llm_abstraction.llm_client import LLMClient
from src.core.models import WorldviewDetail # Import the new TypedDict
import os # For test block
from dotenv import load_dotenv # For test block
import openai # For test block
import json # For test block

class WorldWeaverAgent:
    """
    Generates multiple distinct worldview options based on a narrative outline.
    Each worldview is structured with fields like name, core concept, key elements, and atmosphere.
    """
    def __init__(self):
        try:
            self.llm_client = LLMClient()
        except ValueError as e:
            print(f"WorldWeaverAgent Error: LLMClient initialization failed. {e}")
            print("Please ensure OPENAI_API_KEY is set in your environment or .env file.")
            raise
        except Exception as e:
            print(f"WorldWeaverAgent Error: An unexpected error occurred during LLMClient initialization: {e}")
            raise

    def _construct_prompt(self, narrative_outline: str, num_worldviews: int = 2) -> str:
        # Prompt designed to elicit detailed structured information for each worldview.
        worldview_structure_template = """BEGIN WORLDVIEW {worldview_num}:
World Name: [A unique and evocative name for this world/setting]
Core Concept: [A 2-3 sentence description of the central concept, time period, and primary setting of this world. This is the main descriptive part.]
Key Elements: [List 2-3 comma-separated key defining elements, e.g., unique physical laws, specific magic systems, prevalent technologies, important societal norms]
Atmosphere: [1-2 words describing the dominant mood, e.g., Mystical, Grim, Adventurous, Technologically Advanced]
END WORLDVIEW {worldview_num}:"""

        all_worldview_prompts = "\n\n".join([worldview_structure_template.format(worldview_num=i+1) for i in range(num_worldviews)])

        prompt = f"""You are a creative world-building assistant. Based on the following narrative outline, generate {num_worldviews} distinct worldview options.

For EACH worldview option, you MUST provide the following fields, using the exact headings as shown, each on a new line.
Follow the structure provided below for each worldview:

{all_worldview_prompts}

Do not add any commentary or text outside of this structure for each worldview.
Ensure there is a blank line after "END WORLDVIEW X:" before the next "BEGIN WORLDVIEW X+1:" (if applicable for {num_worldviews} > 1).

Narrative Outline:
---
{narrative_outline}
---

Please generate {num_worldviews} distinct worldview options now, following the specified format strictly.
"""
        return prompt

    def _parse_multiple_worldviews(self, llm_response: str, num_worldviews: int) -> List[WorldviewDetail]:
        worldviews: List[WorldviewDetail] = []

        # Regex to capture each worldview block, including its BEGIN/END markers
        worldview_block_regex = r"(?i)BEGIN WORLDVIEW\s*(\d+):\s*(.*?)\s*END WORLDVIEW\s*\1:"

        matches = re.finditer(worldview_block_regex, llm_response, re.DOTALL)

        parsed_count = 0
        for match in matches:
            if parsed_count >= num_worldviews:
                print(f"WorldWeaverAgent: Warning - Parsed requested {num_worldviews} worldviews, but more BEGIN/END blocks found. Ignoring extras.")
                break

            # worldview_num_from_block = int(match.group(1).strip()) # Can be used for validation if needed
            block_text = match.group(2).strip()

            detail = WorldviewDetail(
                world_name=None,
                core_concept="Not parsed",
                key_elements=None,
                atmosphere=None,
                raw_llm_output_for_worldview=block_text
            )

            name_match = re.search(r"World Name:\s*(.*?)(?=\n\s*\w+:|$)", block_text, re.IGNORECASE | re.DOTALL)
            if name_match: detail['world_name'] = name_match.group(1).strip()

            concept_match = re.search(r"Core Concept:\s*(.*?)(?=\n\s*\w+:|$)", block_text, re.IGNORECASE | re.DOTALL)
            if concept_match: detail['core_concept'] = concept_match.group(1).strip()

            elements_match = re.search(r"Key Elements:\s*(.*?)(?=\n\s*\w+:|$)", block_text, re.IGNORECASE | re.DOTALL)
            if elements_match:
                raw_elements = elements_match.group(1).strip()
                if raw_elements.lower() != "none":
                    detail['key_elements'] = [e.strip() for e in raw_elements.split(',') if e.strip()]
                else:
                    detail['key_elements'] = []

            atmosphere_match = re.search(r"Atmosphere:\s*(.*)", block_text, re.IGNORECASE | re.DOTALL) # Often last
            if atmosphere_match: detail['atmosphere'] = atmosphere_match.group(1).strip()

            # Ensure core_concept is not the default if other fields were parsed, or if block_text itself is valid
            if detail['core_concept'] == "Not parsed" and block_text:
                if not name_match and not elements_match and not atmosphere_match: # If no fields parsed, assume block is core_concept
                     detail['core_concept'] = block_text
                elif not concept_match: # If other fields parsed but not core_concept specifically
                     print(f"WorldWeaverAgent: Warning - Core Concept not explicitly parsed for a worldview block. Raw block: {block_text[:100]}")


            worldviews.append(detail)
            parsed_count +=1

        if not worldviews:
            print(f"WorldWeaverAgent: Error - No worldviews could be parsed using BEGIN/END WORLDVIEW markers. LLM Response (first 500 chars):\n{llm_response[:500]}...")
            if llm_response.strip(): # Fallback: treat entire response as one worldview's core concept
                 print("WorldWeaverAgent: Warning - Treating entire response as raw output for a single worldview's core concept.")
                 worldviews.append(WorldviewDetail(
                    world_name="World (Parsing Error)", core_concept=llm_response.strip(), key_elements=None, atmosphere=None, raw_llm_output_for_worldview=llm_response.strip()
                 ))
        elif len(worldviews) < num_worldviews:
             print(f"WorldWeaverAgent: Warning - Expected {num_worldviews} worldviews, but only parsed {len(worldviews)}.")
        else:
            print(f"WorldWeaverAgent: Successfully parsed {len(worldviews)} worldviews.")

        return worldviews

    def generate_worldview(self, narrative_outline: str, num_worldviews: int = 2) -> List[WorldviewDetail]:
        """
        Generates a list of structured worldview descriptions.
        """
        if not narrative_outline:
            raise ValueError("Narrative outline cannot be empty.")
        if num_worldviews <= 0:
            raise ValueError("Number of worldviews must be positive.")

        prompt = self._construct_prompt(narrative_outline, num_worldviews)
        print(f"WorldWeaverAgent: Sending prompt for {num_worldviews} worldview options to LLM.")

        # Use large max_tokens for detailed worldview generation with reasoning models
        try:
            llm_response_text = self.llm_client.generate_text(
                prompt=prompt,
                model_name="gpt-4o-2024-08-06",
                max_tokens=32768
            )
            print("WorldWeaverAgent: Received worldview options text from LLM.")

            parsed_worldviews = self._parse_multiple_worldviews(llm_response_text, num_worldviews)

            if not parsed_worldviews:
                 print(f"WorldWeaverAgent: No worldviews were parsed from LLM response. Snippet: {llm_response_text[:300]}...")
                 return [] # Return empty list if nothing usable parsed

            print(f"WorldWeaverAgent: Parsed {len(parsed_worldviews)} worldview(s).")
            return parsed_worldviews
        except Exception as e:
            print(f"WorldWeaverAgent: Error during LLM call or parsing - {e}")
            raise

if __name__ == "__main__":
    print("--- Testing WorldWeaverAgent (Multiple Structured Worldviews) ---")
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or "dummy" in api_key.lower() or api_key == "your_openai_api_key_here":
        print("WARNING: A valid OpenAI API key is required for this test to properly interact with the LLM.")
        print("Attempting to run with potentially dummy/invalid key. LLM calls WILL FAIL if key is not valid.")
        if "dummy" in api_key.lower(): # More generic dummy check for critical tests
             print("ERROR: Test cannot reliably proceed with a known dummy key pattern. Please set a real API key for live testing.")
             exit(1)

    sample_outline = """
    Core Concept: A city where emotions manifest as tangible, weather-like phenomena. Joy can bring sunshine, while collective fear can summon storms.
    Main Conflict Hint: A rogue 'Emotion Weaver' is attempting to seize control of the city by manipulating mass emotions, threatening to plunge it into an endless emotional tempest.
    Primary Character Type Idea: A young 'Emotion Sensitive' who can predict and slightly influence these emotional weather patterns, and is perhaps the only one who can stop the Weaver.
    Story Highlights/Potential: Visually stunning displays of emotion-weather, intricate social dynamics based on emotional control/expression, a philosophical exploration of feelings.
    Overall Tone/Style: Magical realism, whimsical yet with underlying tension, visually descriptive.
    """
    num_to_generate = 2

    try:
        agent = WorldWeaverAgent()
        print("WorldWeaverAgent initialized.")

        print(f"Generating {num_to_generate} worldview options for sample outline...")
        worldviews = agent.generate_worldview(narrative_outline=sample_outline, num_worldviews=num_to_generate)

        print(f"\nGenerated {len(worldviews)} Worldview Options:")
        if worldviews:
            # Using json.dumps for a more readable structured output if available
            try:
                print(json.dumps(worldviews, ensure_ascii=False, indent=2))
            except ImportError: # Fallback if json is not available for some reason
                for i, worldview_detail in enumerate(worldviews):
                    print(f"\n--- Worldview Option {i+1} ---")
                    print(f"  World Name: {worldview_detail.get('world_name')}")
                    print(f"  Core Concept: {worldview_detail.get('core_concept')}")
                    print(f"  Key Elements: {worldview_detail.get('key_elements')}")
                    print(f"  Atmosphere: {worldview_detail.get('atmosphere')}")
                    # print(f"  Raw LLM: {worldview_detail.get('raw_llm_output_for_worldview')}")
        else:
            print("No worldview options were generated or parsed.")
            if os.getenv("OPENAI_API_KEY") and "dummy" in os.getenv("OPENAI_API_KEY","").lower():
                 print("This might be due to using a dummy API key.")

    except ValueError as ve:
        print(f"Configuration or Input Error: {ve}")
    except openai.APIError as apie:
        print(f"OpenAI API Error: {apie}")
    except Exception as e:
        print(f"An error occurred during agent testing: {e}")
        traceback.print_exc()

    print("\n--- WorldWeaverAgent Test Finished ---")

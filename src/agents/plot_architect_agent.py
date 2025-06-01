import re
from typing import List
from src.llm_abstraction.llm_client import LLMClient

class PlotArchitectAgent:
    def __init__(self):
        try:
            self.llm_client = LLMClient()
        except ValueError as e:
            print(f"Error initializing LLMClient in PlotArchitectAgent: {e}")
            raise
        except Exception as e:
            print(f"An unexpected error occurred during LLMClient initialization in PlotArchitectAgent: {e}")
            raise

    def _construct_prompt(self, narrative_outline: str, worldview_data: str) -> str:
        prompt = f"""You are a master storyteller and plot architect.
Based on the following narrative outline and worldview, generate 3-5 key plot points that will form the backbone of an engaging story.
Each plot point should be a concise summary (1-2 sentences) of a significant event, conflict escalation, turning point, or resolution stage.
Please output these plot points as a numbered or bulleted list, with each point on a new line.

Narrative Outline:
---
{narrative_outline}
---

Worldview Data:
---
{worldview_data}
---

Generate 3-5 key plot points now:
"""
        return prompt

    def _parse_llm_response_to_list(self, llm_response: str) -> List[str]:
        """Parses a string of listed items into a list of strings."""
        if not llm_response:
            return []

        plot_points = []
        # Split by newline, handles various newline characters
        lines = llm_response.strip().splitlines()

        for line in lines:
            stripped_line = line.strip()
            if not stripped_line: # Skip empty lines
                continue

            # Remove common list prefixes (numbers, bullets, hyphens)
            # Regex: matches lines starting with (optional spaces) (number and dot) or (bullet/hyphen) followed by (optional spaces)
            cleaned_line = re.sub(r"^\s*(\d+\.|\*|-)\s*", "", stripped_line)

            if cleaned_line: # Ensure line is not empty after stripping prefixes
                plot_points.append(cleaned_line)

        return plot_points

    def generate_plot_points(self, narrative_outline: str, worldview_data: str) -> List[str]:
        """
        Generates a list of key plot points based on the narrative outline and worldview.
        """
        if not narrative_outline:
            raise ValueError("Narrative outline cannot be empty.")
        if not worldview_data:
            raise ValueError("Worldview data cannot be empty.")

        prompt = self._construct_prompt(narrative_outline, worldview_data)

        print(f"PlotArchitectAgent: Sending prompt for plot point generation to LLM.")
        # print(f"PlotArchitectAgent: Prompt content:\n{prompt[:400]}...") # For debugging

        try:
            llm_response_text = self.llm_client.generate_text(
                prompt=prompt,
                model_name="gpt-3.5-turbo", # Or a configurable model
                max_tokens=400 # Adjust as needed for 3-5 plot points
            )
            print("PlotArchitectAgent: Received plot points text from LLM.")

            parsed_plot_points = self._parse_llm_response_to_list(llm_response_text)

            if not parsed_plot_points and llm_response_text:
                # LLM responded but parsing failed to extract points
                print(f"PlotArchitectAgent: Warning - LLM responded but no plot points were parsed. LLM raw response: {llm_response_text}")
                # Fallback: return the raw response as a single plot point, or handle as error
                # For now, let's return an empty list if parsing fails, signaling an issue.
                return []

            print(f"PlotArchitectAgent: Parsed {len(parsed_plot_points)} plot points.")
            return parsed_plot_points

        except Exception as e:
            print(f"PlotArchitectAgent: Error during LLM call or parsing - {e}")
            # Consider how to handle this: raise, return empty, etc.
            # For now, re-raising to make it visible.
            raise

if __name__ == "__main__":
    print("--- Testing PlotArchitectAgent ---")

    sample_outline = "A detective in a futuristic city, haunted by his past, takes on a case involving a mysterious new street drug that causes vivid, shared hallucinations. He must navigate the city's corrupt underbelly and his own demons to find the source."
    sample_worldview = "The city is Neo-Veridia, a sprawling megalopolis in 2242, characterized by towering skyscrapers, constant rain, and extreme social stratification. Advanced bio-enhancements are common, but heavily regulated. The mood is noirish and cynical, with an undercurrent of digital surrealism due to pervasive AR."

    try:
        agent = PlotArchitectAgent()
        print("PlotArchitectAgent initialized.")

        print(f"Generating plot points for sample outline and worldview...")
        plot_points = agent.generate_plot_points(
            narrative_outline=sample_outline,
            worldview_data=sample_worldview
        )

        print("\nGenerated Plot Points:")
        if plot_points:
            for i, point in enumerate(plot_points):
                print(f"{i+1}. {point}")
        else:
            print("No plot points were generated or parsed.")

    except ValueError as ve:
        print(f"Configuration or Input Error: {ve}")
    except Exception as e:
        print(f"An error occurred during agent testing: {e}")
    print("--- PlotArchitectAgent Test Finished ---")

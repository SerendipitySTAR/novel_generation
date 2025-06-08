import re
import json
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from src.llm_abstraction.llm_client import LLMClient
from src.core.models import PlotChapterDetail # For type hinting and structure reference
# from src.persistence.database_manager import DatabaseManager # Not directly used by this agent

class PlotTwistAgent:
    """
    Generates plot twist options for a specific target chapter based on the preceding plot.
    """
    def __init__(self, llm_client: Optional[LLMClient] = None, db_name: Optional[str] = None):
        try:
            self.llm_client = llm_client if llm_client else LLMClient()
        except Exception as e:
            print(f"PlotTwistAgent Error: LLMClient initialization failed. {e}")
            raise
        # self.db_manager = DatabaseManager(db_name=db_name) if db_name else None # Not used in this version

    def _construct_prompt(self, preceding_plot_summary: str, target_chapter_number: int, num_options: int) -> str:
        prompt = f"""You are a master storyteller, expert in crafting compelling plot twists.
Based on the summary of the preceding plot, generate {num_options} distinct and interesting plot twist options for Chapter {target_chapter_number}.
Each option should represent a plausible but surprising new direction for the story.

Preceding Plot Summary:
{preceding_plot_summary}

For each of the {num_options} options, provide a detailed chapter plan.
The chapter plan for each option MUST strictly follow this format (including all field names):

BEGIN PLOT TWIST OPTION:
Chapter_Number: {target_chapter_number}
Title: [A compelling title for this chapter option that reflects the twist]
Estimated_Words: [An estimated word count for this chapter, e.g., 1000, 1500, 2000]
Core_Scene_Summary: [A concise summary of the main scene(s) in this chapter option. 2-3 sentences]
Characters_Present: [Comma-separated list of key characters present in this chapter option]
Key_Events_and_Plot_Progression: [Detailed description of key events and how the plot progresses in this specific option. This should clearly articulate the twist. 3-5 sentences]
Goal_and_Conflict: [The primary goal of the protagonist (or focus character) in this chapter option and the main conflict they face. 1-2 sentences]
Turning_Point: [A significant turning point or revelation within this chapter option. 1-2 sentences]
Tone_and_Style_Notes: [Notes on the desired tone and writing style for this chapter option, e.g., "Suspenseful, fast-paced", "Introspective, melancholic".]
Suspense_or_Hook: [How this chapter option ends, creating suspense or a hook for the next chapter. 1 sentence]
Raw_LLM_Output_For_Chapter: [Leave this field empty or with a placeholder like "N/A" - it will be filled later by other processes.]
END PLOT TWIST OPTION.

Ensure each field is present for every option. The "Key_Events_and_Plot_Progression" should be the most detailed and clearly explain the twist.
Generate exactly {num_options} options, each enclosed in "BEGIN PLOT TWIST OPTION:" and "END PLOT TWIST OPTION."
"""
        return prompt

    def _parse_llm_response_for_twists(self, llm_response: str, target_chapter_number: int) -> List[Dict[str, Any]]:
        options_data: List[Dict[str, Any]] = []

        # Regex to find each option block
        option_blocks = re.findall(r"BEGIN PLOT TWIST OPTION:(.*?)END PLOT TWIST OPTION\.", llm_response, re.DOTALL | re.IGNORECASE)

        if not option_blocks:
            print(f"PlotTwistAgent: Could not find any plot twist option blocks in LLM response. Response snippet: {llm_response[:500]}")
            return []

        for block_text in option_blocks:
            block_text = block_text.strip()
            profile_data: Dict[str, Any] = {"chapter_number": target_chapter_number} # Default chapter number

            fields_map = {
                'chapter_number': r"Chapter_Number:\s*(.+)",
                'title': r"Title:\s*(.+)",
                'estimated_words': r"Estimated_Words:\s*(.+)",
                'core_scene_summary': r"Core_Scene_Summary:\s*(.+)",
                'characters_present': r"Characters_Present:\s*(.+)",
                'key_events_and_plot_progression': r"Key_Events_and_Plot_Progression:\s*(.+)",
                'goal_and_conflict': r"Goal_and_Conflict:\s*(.+)",
                'turning_point': r"Turning_Point:\s*(.+)",
                'tone_and_style_notes': r"Tone_and_Style_Notes:\s*(.+)",
                'suspense_or_hook': r"Suspense_or_Hook:\s*(.+)",
                'raw_llm_output_for_chapter': r"Raw_LLM_Output_For_Chapter:\s*(.*)"
            }

            for key, pattern in fields_map.items():
                match = re.search(pattern, block_text, re.IGNORECASE | re.MULTILINE)
                if match:
                    value = match.group(1).strip()
                    if key == 'estimated_words':
                        try:
                            profile_data[key] = int(value)
                        except ValueError:
                            print(f"PlotTwistAgent: Warning - Could not parse '{value}' as integer for Estimated_Words. Setting to None.")
                            profile_data[key] = None
                    elif key == 'characters_present':
                        profile_data[key] = [s.strip() for s in value.split(',') if s.strip()] if value.lower() != 'none' else []
                    elif key == 'raw_llm_output_for_chapter' and (not value or value.lower() == "n/a"):
                        profile_data[key] = None # Store None if placeholder
                    else:
                        profile_data[key] = value
                else:
                    # For PlotChapterDetail, most fields are Optional, so missing is okay.
                    # However, ensure required ones like chapter_number (already defaulted) and title are handled.
                    if key == 'title': # Title is not Optional in PlotChapterDetail if strictly following
                        profile_data[key] = f"Untitled Chapter {target_chapter_number} Option"
                    else:
                        profile_data[key] = None # Set to None if not found and field is Optional
                    print(f"PlotTwistAgent: Warning - Field '{key}' not found in option block.")

            # Ensure chapter_number from parsed block overrides default if present and valid, otherwise keep target_chapter_number
            parsed_cn = profile_data.get('chapter_number')
            if isinstance(parsed_cn, str):
                try:
                    profile_data['chapter_number'] = int(parsed_cn)
                except ValueError:
                    profile_data['chapter_number'] = target_chapter_number # Fallback
            elif not isinstance(parsed_cn, int) :
                 profile_data['chapter_number'] = target_chapter_number


            # Validate that essential fields are present (e.g. title, key_events)
            if not profile_data.get('title') or not profile_data.get('key_events_and_plot_progression'):
                print(f"PlotTwistAgent: Warning - Skipping an option due to missing critical fields (title or key_events). Block snippet: {block_text[:200]}")
                continue

            options_data.append(profile_data)

        return options_data

    def generate_twist_options(self, novel_id: int, current_plot_details: List[Dict[str, Any]], target_chapter_number: int, num_options: int = 2) -> List[Dict[str, Any]]:
        """
        Generates plot twist options for the target_chapter_number.
        novel_id is currently unused by this agent directly but kept for API consistency.
        """
        if not current_plot_details:
            print("PlotTwistAgent: Warning - No preceding plot details provided. Generating generic twists.")
            preceding_plot_summary = "The story has just begun."
        else:
            # Create a summary of chapters before the target chapter
            relevant_plot_details = [
                chap for chap in current_plot_details
                if chap.get('chapter_number', 0) < target_chapter_number
            ]
            relevant_plot_details.sort(key=lambda x: x.get('chapter_number', 0)) # Sort by chapter number

            summary_parts = []
            for chap_detail in relevant_plot_details:
                summary_parts.append(
                    f"Chapter {chap_detail.get('chapter_number', 'N/A')} ({chap_detail.get('title', 'Untitled')}): "
                    f"{chap_detail.get('key_events_and_plot_progression', chap_detail.get('core_scene_summary', 'No summary.'))}"
                )
            preceding_plot_summary = "\n".join(summary_parts)
            if not preceding_plot_summary:
                 preceding_plot_summary = f"No plot details available before Chapter {target_chapter_number}. The story is about to unfold for this chapter."


        prompt = self._construct_prompt(preceding_plot_summary, target_chapter_number, num_options)

        try:
            # Assuming a utility for dynamic token calculation exists
            # from src.utils.dynamic_token_config import get_dynamic_max_tokens
            # context_for_tokens = {"plot_summary": preceding_plot_summary, "num_options": num_options}
            # max_tokens = get_dynamic_max_tokens("plot_twist_generation", context_for_tokens)
            max_tokens = 3000 # Fallback or default if dynamic config not used here

            llm_response = self.llm_client.generate_text(
                prompt=prompt,
                model_name="gpt-4o-2024-08-06", # Or a suitable model
                max_tokens=max_tokens
            )
        except Exception as e:
            print(f"PlotTwistAgent: LLM call failed - {e}")
            return []

        if not llm_response:
            print("PlotTwistAgent: LLM returned an empty response.")
            return []

        parsed_options = self._parse_llm_response_for_twists(llm_response, target_chapter_number)

        # Ensure the correct number of options are returned, or handle discrepancies
        if len(parsed_options) != num_options:
            print(f"PlotTwistAgent: Warning - Expected {num_options} options, but parsed {len(parsed_options)}.")
            # Could try to generate more, or pad, or just return what was parsed.
            # For now, return what was parsed.

        # Validate structure against PlotChapterDetail (loosely, as it's a dict)
        final_options = []
        for option_dict in parsed_options:
            try:
                # This is a runtime check; static type checkers won't catch dict mismatches with TypedDict fully.
                # Option is to cast to PlotChapterDetail if needed by consumers, or ensure keys match.
                # For now, we assume the parser creates dicts that are compatible.
                # Example: PlotChapterDetail(**option_dict) # This would fail if keys mismatch or types are wrong
                final_options.append(option_dict)
            except TypeError as te:
                print(f"PlotTwistAgent: Warning - Parsed option does not match PlotChapterDetail structure: {te}. Option: {option_dict}")
                continue # Skip this option

        return final_options

if __name__ == "__main__":
    print("--- Testing PlotTwistAgent ---")
    # Mock LLMClient or use a real one with .env setup
    # For this test, we'll assume LLMClient can be instantiated.
    # load_dotenv() # If using real LLM

    agent = PlotTwistAgent()

    sample_plot_details = [
        {"chapter_number": 1, "title": "The Discovery", "key_events_and_plot_progression": "Alice finds a mysterious map in her attic."},
        {"chapter_number": 2, "title": "The Journey Begins", "core_scene_summary": "Alice follows the map to a hidden cave."},
    ]

    target_chapter = 3
    num_twist_options = 2
    print(f"\nGenerating {num_twist_options} twist options for Chapter {target_chapter}...")

    # This will make a real LLM call if OPENAI_API_KEY is set and valid.
    # Otherwise, LLMClient might raise an error or use a dummy response if configured.
    try:
        twist_options_result = agent.generate_twist_options(
            novel_id=1, # Dummy novel_id
            current_plot_details=sample_plot_details,
            target_chapter_number=target_chapter,
            num_options=num_twist_options
        )

        if twist_options_result:
            print(f"\n--- Generated Plot Twist Options ({len(twist_options_result)} received) ---")
            for i, option in enumerate(twist_options_result):
                print(f"\nOption {i+1}:")
                for key, value in option.items():
                    print(f"  {key}: {value}")
        else:
            print("No plot twist options were generated by the agent.")

    except Exception as e:
        print(f"Error during PlotTwistAgent test: {e}")
        import traceback
        traceback.print_exc()

    print("\n--- PlotTwistAgent Test Finished ---")

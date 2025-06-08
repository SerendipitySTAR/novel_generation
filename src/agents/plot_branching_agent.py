import re
import json
from typing import List, Optional, Dict, Any

from src.llm_abstraction.llm_client import LLMClient
from src.core.models import PlotChapterDetail # For type hinting and structure reference

class PlotBranchingAgent:
    """
    Generates multiple distinct plot continuation paths (branches),
    each consisting of several chapter outlines.
    """
    def __init__(self, llm_client: Optional[LLMClient] = None, db_name: Optional[str] = None):
        try:
            self.llm_client = llm_client if llm_client else LLMClient()
        except Exception as e:
            print(f"PlotBranchingAgent Error: LLMClient initialization failed. {e}")
            raise
        # self.db_manager = DatabaseManager(db_name=db_name) # Not used in this version

    def _construct_prompt(self, preceding_plot_summary: str, branch_point_chapter_number: int, num_options: int, num_chapters_per_branch: int) -> str:
        prompt = f"""You are a master narrative strategist, specializing in creating divergent plotlines.
Based on the summary of the plot leading up to Chapter {branch_point_chapter_number}, generate {num_options} distinct and significantly different plot continuation paths.
Each path (branch) should consist of {num_chapters_per_branch} chapter outlines, starting from Chapter {branch_point_chapter_number}.

Preceding Plot Summary (up to end of Chapter {branch_point_chapter_number - 1}):
---
{preceding_plot_summary}
---

For each of the {num_options} plot branch options:
1.  Provide a brief (1-2 sentences) overall theme or direction for this specific branch.
2.  Then, for each of the {num_chapters_per_branch} chapters within that branch, provide a detailed chapter plan.
    The chapter numbers for these plans must start from {branch_point_chapter_number} and increment sequentially within the branch.

Use the following format for EACH branch option:

BEGIN PLOT BRANCH OPTION:
Branch_Theme: [Brief overall theme/direction of this branch]

--- Branch Chapter 1 (Overall Chapter {branch_point_chapter_number}) ---
Chapter_Number: {branch_point_chapter_number}
Title: [Title for this chapter in this branch]
Estimated_Words: [e.g., 1000, 1500]
Core_Scene_Summary: [Main scene(s) summary. 2-3 sentences]
Characters_Present: [Comma-separated list]
Key_Events_and_Plot_Progression: [Key events & plot progression for this chapter. 3-5 sentences]
Goal_and_Conflict: [Primary goal & conflict. 1-2 sentences]
Turning_Point: [Significant turning point/revelation. 1-2 sentences]
Tone_and_Style_Notes: [e.g., "Suspenseful, fast-paced"]
Suspense_or_Hook: [Ending hook. 1 sentence]
Raw_LLM_Output_For_Chapter: [N/A]

--- Branch Chapter 2 (Overall Chapter {branch_point_chapter_number + 1}) ---
Chapter_Number: {branch_point_chapter_number + 1}
Title: [Title for this chapter in this branch]
Estimated_Words: [...]
Core_Scene_Summary: [...]
Characters_Present: [...]
Key_Events_and_Plot_Progression: [...]
Goal_and_Conflict: [...]
Turning_Point: [...]
Tone_and_Style_Notes: [...]
Suspense_or_Hook: [...]
Raw_LLM_Output_For_Chapter: [N/A]

... (continue for all {num_chapters_per_branch} chapters in this branch, incrementing Chapter_Number accordingly) ...
END PLOT BRANCH OPTION.

Ensure each field is present for every chapter within every branch.
Generate exactly {num_options} distinct plot branch options.
"""
        return prompt

    def _parse_llm_response_for_branches(self, llm_response: str, start_chapter_number: int, num_chapters_per_branch: int) -> List[List[Dict[str, Any]]]:
        all_branches_data: List[List[Dict[str, Any]]] = []

        branch_option_blocks = re.findall(r"BEGIN PLOT BRANCH OPTION:(.*?)END PLOT BRANCH OPTION\.", llm_response, re.DOTALL | re.IGNORECASE)

        if not branch_option_blocks:
            print(f"PlotBranchingAgent: No plot branch option blocks found. Response snippet: {llm_response[:500]}")
            return []

        for branch_block_text in branch_option_blocks:
            branch_block_text = branch_block_text.strip()
            current_branch_chapters: List[Dict[str, Any]] = []

            # Extract Branch_Theme (optional, for context or logging)
            theme_match = re.search(r"Branch_Theme:\s*(.*)", branch_block_text, re.IGNORECASE)
            branch_theme = theme_match.group(1).strip() if theme_match else "N/A"
            print(f"PlotBranchingAgent: Parsing branch with theme: {branch_theme}")

            # Find individual chapter blocks within this branch
            # Using a simpler split based on "--- Branch Chapter X ---" or "Chapter_Number:"
            # This assumes chapters are somewhat consistently delimited.
            chapter_sections = re.split(r"---\s*Branch Chapter\s*\d+\s*\(Overall Chapter\s*\d+\)\s*---", branch_block_text)
            if len(chapter_sections) <= 1: # If primary split fails, try splitting by "Chapter_Number:" as a delimiter
                 # Look for "Chapter_Number:" as start of a chapter, ensuring it's not part of another field.
                 # This regex looks for "Chapter_Number:" at the beginning of a line or after a clear separator.
                 chapter_sections = re.split(r"(?m)(?=^\s*Chapter_Number:)", branch_block_text)


            expected_chapter_num_counter = start_chapter_number

            for i, chapter_text_block in enumerate(chapter_sections):
                chapter_text_block = chapter_text_block.strip()
                if not chapter_text_block or chapter_text_block.lower() == "branch_theme:": # Skip empty blocks or theme line if it was caught by split
                    if "branch_theme:" in chapter_text_block.lower() and theme_match and chapter_text_block.strip() == theme_match.group(0).strip():
                        continue # Skip the theme line itself if caught as a section
                    if not chapter_text_block.strip():
                        continue


                if len(current_branch_chapters) >= num_chapters_per_branch:
                    break # Already collected enough chapters for this branch

                profile_data: Dict[str, Any] = {}

                fields_map = {
                    'chapter_number': r"Chapter_Number:\s*(\d+)",
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

                parsed_any_field = False
                for key, pattern in fields_map.items():
                    match = re.search(pattern, chapter_text_block, re.IGNORECASE | re.MULTILINE | re.DOTALL)
                    if match:
                        parsed_any_field = True
                        value = match.group(1).strip()
                        if key == 'chapter_number' or key == 'estimated_words':
                            try: profile_data[key] = int(value)
                            except ValueError: profile_data[key] = None
                        elif key == 'characters_present':
                            profile_data[key] = [s.strip() for s in value.split(',') if s.strip()] if value.lower() != 'none' else []
                        elif key == 'raw_llm_output_for_chapter' and (not value or value.lower() == "n/a"):
                            profile_data[key] = None
                        else:
                            profile_data[key] = value
                    else:
                        profile_data[key] = None # Default to None if not found

                if not parsed_any_field and len(chapter_sections) > 1 and i==0: # Often the first split part is empty or just the theme.
                    continue


                # Assign chapter number if not parsed or if it's the first chapter of the branch
                # The prompt specifies chapter numbers, but this ensures they are sequential from branch_point.
                if not profile_data.get('chapter_number') or (len(current_branch_chapters) == 0 and profile_data.get('chapter_number') != start_chapter_number) :
                     profile_data['chapter_number'] = start_chapter_number + len(current_branch_chapters)

                # Correct sequential numbering based on its position in this branch
                current_sequential_chapter_num = start_chapter_number + len(current_branch_chapters)
                if profile_data.get('chapter_number') != current_sequential_chapter_num:
                    print(f"PlotBranchingAgent: Warning - Parsed chapter number {profile_data.get('chapter_number')} for branch {len(all_branches_data)+1} does not match expected sequential number {current_sequential_chapter_num}. Overwriting.")
                    profile_data['chapter_number'] = current_sequential_chapter_num

                if not profile_data.get('title'): # Default title if missing
                    profile_data['title'] = f"Chapter {profile_data['chapter_number']} (Branch {len(all_branches_data)+1})"

                if profile_data.get('title'): # Only add if it seems like a valid chapter block
                    current_branch_chapters.append(profile_data)

            if current_branch_chapters:
                # Ensure the branch has the correct number of chapters, pad if necessary (though LLM should provide)
                while len(current_branch_chapters) < num_chapters_per_branch:
                    print(f"PlotBranchingAgent: Warning - Branch {len(all_branches_data)+1} has {len(current_branch_chapters)} chapters, expected {num_chapters_per_branch}. Padding with placeholder.")
                    placeholder_chap_num = start_chapter_number + len(current_branch_chapters)
                    current_branch_chapters.append({
                        "chapter_number": placeholder_chap_num,
                        "title": f"Placeholder Chapter {placeholder_chap_num}",
                        "core_scene_summary": "This chapter is a placeholder due to insufficient generation for this branch.",
                        "key_events_and_plot_progression": "Placeholder events.",
                        # ... other fields can be None or have placeholders
                    })
                all_branches_data.append(current_branch_chapters[:num_chapters_per_branch]) # Ensure correct length

        return all_branches_data

    def generate_branching_plot_options(self, novel_id: int, current_plot_details: List[Dict[str, Any]],
                                         branch_point_chapter_number: int, num_options: int = 2,
                                         num_chapters_per_branch: int = 3) -> List[List[Dict[str, Any]]]:

        if not current_plot_details:
            preceding_plot_summary = f"The story is about to begin at Chapter {branch_point_chapter_number}. No prior plot details exist."
        else:
            relevant_plot_details = [
                chap for chap in current_plot_details
                if chap.get('chapter_number', 0) < branch_point_chapter_number
            ]
            relevant_plot_details.sort(key=lambda x: x.get('chapter_number', 0))

            summary_parts = []
            for chap_detail in relevant_plot_details:
                summary_parts.append(
                    f"Ch {chap_detail.get('chapter_number', 'N/A')} ({chap_detail.get('title', 'Untitled')}): "
                    f"{chap_detail.get('key_events_and_plot_progression', chap_detail.get('core_scene_summary', 'No summary.'))}"
                )
            preceding_plot_summary = "\n".join(summary_parts) if summary_parts else f"No plot details available before Chapter {branch_point_chapter_number}."

        prompt = self._construct_prompt(preceding_plot_summary, branch_point_chapter_number, num_options, num_chapters_per_branch)

        try:
            max_tokens = 1000 + (num_options * num_chapters_per_branch * 400) # Estimate tokens

            llm_response = self.llm_client.generate_text(
                prompt=prompt,
                model_name="gpt-4o-2024-08-06",
                max_tokens=min(max_tokens, 8000) # Cap at a reasonable max
            )
        except Exception as e:
            print(f"PlotBranchingAgent: LLM call failed - {e}")
            return []

        if not llm_response:
            print("PlotBranchingAgent: LLM returned an empty response.")
            return []

        parsed_branches = self._parse_llm_response_for_branches(llm_response, branch_point_chapter_number, num_chapters_per_branch)

        if len(parsed_branches) != num_options:
            print(f"PlotBranchingAgent: Warning - Expected {num_options} branches, but parsed {len(parsed_branches)}.")
            # Could add logic to pad or truncate if strict number of branches is needed.

        return parsed_branches

if __name__ == "__main__":
    print("--- Testing PlotBranchingAgent ---")
    # Requires OPENAI_API_KEY in .env or environment for LLMClient
    # from dotenv import load_dotenv
    # load_dotenv()

    agent = PlotBranchingAgent()

    sample_plot_so_far = [
        {"chapter_number": 1, "title": "The Old Manor", "key_events_and_plot_progression": "A group of friends decides to explore an abandoned manor."},
        {"chapter_number": 2, "title": "Whispers in the Dark", "core_scene_summary": "They find a hidden diary hinting at a treasure, but also a curse. One friend gets separated."},
        {"chapter_number": 3, "title": "The Ritual Chamber", "key_events_and_plot_progression": "The separated friend is found in a ritual chamber, unharmed but changed. The diary speaks of a choice at the 'Crossroads of Fate'."}
    ]

    branch_chapter = 4
    num_branch_options = 2
    chapters_in_branch = 2 # Shorter for testing

    print(f"\nGenerating {num_branch_options} branching options from Chapter {branch_chapter}, each with {chapters_in_branch} chapters...")

    try:
        branch_options_result = agent.generate_branching_plot_options(
            novel_id=1, # Dummy
            current_plot_details=sample_plot_so_far,
            branch_point_chapter_number=branch_chapter,
            num_options=num_branch_options,
            num_chapters_per_branch=chapters_in_branch
        )

        if branch_options_result:
            print(f"\n--- Generated Plot Branch Options ({len(branch_options_result)} received) ---")
            for i, branch_path in enumerate(branch_options_result):
                print(f"\nBranch Option {i+1} (contains {len(branch_path)} chapters):")
                for chapter_idx, chapter_detail in enumerate(branch_path):
                    print(f"  Chapter {chapter_idx+1} of branch (Overall Chapter {chapter_detail.get('chapter_number', 'N/A')}):")
                    print(f"    Title: {chapter_detail.get('title', 'N/A')}")
                    print(f"    Summary: {chapter_detail.get('core_scene_summary', 'N/A')}")
                    print(f"    Events: {chapter_detail.get('key_events_and_plot_progression', 'N/A')}")
        else:
            print("No plot branch options were generated by the agent.")

    except Exception as e:
        print(f"Error during PlotBranchingAgent test: {e}")
        import traceback
        traceback.print_exc()

    print("\n--- PlotBranchingAgent Test Finished ---")

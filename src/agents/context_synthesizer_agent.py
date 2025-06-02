import os
from typing import List, Dict, Optional
from dotenv import load_dotenv
import json # Required for potential plot deserialization if needed directly here

from src.persistence.database_manager import DatabaseManager
from src.agents.lore_keeper_agent import LoreKeeperAgent
from src.core.models import Character, Chapter, Novel, Outline, WorldView, Plot, PlotChapterDetail, DetailedCharacterProfile # Added PlotChapterDetail, DetailedCharacterProfile

class ContextSynthesizerAgent:
    def __init__(self, db_name: str = "novel_mvp.db", chroma_db_directory: str = "./chroma_db"):
        self.db_manager = DatabaseManager(db_name=db_name)
        try:
            self.lore_keeper = LoreKeeperAgent(db_name=db_name, chroma_db_directory=chroma_db_directory)
        except ValueError as e:
            print(f"Error initializing LoreKeeperAgent in ContextSynthesizerAgent: {e}")
            raise

    def generate_chapter_brief(self, novel_id: int, current_chapter_number: int,
                               current_chapter_plot_summary_for_brief: str, # Renamed for clarity, this is from PlotChapterDetail
                               active_character_ids: List[int]) -> str:
        brief_parts: List[str] = []

        novel: Optional[Novel] = self.db_manager.get_novel_by_id(novel_id)
        if novel:
            brief_parts.append(f"**Novel Theme:** {novel['user_theme']}")
            brief_parts.append(f"**Style Preferences:** {novel['style_preferences']}\n")

            outline: Optional[Outline] = self.db_manager.get_outline_by_id(novel['active_outline_id']) if novel['active_outline_id'] else None
            if outline:
                brief_parts.append(f"**Overall Novel Outline:**\n{outline['overview_text']}\n")

            worldview_db: Optional[WorldView] = self.db_manager.get_worldview_by_id(novel['active_worldview_id']) if novel['active_worldview_id'] else None
            if worldview_db: # worldview_db.description_text is the core_concept from selected WorldviewDetail
                brief_parts.append(f"**Worldview Core Concept:**\n{worldview_db['description_text']}\n")

            # The plot_summary in DB is a JSON string of List[PlotChapterDetail]
            # We don't need the full plot here, as current_chapter_plot_summary_for_brief is passed in.
            # However, if we wanted overall plot arc, we could deserialize:
            # plot_db: Optional[Plot] = self.db_manager.get_plot_by_id(novel['active_plot_id']) if novel['active_plot_id'] else None
            # if plot_db and plot_db['plot_summary']:
            #     try:
            #         all_chapter_plots: List[PlotChapterDetail] = json.loads(plot_db['plot_summary'])
            #         # Could then summarize all_chapter_plots if needed for "Main Plot Arc"
            #         brief_parts.append(f"**Main Plot Arc (Summary from detailed plot - first chapter for example):**\n{all_chapter_plots[0].get('key_events_and_plot_progression', 'N/A')}\n")
            #     except json.JSONDecodeError:
            #         brief_parts.append(f"**Main Plot Arc (Raw from DB):**\n{plot_db['plot_summary']}\n")


        # Previous Chapter Summaries
        all_db_chapters: List[Chapter] = self.db_manager.get_chapters_for_novel(novel_id)
        previous_chapters_summaries_text: List[str] = []
        for ch_db in sorted(all_db_chapters, key=lambda c: c['chapter_number']):
            if ch_db['chapter_number'] < current_chapter_number:
                previous_chapters_summaries_text.append(f"  - Chapter {ch_db['chapter_number']} ({ch_db['title']}) Summary: {ch_db['summary']}")

        if previous_chapters_summaries_text:
            brief_parts.append("**Previously Happened:**\n" + "\n".join(previous_chapters_summaries_text) + "\n")

        # Active Character Details (now using DetailedCharacterProfile)
        active_characters_details_text: List[str] = []
        active_character_names_for_lore_query: List[str] = []

        # Fetch all characters for the novel, then filter by active_character_ids
        # DatabaseManager now returns List[DetailedCharacterProfile]
        all_character_profiles: List[DetailedCharacterProfile] = self.db_manager.get_characters_for_novel(novel_id)

        active_character_profiles: List[DetailedCharacterProfile] = []
        if active_character_ids:
            for char_prof in all_character_profiles:
                if char_prof.get("character_id") in active_character_ids: # character_id is Optional
                    active_character_profiles.append(char_prof)
        else: # Fallback if no specific IDs, take first few
            active_character_profiles = all_character_profiles[:2]


        for char_profile in active_character_profiles:
            char_name = char_profile.get('name', 'N/A')
            active_character_names_for_lore_query.append(char_name)
            char_info = (
                f"  - **{char_name}** (Role: {char_profile.get('role_in_story', 'N/A')})\n"
                f"    Traits: {char_profile.get('personality_traits', 'N/A')}\n"
                f"    Motivation: {char_profile.get('motivations_deep_drive', 'N/A')}\n"
                f"    Short-term Goal: {char_profile.get('goal_short_term', 'N/A')}"
            )
            active_characters_details_text.append(char_info)

        if active_characters_details_text:
            brief_parts.append("**Focus Characters for this Chapter:**\n" + "\n".join(active_characters_details_text) + "\n")

        # Current chapter plot summary (passed as argument, derived from PlotChapterDetail by workflow manager)
        brief_parts.append(f"**Specific Plot Focus for THIS Chapter ({current_chapter_number}):**\n{current_chapter_plot_summary_for_brief}\n")

        # Get Context from LoreKeeperAgent
        print(f"ContextSynthesizer: Querying LoreKeeper for novel_id {novel_id} with focus '{current_chapter_plot_summary_for_brief[:100]}...' and characters {active_character_names_for_lore_query}")
        lore_context = self.lore_keeper.get_context_for_chapter(
            novel_id,
            current_plot_focus=current_chapter_plot_summary_for_brief,
            active_characters_in_scene=active_character_names_for_lore_query
        )
        brief_parts.append(f"--- RELEVANT LORE AND CONTEXT (from Knowledge Base) ---\n{lore_context}\n--- END LORE AND CONTEXT ---\n")

        brief_parts.append("--- END OF BRIEF ---")
        return "\n\n".join(brief_parts) # Use double newline for better section separation in final brief

if __name__ == "__main__":
    print("--- Testing ContextSynthesizerAgent ---")
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY") or "dummy" in os.getenv("OPENAI_API_KEY", "").lower():
        print("WARNING: A valid OPENAI_API_KEY is required for full testing (LoreKeeper RAG).")

    test_sql_db_name = "test_context_synth_agent_v2.db"
    test_chroma_db_dir = "./test_context_synth_chroma_v2"
    import shutil
    if os.path.exists(test_sql_db_name): os.remove(test_sql_db_name)
    if os.path.exists(test_chroma_db_dir): shutil.rmtree(test_chroma_db_dir)

    db_mngr = DatabaseManager(db_name=test_sql_db_name)

    novel_id_test = db_mngr.add_novel("Test Novel for Context", "Fantasy")
    outline_id_test = db_mngr.add_outline(novel_id_test, "A hero seeks a lost artifact.")
    worldview_id_test = db_mngr.add_worldview(novel_id_test, "A world of floating islands and sky-ships.")

    # Create sample PlotChapterDetail list and store its JSON
    sample_plot_details_list: List[PlotChapterDetail] = [
        {
            "chapter_number": 1, "title": "The Call", "estimated_words": 1000,
            "core_scene_summary": "The hero, Kael, lives a quiet life in his village.",
            "characters_present": ["Kael", "Elder Maeve"],
            "key_events_and_plot_progression": "A mysterious illness strikes the village. Elder Maeve reveals that only the Sunstone of Eldoria can cure it. Kael is chosen for the quest.",
            "goal_and_conflict": "Kael's goal is to accept the quest. Conflict: his self-doubt and fear of the unknown.",
            "turning_point": "Kael accepts the quest after seeing a loved one fall ill.",
            "tone_and_style_notes": "Hopeful but with a sense of urgency.",
            "suspense_or_hook": "Elder Maeve gives Kael a cryptic map fragment.",
            "raw_llm_output_for_chapter": "..."
        },
        {
            "chapter_number": 2, "title": "Into the Whispering Woods", "estimated_words": 1200,
            "core_scene_summary": "Kael enters the perilous Whispering Woods, the first step on his journey.",
            "characters_present": ["Kael", "Mysterious Forest Spirit"],
            "key_events_and_plot_progression": "Kael navigates dangerous flora. Encounters a mischievous forest spirit who offers a riddle or a challenge in exchange for passage.",
            "goal_and_conflict": "Kael must safely pass through the woods. Conflict: the woods' natural dangers and the spirit's tricks.",
            "turning_point": "Kael solves the riddle/passes the challenge, earning the spirit's respect or a useful charm.",
            "tone_and_style_notes": "Mysterious, adventurous, slightly tense.",
            "suspense_or_hook": "The spirit warns of a 'shadow that follows' Kael.",
            "raw_llm_output_for_chapter": "..."
        }
    ]
    plot_id_test = db_mngr.add_plot(novel_id_test, json.dumps(sample_plot_details_list))

    db_mngr.update_novel_active_outline(novel_id_test, outline_id_test)
    db_mngr.update_novel_active_worldview(novel_id_test, worldview_id_test)
    db_mngr.update_novel_active_plot(novel_id_test, plot_id_test)

    # Add Characters (now storing DetailedCharacterProfile as JSON in description)
    char1_profile = DetailedCharacterProfile(character_id=None, novel_id=novel_id_test, name="Kael", role_in_story="Protagonist", creation_date=datetime.now(timezone.utc).isoformat(),
                                           personality_traits="Brave, Resourceful", motivations_deep_drive="Protect his village", goal_short_term="Find the Sunstone")
    char1_desc_json = json.dumps({k:v for k,v in char1_profile.items() if k not in ['character_id', 'novel_id', 'creation_date', 'name', 'role_in_story']})
    char1_id = db_mngr.add_character(novel_id_test, char1_profile['name'], char1_desc_json, char1_profile['role_in_story'])

    char2_profile = DetailedCharacterProfile(character_id=None, novel_id=novel_id_test, name="Elder Maeve", role_in_story="Mentor", creation_date=datetime.now(timezone.utc).isoformat(),
                                           personality_traits="Wise, Mysterious", motivations_deep_drive="Preserve ancient knowledge", goal_short_term="Guide Kael")
    char2_desc_json = json.dumps({k:v for k,v in char2_profile.items() if k not in ['character_id', 'novel_id', 'creation_date', 'name', 'role_in_story']})
    char2_id = db_mngr.add_character(novel_id_test, char2_profile['name'], char2_desc_json, char2_profile['role_in_story'])

    db_mngr.add_chapter(novel_id_test, 1, "The Call", "Content of chapter 1...", "Kael accepts the quest.")

    # Initialize LoreKeeper for the context synthesizer
    # This will attempt RAG, may fail if API key is dummy, but ContextSynthesizer should handle it
    try:
        lore_keeper_for_test = LoreKeeperAgent(db_name=test_sql_db_name, chroma_db_directory=test_chroma_db_dir)
        novel_obj = db_mngr.get_novel_by_id(novel_id_test)
        outline_obj = db_mngr.get_outline_by_id(outline_id_test)
        worldview_obj = db_mngr.get_worldview_by_id(worldview_id_test)
        plot_obj = db_mngr.get_plot_by_id(plot_id_test) # Contains JSON string
        characters_for_kb = db_mngr.get_characters_for_novel(novel_id_test) # List[DetailedCharacterProfile]

        # Adapt characters for LoreKeeperAgent if it expects List[Character]
        # For this test, we assume LoreKeeperAgent can handle List[DetailedCharacterProfile] or extracts needed fields.
        # If not, a conversion step would be needed here.
        if novel_obj and outline_obj and worldview_obj and plot_obj and characters_for_kb:
            lore_keeper_for_test.initialize_knowledge_base(novel_id_test, outline_obj, worldview_obj, plot_obj, characters_for_kb) # type: ignore
            print("LoreKeeperAgent initialized for test.")
        else:
            print("ERROR: Failed to fetch all components for LoreKeeper init.")
    except Exception as e:
        print(f"Error initializing LoreKeeper for test: {e}")


    agent = ContextSynthesizerAgent(db_name=test_sql_db_name, chroma_db_directory=test_chroma_db_dir)
    print("ContextSynthesizerAgent initialized.")

    # Test for Chapter 2, using plot details for Chapter 2
    target_chapter_num_test = 2
    # The plot summary for the brief is now derived by WorkflowManager's execute_context_synthesizer_agent node.
    # Here, we simulate that derivation.
    current_chap_detail_for_brief = sample_plot_details_list[target_chapter_num_test - 1]
    plot_summary_for_brief = current_chap_detail_for_brief.get('key_events_and_plot_progression') or \
                             current_chap_detail_for_brief.get('core_scene_summary') or \
                             f"Plot for Chapter {target_chapter_num_test} needs to be developed based on title: {current_chap_detail_for_brief.get('title', 'N/A')}."

    active_ids_test = [char1_id, char2_id] # Kael and Elder Maeve might not be in Ch2 per plot, this is for testing retrieval

    print(f"\nGenerating brief for Chapter {target_chapter_num_test}...")
    brief = agent.generate_chapter_brief(
        novel_id_test,
        target_chapter_num_test,
        plot_summary_for_brief,
        active_ids_test
    )

    print("\n--- Generated Chapter Brief ---")
    print(brief)
    print("--- End of Generated Chapter Brief ---")

    assert f"**Novel Theme:** Test Novel for Context" in brief
    assert "**Overall Novel Outline:**\n" + "A hero seeks a lost artifact." in brief
    assert "**Worldview Core Concept:**\nA world of floating islands and sky-ships." in brief
    assert f"Chapter 1 (The Call) Summary: Kael accepts the quest." in brief
    assert "Character: Kael" in brief
    assert f"Specific Plot Focus for THIS Chapter ({target_chapter_num_test}):\n{plot_summary_for_brief}" in brief
    assert "--- RELEVANT LORE AND CONTEXT (from Knowledge Base) ---" in brief
    print("\nBasic content verification of the brief passed.")

    if os.path.exists(test_sql_db_name): os.remove(test_sql_db_name)
    if os.path.exists(test_chroma_db_dir): shutil.rmtree(test_chroma_db_dir)
    if os.path.exists(".env") and "dummykeyforcontextsynthtesting" in open(".env","r").read(): os.remove(".env")
    print("\n--- ContextSynthesizerAgent Test Finished ---")

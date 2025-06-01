import os
from typing import List, Dict, Optional # Added Optional
from dotenv import load_dotenv

from src.persistence.database_manager import DatabaseManager
from src.agents.lore_keeper_agent import LoreKeeperAgent
from src.core.models import Character, Chapter, Novel, Outline, WorldView, Plot # Added Novel, Outline, WorldView, Plot

class ContextSynthesizerAgent:
    def __init__(self, db_name: str = "novel_mvp.db", chroma_db_directory: str = "./chroma_db"): # Added chroma_db_directory
        self.db_manager = DatabaseManager(db_name=db_name)
        # LoreKeeperAgent instantiation needs the chroma_db_directory and will handle its own API key needs
        try:
            self.lore_keeper = LoreKeeperAgent(db_name=db_name, chroma_db_directory=chroma_db_directory)
        except ValueError as e:
            print(f"Error initializing LoreKeeperAgent in ContextSynthesizerAgent: {e}")
            print("Ensure OPENAI_API_KEY is set for LoreKeeperAgent's KnowledgeBaseManager.")
            raise

    def generate_chapter_brief(self, novel_id: int, current_chapter_number: int, current_chapter_plot_summary: str, active_character_ids: List[int]) -> str:
        brief_parts: List[str] = []

        # Fetch Overall Novel Information
        novel: Optional[Novel] = self.db_manager.get_novel_by_id(novel_id)
        if novel:
            brief_parts.append(f"Novel Theme: {novel['user_theme']}\nStyle: {novel['style_preferences']}\n")

            outline: Optional[Outline] = self.db_manager.get_outline_by_id(novel['active_outline_id']) if novel['active_outline_id'] else None
            if outline:
                brief_parts.append(f"Overall Outline: {outline['overview_text']}\n")

            worldview: Optional[WorldView] = self.db_manager.get_worldview_by_id(novel['active_worldview_id']) if novel['active_worldview_id'] else None
            if worldview:
                brief_parts.append(f"Worldview: {worldview['description_text']}\n")

            main_plot: Optional[Plot] = self.db_manager.get_plot_by_id(novel['active_plot_id']) if novel['active_plot_id'] else None
            if main_plot:
                brief_parts.append(f"Main Plot Arc: {main_plot['plot_summary']}\n")
        else:
            brief_parts.append("Novel information not found.\n")


        # Fetch Previous Chapter Summaries
        all_chapters_for_novel: List[Chapter] = self.db_manager.get_chapters_for_novel(novel_id)
        previous_chapters_summaries: List[str] = []
        # Sort chapters by chapter_number to ensure correct order
        for ch in sorted(all_chapters_for_novel, key=lambda c: c['chapter_number']):
            if ch['chapter_number'] < current_chapter_number:
                previous_chapters_summaries.append(f"Chapter {ch['chapter_number']} ({ch['title']}) Summary: {ch['summary']}")

        if previous_chapters_summaries:
            brief_parts.append("Previous Events:\n" + "\n".join(previous_chapters_summaries) + "\n")

        # Fetch Active Character Details
        active_characters_info: List[str] = []
        active_character_names_for_lore_query: List[str] = []
        for char_id in active_character_ids:
            char: Optional[Character] = self.db_manager.get_character_by_id(char_id)
            if char:
                active_characters_info.append(f"Character: {char['name']} - Role: {char['role_in_story']}. Description: {char['description']}")
                active_character_names_for_lore_query.append(char['name'])

        if active_characters_info:
            brief_parts.append("Focus Characters for this Chapter:\n" + "\n".join(active_characters_info) + "\n")

        # Current chapter focus (already provided as an argument)
        brief_parts.append(f"Current Chapter Focus (Chapter {current_chapter_number}): {current_chapter_plot_summary}\n")

        # Get Context from LoreKeeperAgent
        # This call might fail if API key is dummy/invalid, LoreKeeper handles it by returning basic context
        print(f"Querying LoreKeeper for novel_id {novel_id} with focus '{current_chapter_plot_summary}' and characters {active_character_names_for_lore_query}")
        lore_context = self.lore_keeper.get_context_for_chapter(
            novel_id,
            current_plot_focus=current_chapter_plot_summary,
            active_characters_in_scene=active_character_names_for_lore_query
        )
        brief_parts.append(f"Relevant Lore and Context:\n{lore_context}\n")

        brief_parts.append("--- END OF BRIEF ---")
        return "\n".join(brief_parts)

if __name__ == "__main__":
    print("--- Testing ContextSynthesizerAgent ---")

    # API Key Check (LoreKeeperAgent > KnowledgeBaseManager will need this)
    if not os.path.exists(".env") and not os.getenv("OPENAI_API_KEY"):
        print("Creating a dummy .env file for testing ContextSynthesizerAgent (via LoreKeeperAgent)...")
        with open(".env", "w") as f:
            f.write("OPENAI_API_KEY=\"sk-dummykeyforcontextsynthtesting\"\n")

    load_dotenv()
    if not os.getenv("OPENAI_API_KEY") or "dummykey" in os.getenv("OPENAI_API_KEY", ""):
        print("WARNING: A valid OPENAI_API_KEY is required for full testing of ContextSynthesizerAgent (via LoreKeeperAgent).")
        print("Using a dummy key will result in limited or failing context from LoreKeeperAgent.")

    test_sql_db_name = "test_context_agent.db"
    test_chroma_db_dir = "./test_context_synth_chroma_db" # Unique Chroma dir for this test

    import shutil
    if os.path.exists(test_sql_db_name):
        os.remove(test_sql_db_name)
    if os.path.exists(test_chroma_db_dir):
        shutil.rmtree(test_chroma_db_dir)

    # Initialize DatabaseManager for setup
    db_setup_manager = DatabaseManager(db_name=test_sql_db_name)

    # Initialize LoreKeeperAgent separately for setup, it will create its own Chroma instance
    # This also ensures its own __init__ API key check runs.
    try:
        lore_setup_agent = LoreKeeperAgent(db_name=test_sql_db_name, chroma_db_directory=test_chroma_db_dir)
        print("LoreKeeperAgent for setup initialized.")
    except ValueError as e:
        print(f"Failed to initialize LoreKeeperAgent for setup: {e}")
        # Cleanup and exit if setup agent fails
        if os.path.exists(test_sql_db_name): os.remove(test_sql_db_name)
        if os.path.exists(test_chroma_db_dir): shutil.rmtree(test_chroma_db_dir)
        if os.path.exists(".env") and "dummykeyforcontextsynthtesting" in open(".env").read(): os.remove(".env")
        exit(1)

    # 1. Populate with dummy data
    novel_id = db_setup_manager.add_novel("Chronicles of the Starlight Wand", "Sci-Fantasy Adventure")
    print(f"Created Novel ID: {novel_id}")

    outline_id = db_setup_manager.add_outline(novel_id, "A young inventor finds a wand that channels cosmic energy.")
    worldview_id = db_setup_manager.add_worldview(novel_id, "A universe where ancient magic and advanced tech coexist uneasily.")
    plot_id = db_setup_manager.add_plot(novel_id, "The inventor must learn to control the wand and protect it from a galactic tyrant.")

    # Update novel with active components
    db_setup_manager.update_novel_active_outline(novel_id, outline_id)
    db_setup_manager.update_novel_active_worldview(novel_id, worldview_id)
    db_setup_manager.update_novel_active_plot(novel_id, plot_id)
    print(f"Added and linked Outline, Worldview, Plot for Novel ID: {novel_id}")

    char1_id = db_setup_manager.add_character(novel_id, "Lyra", "Curious inventor, good with gadgets.", "Protagonist")
    char2_id = db_setup_manager.add_character(novel_id, "Zorg", "Menacing cyborg general.", "Antagonist")
    characters = db_setup_manager.get_characters_for_novel(novel_id)
    print(f"Added {len(characters)} characters.")

    chap1_id = db_setup_manager.add_chapter(novel_id, 1, "The Discovery", "Lyra stumbles upon the wand in her workshop.", "Lyra finds wand.")
    chap1_data = db_setup_manager.get_chapter_by_id(chap1_id)
    print(f"Added Chapter 1: '{chap1_data['title'] if chap1_data else 'N/A'}'")


    # 2. Initialize Knowledge Base using LoreKeeperAgent
    print("\nInitializing Knowledge Base via LoreKeeperAgent...")
    novel_obj = db_setup_manager.get_novel_by_id(novel_id)
    outline_obj = db_setup_manager.get_outline_by_id(outline_id)
    worldview_obj = db_setup_manager.get_worldview_by_id(worldview_id)
    plot_obj = db_setup_manager.get_plot_by_id(plot_id)

    if not (novel_obj and outline_obj and worldview_obj and plot_obj and characters and chap1_data):
        print("ERROR: Failed to retrieve all necessary data for KB initialization.")
        # Clean up and exit
        if os.path.exists(test_sql_db_name): os.remove(test_sql_db_name)
        if os.path.exists(test_chroma_db_dir): shutil.rmtree(test_chroma_db_dir)
        if os.path.exists(".env") and "dummykeyforcontextsynthtesting" in open(".env").read(): os.remove(".env")
        exit(1)

    try:
        lore_setup_agent.initialize_knowledge_base(novel_id, outline_obj, worldview_obj, plot_obj, characters)
        lore_setup_agent.update_knowledge_base_with_chapter(novel_id, chap1_data)
        print("Knowledge Base initialized and Chapter 1 added by LoreKeeperAgent.")
    except Exception as e:
        print(f"ERROR during LoreKeeperAgent KB initialization or chapter update: {e}")
        print("This is likely due to an invalid/dummy OPENAI_API_KEY. Subsequent context retrieval may be limited.")


    # 3. Instantiate ContextSynthesizerAgent
    try:
        context_agent = ContextSynthesizerAgent(db_name=test_sql_db_name, chroma_db_directory=test_chroma_db_dir)
        print("\nContextSynthesizerAgent initialized.")
    except ValueError as e:
        print(f"Failed to initialize ContextSynthesizerAgent: {e}")
        # Clean up and exit
        if os.path.exists(test_sql_db_name): os.remove(test_sql_db_name)
        if os.path.exists(test_chroma_db_dir): shutil.rmtree(test_chroma_db_dir)
        if os.path.exists(".env") and "dummykeyforcontextsynthtesting" in open(".env").read(): os.remove(".env")
        exit(1)

    # 4. Generate Chapter Brief for an upcoming chapter
    target_chapter_number = 2
    target_chapter_plot = "Lyra experiments with the wand, accidentally alerting Zorg to its activation."
    target_active_char_ids = [char1_id, char2_id] # Lyra and Zorg

    print(f"\nGenerating brief for Chapter {target_chapter_number}...")
    brief = context_agent.generate_chapter_brief(
        novel_id,
        target_chapter_number,
        target_chapter_plot,
        target_active_char_ids
    )

    print("\n--- Generated Chapter Brief ---")
    print(brief)
    print("--- End of Generated Chapter Brief ---")

    # 5. Verification (basic checks)
    assert f"Novel Theme: {novel_obj['user_theme']}" in brief, "Novel theme missing."
    assert f"Overall Outline: {outline_obj['overview_text']}" in brief, "Outline missing."
    assert f"Worldview: {worldview_obj['description_text']}" in brief, "Worldview missing."
    assert f"Main Plot Arc: {plot_obj['plot_summary']}" in brief, "Main plot missing."
    assert f"Chapter 1 ({chap1_data['title']}) Summary: {chap1_data['summary']}" in brief, "Previous chapter summary missing."
    assert f"Character: {characters[0]['name']}" in brief, "Character info missing."
    assert f"Current Chapter Focus (Chapter {target_chapter_number}): {target_chapter_plot}" in brief, "Current chapter focus missing."
    assert "Relevant Lore and Context:" in brief, "Lore context section missing."
    # More specific check for lore context content can be tricky with dummy keys / real key variations
    if "No specific context found" not in brief and ("dummykey" not in os.getenv("OPENAI_API_KEY","")):
        assert len(brief.split("Relevant Lore and Context:\n")[1].strip()) > 0, "Lore context appears empty with potentially valid key."
    print("\nBasic content verification of the brief passed.")

    # 6. Clean up
    print("\nCleaning up test databases and directories...")
    if os.path.exists(test_sql_db_name):
        os.remove(test_sql_db_name)
        print(f"Removed SQL DB: {test_sql_db_name}")
    if os.path.exists(test_chroma_db_dir):
        shutil.rmtree(test_chroma_db_dir)
        print(f"Removed Chroma DB directory: {test_chroma_db_dir}")

    if os.path.exists(".env") and "dummykeyforcontextsynthtesting" in open(".env").read():
        print("Removing dummy .env file for ContextSynthesizerAgent test...")
        os.remove(".env")

    print("--- ContextSynthesizerAgent Test Finished ---")

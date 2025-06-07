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
            self.lore_keeper = None # Ensure lore_keeper is None if init fails
            # raise # Or handle more gracefully depending on desired behavior if LKA is critical

    def _generate_focused_rag_queries(self, plot_summary: str) -> List[str]:
        if not self.lore_keeper or not self.lore_keeper.llm_client:
            print("ContextSynthesizerAgent: LLMClient for LoreKeeper not available. Falling back to using plot summary as the sole RAG query.")
            return [plot_summary]

        prompt = (
            f"Given the following plot summary for an upcoming novel chapter:\n"
            f"\"{plot_summary}\"\n\n"
            f"Generate a list of 3-5 concise and distinct search query strings or key questions that would be most effective for querying a knowledge base to retrieve relevant background information, lore, character details, or world details needed to write this chapter.\n"
            f"Output these queries as a comma-separated list. For example: \"Sunstone location, Dragon's Peak defenses, Kael's previous encounter with dragons\""
        )
        try:
            response_text = self.lore_keeper.llm_client.generate_text(prompt, max_tokens=150, temperature=0.5)
            if response_text:
                queries = [q.strip() for q in response_text.split(',') if q.strip()]
                if queries:
                    print(f"ContextSynthesizerAgent: Generated focused RAG queries: {queries}")
                    return queries
                else:
                    print("ContextSynthesizerAgent: LLM generated an empty or poorly formatted list of queries. Falling back.")
            else:
                print("ContextSynthesizerAgent: LLM generated no response for RAG queries. Falling back.")
        except Exception as e:
            print(f"ContextSynthesizerAgent: Error during LLM call for RAG query generation: {e}. Falling back.")

        return [plot_summary] # Fallback

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

        # --- Hierarchical Previous Chapter Context ---
        NUM_FULL_TEXT_PREVIOUS = 1
        NUM_SUMMARY_PREVIOUS = 3
        # Older chapters will get titles only

        brief_parts.append("**--- Previous Chapter Context (Hierarchical) ---**")

        all_db_chapters: List[Chapter] = self.db_manager.get_chapters_for_novel(novel_id)
        sorted_chapters = sorted(all_db_chapters, key=lambda c: c['chapter_number'])

        chapters_before_current = [ch for ch in sorted_chapters if ch['chapter_number'] < current_chapter_number]
        chapters_before_current.reverse() # Process in reverse chronological order (most recent first)

        full_text_added_count = 0
        summary_added_count = 0
        titles_added_count = 0

        temp_full_text_section = []
        temp_summary_section = []
        temp_titles_only_section = []

        for ch_db in chapters_before_current:
            ch_num = ch_db['chapter_number']
            ch_title = ch_db['title']
            ch_summary = ch_db['summary']

            if full_text_added_count < NUM_FULL_TEXT_PREVIOUS:
                full_content = ch_db.get('content', 'Content not available.')
                # Using a significant portion of content, or full if short.
                # For example, up to 1500 chars or full content if shorter.
                content_snippet = full_content[:1500] + ("..." if len(full_content) > 1500 else "")
                temp_full_text_section.append(f"  **Chapter {ch_num}: {ch_title} (Full Text Snippet)**\n    {content_snippet}\n")
                full_text_added_count += 1
            elif summary_added_count < NUM_SUMMARY_PREVIOUS:
                temp_summary_section.append(f"  - Chapter {ch_num} ({ch_title}) Summary: {ch_summary}")
                summary_added_count += 1
            else:
                if titles_added_count == 0:
                    temp_titles_only_section.append("  Older Chapter Mentions (Titles):")
                temp_titles_only_section.append(f"    - Chapter {ch_num}: {ch_title}")
                titles_added_count += 1

        if temp_full_text_section:
            brief_parts.append("\n**Immediately Preceding Chapter(s) (Full Text/Detailed Snippet):**")
            brief_parts.extend(reversed(temp_full_text_section))
        if temp_summary_section:
            brief_parts.append("\n**Recent Past Chapters (Summaries):**")
            brief_parts.extend(reversed(temp_summary_section))
        if temp_titles_only_section:
            # Reverse the order of titles so they appear chronologically under the header
            temp_titles_only_section_ordered = list(reversed(temp_titles_only_section))
            # The header "Older Chapter Mentions (Titles):" is already the first element if list is not empty
            # So, we take it out, reverse the rest, and add it back.
            older_header = ""
            actual_titles = []
            if temp_titles_only_section_ordered and "Older Chapter Mentions (Titles):" in temp_titles_only_section_ordered[-1]: # Header was added first, so now last after reverse
                older_header = temp_titles_only_section_ordered.pop() # Remove header
                actual_titles = list(reversed(temp_titles_only_section_ordered)) # Reverse titles back to older first
            else: # Should not happen if titles_added_count logic is correct
                 actual_titles = list(reversed(temp_titles_only_section_ordered))


            brief_parts.append("\n**Earlier Chapter Mentions (Titles):**")
            if older_header and "Older Chapter Mentions (Titles):" not in actual_titles[0] : # Avoid double header if already there
                 pass # The structure of titles_only_section already includes its own sub-header if items exist.
                      # The main header "Earlier Chapter Mentions (Titles):" is added above.
            brief_parts.extend(actual_titles)


        if not temp_full_text_section and not temp_summary_section and not temp_titles_only_section and current_chapter_number > 1:
            brief_parts.append("  (No previous chapters found or processed based on configuration).")
        elif current_chapter_number == 1:
             brief_parts.append("  (This is the first chapter, no preceding chapter context).")

        brief_parts.append("**--- End of Previous Chapter Context ---**\n")

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

        # Get Context from LoreKeeperAgent using focused queries
        focused_queries = self._generate_focused_rag_queries(current_chapter_plot_summary_for_brief)

        aggregated_kb_results_content = []
        seen_kb_document_contents = set()
        retrieved_kb_context_str = "Knowledge Base access unavailable or no relevant information found."

        if self.lore_keeper and self.lore_keeper.kb_manager:
            print(f"ContextSynthesizer: Performing RAG queries for novel_id {novel_id} using {len(focused_queries)} focused queries.")
            for query_str in focused_queries:
                try:
                    # print(f"ContextSynthesizer: RAG Query: '{query_str}'")
                    kb_results_for_query = self.lore_keeper.kb_manager.query_knowledge_base(
                        novel_id, query_str, n_results=2 # Fetch 2 results per focused query
                    )
                    if kb_results_for_query:
                        for doc_content, score in kb_results_for_query:
                            if doc_content not in seen_kb_document_contents:
                                aggregated_kb_results_content.append(
                                    f"- {doc_content} (Source query: '{query_str[:50].strip()}...', Similarity: {score:.2f})"
                                )
                                seen_kb_document_contents.add(doc_content)
                except Exception as e:
                    print(f"ContextSynthesizer: Error during RAG query for '{query_str}': {e}")

            if aggregated_kb_results_content:
                retrieved_kb_context_str = "\n".join(aggregated_kb_results_content)
            else:
                 retrieved_kb_context_str = "No specific information retrieved from Knowledge Base for this chapter's focus using focused queries."
        else:
            print("ContextSynthesizer: LoreKeeper or KBManager not available, skipping RAG queries.")
            retrieved_kb_context_str = "Knowledge Base access unavailable (LoreKeeper not initialized)."


        brief_parts.append(f"--- RELEVANT LORE AND CONTEXT (from Knowledge Base) ---\n{retrieved_kb_context_str}\n--- END LORE AND CONTEXT ---\n")

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
    plot_id_test = db_mngr.add_plot(novel_id_test, json.dumps(sample_plot_details_list, ensure_ascii=False, indent=2))

    db_mngr.update_novel_active_outline(novel_id_test, outline_id_test)
    db_mngr.update_novel_active_worldview(novel_id_test, worldview_id_test)
    db_mngr.update_novel_active_plot(novel_id_test, plot_id_test)

    # Add Characters (now storing DetailedCharacterProfile as JSON in description)
    char1_profile = DetailedCharacterProfile(character_id=None, novel_id=novel_id_test, name="Kael", role_in_story="Protagonist", creation_date=datetime.now(timezone.utc).isoformat(),
                                           personality_traits="Brave, Resourceful", motivations_deep_drive="Protect his village", goal_short_term="Find the Sunstone")
    char1_desc_json = json.dumps({k:v for k,v in char1_profile.items() if k not in ['character_id', 'novel_id', 'creation_date', 'name', 'role_in_story']}, ensure_ascii=False, indent=2)
    char1_id = db_mngr.add_character(novel_id_test, char1_profile['name'], char1_desc_json, char1_profile['role_in_story'])

    char2_profile = DetailedCharacterProfile(character_id=None, novel_id=novel_id_test, name="Elder Maeve", role_in_story="Mentor", creation_date=datetime.now(timezone.utc).isoformat(),
                                           personality_traits="Wise, Mysterious", motivations_deep_drive="Preserve ancient knowledge", goal_short_term="Guide Kael")
    char2_desc_json = json.dumps({k:v for k,v in char2_profile.items() if k not in ['character_id', 'novel_id', 'creation_date', 'name', 'role_in_story']}, ensure_ascii=False, indent=2)
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
    # Assertion for previous chapter context will depend on NUM_FULL_TEXT_PREVIOUS, NUM_SUMMARY_PREVIOUS
    # If current_chapter_number is 2, Chapter 1 ("The Call") should be full text.
    if target_chapter_num_test == 2:
        assert f"Chapter 1: The Call (Full Text Snippet)" in brief
        assert "Content of chapter 1..."[:50] in brief # Check for part of the content
    else: # If testing for chapter > 2, then Chapter 1 summary might appear or just title
        assert f"Chapter 1 (The Call) Summary: Kael accepts the quest." in brief # This might change based on N values

    assert "Kael" in brief # Check for character name, not "Character: Kael"
    assert f"Specific Plot Focus for THIS Chapter ({target_chapter_num_test}):\n{plot_summary_for_brief}" in brief
    assert "--- RELEVANT LORE AND CONTEXT (from Knowledge Base) ---" in brief
    print("\nBasic content verification of the brief passed.")

    if os.path.exists(test_sql_db_name): os.remove(test_sql_db_name)
    if os.path.exists(test_chroma_db_dir): shutil.rmtree(test_chroma_db_dir)
    if os.path.exists(".env") and "dummykeyforcontextsynthtesting" in open(".env","r").read(): os.remove(".env")
    print("\n--- ContextSynthesizerAgent Test Finished ---")

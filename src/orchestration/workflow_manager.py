from langgraph.graph import StateGraph, END
from typing import TypedDict, Any, List, Annotated, Dict, Optional
import operator
import os
import json
from dotenv import load_dotenv

# Agent Imports
from src.agents.narrative_pathfinder_agent import NarrativePathfinderAgent
from src.agents.world_weaver_agent import WorldWeaverAgent
from src.agents.plot_architect_agent import PlotArchitectAgent
from src.agents.character_sculptor_agent import CharacterSculptorAgent
from src.agents.lore_keeper_agent import LoreKeeperAgent
from src.agents.context_synthesizer_agent import ContextSynthesizerAgent
from src.agents.chapter_chronicler_agent import ChapterChroniclerAgent
from src.agents.quality_guardian_agent import QualityGuardianAgent # Import added

# Persistence and Core Models
from src.persistence.database_manager import DatabaseManager
from src.core.models import PlotChapterDetail, Plot, Character, Chapter, Outline, WorldView, Novel, WorldviewDetail

# --- State Definition ---
class UserInput(TypedDict):
    theme: str
    style_preferences: Optional[str]

class NovelWorkflowState(TypedDict):
    user_input: UserInput
    error_message: Optional[str]
    history: Annotated[List[str], operator.add]
    novel_id: Optional[int]
    novel_data: Optional[Novel]
    narrative_outline_text: Optional[str]
    all_generated_outlines: Optional[List[str]]
    outline_id: Optional[int]
    outline_data: Optional[Outline]
    outline_review: Optional[Dict[str, Any]] # New field for review
    all_generated_worldviews: Optional[List[WorldviewDetail]]
    selected_worldview_detail: Optional[WorldviewDetail]
    worldview_id: Optional[int]
    worldview_data: Optional[WorldView]
    plot_id: Optional[int]
    detailed_plot_data: Optional[List[PlotChapterDetail]]
    plot_data: Optional[Plot]
    characters: Optional[List[Character]] # This will become List[DetailedCharacterProfile] after CharacterSculptor update
    lore_keeper_initialized: bool
    current_chapter_number: int
    total_chapters_to_generate: int
    generated_chapters: List[Chapter]
    active_character_ids_for_chapter: Optional[List[int]]
    current_chapter_plot_summary: Optional[str]
    chapter_brief: Optional[str]

# --- Node Functions ---
def _log_and_update_history(current_history: List[str], message: str, error: bool = False) -> List[str]:
    updated_history = current_history + [message]
    if error: print(f"Error: {message}")
    else: print(message)
    return updated_history

def execute_narrative_pathfinder_agent(state: NovelWorkflowState) -> Dict[str, Any]:
    history = _log_and_update_history(state.get("history", []), "Executing Node: Narrative Pathfinder Agent")
    try:
        user_input = state["user_input"]
        num_outlines_to_generate = 2
        history = _log_and_update_history(history, f"Calling NarrativePathfinderAgent for {num_outlines_to_generate} outlines for theme: '{user_input['theme']}'")
        agent = NarrativePathfinderAgent()
        all_outlines = agent.generate_outline(
            user_theme=user_input['theme'], style_preferences=user_input.get("style_preferences", "general fiction"),
            num_outlines=num_outlines_to_generate
        )
        if all_outlines:
            history = _log_and_update_history(history, f"Successfully generated {len(all_outlines)} outlines.")
            return {"all_generated_outlines": all_outlines, "history": history, "error_message": None}
        else:
            msg = "Narrative Pathfinder Agent returned no outlines."
            return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}
    except Exception as e:
        msg = f"Error in Narrative Pathfinder Agent node: {e}"
        return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}

def present_outlines_for_selection_cli(state: NovelWorkflowState) -> dict:
    history = _log_and_update_history(state.get("history", []), "Node: Present Outlines for Selection (CLI)")
    print("\n=== Outline Selection ===")
    all_outlines = state.get("all_generated_outlines")
    if not all_outlines:
        error_msg = "No outlines available for selection."
        return {"error_message": error_msg, "history": _log_and_update_history(history, error_msg, True)}
    for i, outline_text in enumerate(all_outlines):
        print(f"\n--- Outline {i + 1} ---\n{outline_text}\n--------------------")
    selected_index = 0
    try:
        choice_str = input(f"Please select an outline by number (1-{len(all_outlines)}) or type '0' to default to Outline 1: ")
        choice_int = int(choice_str)
        if 0 < choice_int <= len(all_outlines): selected_index = choice_int - 1
    except (ValueError, EOFError) as e: print(f"Invalid input or EOF ({e}), defaulting to Outline 1.")
    log_msg = f"User selected Outline {selected_index + 1}." if selected_index !=0 or (selected_index==0 and choice_int !=0) else "User defaulted or error occurred, selecting Outline 1."
    history = _log_and_update_history(history, log_msg)
    selected_outline_text = all_outlines[selected_index]
    print(f"Proceeding with Outline {selected_index + 1}.")
    return {"narrative_outline_text": selected_outline_text, "history": history, "error_message": None}

def persist_novel_record_node(state: NovelWorkflowState) -> Dict[str, Any]:
    history = _log_and_update_history(state.get("history", []), "Executing Node: Persist Novel Record")
    try:
        user_input = state["user_input"]
        db_manager = DatabaseManager()
        new_novel_id = db_manager.add_novel(user_theme=user_input["theme"], style_preferences=user_input.get("style_preferences", ""))
        novel_data = db_manager.get_novel_by_id(new_novel_id)
        history = _log_and_update_history(history, f"Novel record saved to DB with ID: {new_novel_id}.")
        return {"novel_id": new_novel_id, "novel_data": novel_data, "history": history, "error_message": None}
    except Exception as e:
        msg = f"Error in Persist Novel Record node: {e}"
        return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}

def persist_initial_outline_node(state: NovelWorkflowState) -> Dict[str, Any]:
    history = _log_and_update_history(state.get("history", []), "Executing Node: Persist Initial Outline")
    try:
        novel_id = state["novel_id"]
        outline_text_to_persist = state["narrative_outline_text"]
        if novel_id is None or outline_text_to_persist is None:
            msg = "Novel ID or selected outline text ('narrative_outline_text') missing for outline persistence."
            return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}
        db_manager = DatabaseManager()
        new_outline_id = db_manager.add_outline(novel_id=novel_id, overview_text=outline_text_to_persist)
        db_manager.update_novel_active_outline(novel_id, new_outline_id)
        outline_data = db_manager.get_outline_by_id(new_outline_id)
        history = _log_and_update_history(history, f"Initial (selected) outline saved with ID {new_outline_id} and linked to novel {novel_id}.")
        return {"outline_id": new_outline_id, "outline_data": outline_data, "history": history, "error_message": None}
    except Exception as e:
        msg = f"Error in Persist Initial Outline node: {e}"
        return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}

def execute_outline_quality_guardian(state: NovelWorkflowState) -> dict:
    history = _log_and_update_history(state.get("history", []), "Node: Execute Outline Quality Guardian")
    print("Executing Node: Outline Quality Guardian")
    selected_outline_text = state.get("narrative_outline_text")
    if not selected_outline_text:
        error_msg = "No selected outline available for review by Quality Guardian."
        history = _log_and_update_history(history, f"Error: {error_msg}")
        return {"history": history, "error_message": None, "outline_review": None}
    try:
        guardian_agent = QualityGuardianAgent()
        review = guardian_agent.review_outline(selected_outline_text)
        history = _log_and_update_history(history, "Outline review completed by Quality Guardian.")
        print("\n--- Outline Review by Quality Guardian ---")
        if review:
            for key, value in review.items(): print(f"  {key.replace('_', ' ').capitalize()}: {value}")
        else: print("  Quality Guardian Agent did not return a review.")
        print("----------------------------------------\n")
        return {"outline_review": review, "history": history, "error_message": None}
    except Exception as e:
        error_msg = f"Error during Quality Guardian outline review: {e}"
        history = _log_and_update_history(history, error_msg, True)
        print(f"Error in Outline Quality Guardian node: {e}")
        return {"history": history, "error_message": state.get("error_message"), "outline_review": None}

def execute_world_weaver_agent(state: NovelWorkflowState) -> Dict[str, Any]:
    history = _log_and_update_history(state.get("history", []), "Executing Node: World Weaver Agent")
    try:
        outline_text_for_worldview = state["narrative_outline_text"]
        if not outline_text_for_worldview:
            msg = "Selected narrative outline text is required for World Weaver Agent."
            return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}
        num_worldviews_to_generate = 2
        history = _log_and_update_history(history, f"Calling WorldWeaverAgent for {num_worldviews_to_generate} worldviews based on: '{outline_text_for_worldview[:50]}...'")
        agent = WorldWeaverAgent()
        all_worldviews = agent.generate_worldview(
            narrative_outline=outline_text_for_worldview, num_worldviews=num_worldviews_to_generate
        )
        if all_worldviews:
            history = _log_and_update_history(history, f"Successfully generated {len(all_worldviews)} worldviews.")
            return {"all_generated_worldviews": all_worldviews, "history": history, "error_message": None}
        else:
            msg = "World Weaver Agent returned no worldviews."
            return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}
    except Exception as e:
        msg = f"Error in World Weaver Agent node: {e}"
        return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}

def present_worldviews_for_selection_cli(state: NovelWorkflowState) -> dict:
    history = _log_and_update_history(state.get("history", []), "Node: Present Worldviews for Selection (CLI)")
    print("\n=== Worldview Selection ===")
    all_worldviews = state.get("all_generated_worldviews")
    if not all_worldviews:
        error_msg = "No worldviews available for selection."
        return {"error_message": error_msg, "history": _log_and_update_history(history, error_msg, True)}
    for i, wv_detail in enumerate(all_worldviews):
        print(f"\n--- Worldview Option {i + 1} ---")
        print(f"  Name: {wv_detail.get('world_name', 'N/A')}")
        print(f"  Core Concept: {wv_detail.get('core_concept', 'N/A')}")
        print(f"  Key Elements: {', '.join(wv_detail.get('key_elements') or [])}")
        print(f"  Atmosphere: {wv_detail.get('atmosphere', 'N/A')}")
        print("--------------------")
    selected_index = 0
    try:
        choice_str = input(f"Please select a worldview by number (1-{len(all_worldviews)}) or type '0' to default to Option 1: ")
        choice_int = int(choice_str)
        if 0 < choice_int <= len(all_worldviews): selected_index = choice_int - 1
    except (ValueError, EOFError) as e: print(f"Invalid input or EOF ({e}), defaulting to Worldview 1.")
    log_msg = f"User selected Worldview {selected_index + 1}." if selected_index !=0 or (selected_index==0 and choice_int !=0) else "User defaulted or error, selecting Worldview 1."
    history = _log_and_update_history(history, log_msg)
    selected_wv_detail = all_worldviews[selected_index]
    print(f"Proceeding with Worldview {selected_index + 1} ('{selected_wv_detail.get('world_name', 'N/A')}')")
    return {"selected_worldview_detail": selected_wv_detail, "history": history, "error_message": None}

def persist_worldview_node(state: NovelWorkflowState) -> Dict[str, Any]:
    history = _log_and_update_history(state.get("history", []), "Executing Node: Persist Worldview")
    try:
        novel_id = state["novel_id"]
        selected_wv_detail = state.get("selected_worldview_detail")
        if novel_id is None or selected_wv_detail is None:
            msg = "Novel ID or selected worldview detail missing for worldview persistence."
            return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}
        description_to_save = selected_wv_detail.get('core_concept', 'Worldview description not available.')
        if not description_to_save and selected_wv_detail.get('raw_llm_output_for_worldview'):
            description_to_save = "Raw: " + selected_wv_detail['raw_llm_output_for_worldview']
        db_manager = DatabaseManager()
        new_worldview_id = db_manager.add_worldview(novel_id=novel_id, description_text=description_to_save)
        db_manager.update_novel_active_worldview(novel_id, new_worldview_id)
        worldview_data_from_db = db_manager.get_worldview_by_id(new_worldview_id)
        history = _log_and_update_history(history, f"Selected worldview (concept: '{description_to_save[:50]}...') saved with ID {new_worldview_id} and linked to novel {novel_id}.")
        return {"worldview_id": new_worldview_id, "worldview_data": worldview_data_from_db, "history": history, "error_message": None}
    except Exception as e:
        msg = f"Error in Persist Worldview node: {e}"
        return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}

def execute_plot_architect_agent(state: NovelWorkflowState) -> Dict[str, Any]:
    history = _log_and_update_history(state.get("history", []), "Executing Node: Plot Architect Agent")
    try:
        outline_text_for_plot = state["narrative_outline_text"]
        selected_worldview = state.get("selected_worldview_detail")
        if not outline_text_for_plot or not selected_worldview:
            msg = "Selected outline text or selected worldview detail is required for Plot Architect Agent."
            return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}
        worldview_text_for_plot = selected_worldview.get('core_concept', '')
        if not worldview_text_for_plot and selected_worldview.get('raw_llm_output_for_worldview'):
            worldview_text_for_plot = selected_worldview['raw_llm_output_for_worldview']
        num_chapters_for_plot = state.get("total_chapters_to_generate", 3)
        history = _log_and_update_history(history, f"Calling PlotArchitectAgent for {num_chapters_for_plot} detailed chapter structures.")
        agent = PlotArchitectAgent()
        detailed_plot_data_list = agent.generate_plot_points(
            narrative_outline=outline_text_for_plot, worldview_data=worldview_text_for_plot, num_chapters=num_chapters_for_plot
        )
        if detailed_plot_data_list:
            history = _log_and_update_history(history, f"PlotArchitectAgent generated {len(detailed_plot_data_list)} detailed chapter plots.")
            return {"detailed_plot_data": detailed_plot_data_list, "history": history, "error_message": None}
        else:
            msg = "Plot Architect Agent returned no detailed chapter plots."
            return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}
    except Exception as e:
        msg = f"Error in Plot Architect Agent node: {e}"
        return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}

def persist_plot_node(state: NovelWorkflowState) -> Dict[str, Any]:
    history = _log_and_update_history(state.get("history", []), "Executing Node: Persist Plot")
    try:
        novel_id = state["novel_id"]
        detailed_plot = state.get("detailed_plot_data")
        if novel_id is None or not detailed_plot:
            msg = "Novel ID or detailed plot data missing for plot persistence."
            return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}
        db_manager = DatabaseManager()
        plot_summary_json = json.dumps(detailed_plot)
        new_plot_id = db_manager.add_plot(novel_id=novel_id, plot_summary=plot_summary_json)
        db_manager.update_novel_active_plot(novel_id, new_plot_id)
        plot_data_from_db = db_manager.get_plot_by_id(new_plot_id)
        history = _log_and_update_history(history, f"Detailed plot (as JSON) saved with ID {new_plot_id} and linked to novel {novel_id}.")
        return {"plot_id": new_plot_id, "plot_data": plot_data_from_db, "history": history, "error_message": None}
    except Exception as e:
        msg = f"Error in Persist Plot node: {e}"
        return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}

def execute_character_sculptor_agent(state: NovelWorkflowState) -> Dict[str, Any]:
    history = _log_and_update_history(state.get("history", []), "Executing Node: Character Sculptor Agent")
    try:
        novel_id = state["novel_id"]
        outline = state["outline_data"]
        selected_worldview = state.get("selected_worldview_detail")
        detailed_plot = state.get("detailed_plot_data")
        if not all([novel_id, outline, selected_worldview, detailed_plot]):
            msg = "Novel ID, outline data, selected worldview detail, or detailed plot data missing for Character Sculptor."
            return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}
        worldview_text_for_chars = selected_worldview.get('core_concept', "General worldview.")
        plot_summary_for_chars = "; ".join(
            [f"Ch{d.get('chapter_number')}: {d.get('key_events_and_plot_progression', d.get('core_scene_summary', ''))}" for d in detailed_plot]
        )
        if not plot_summary_for_chars: plot_summary_for_chars = "Overall plot not yet detailed."
        # For MVP, let's define concepts here or pass them in user_input.
        character_concepts = ["the main protagonist", "a compelling antagonist"] # Example concepts
        history = _log_and_update_history(history, f"Generating characters for concepts: {character_concepts}")
        agent = CharacterSculptorAgent()
        # The CharacterSculptorAgent now returns List[DetailedCharacterProfile]
        characters_profiles = agent.generate_and_save_characters(
            novel_id=novel_id, narrative_outline=outline['overview_text'],
            worldview_data_core_concept=worldview_text_for_chars, plot_summary_str=plot_summary_for_chars,
            character_concepts=character_concepts
        )
        if characters_profiles: # Check if list is not empty
            history = _log_and_update_history(history, f"Generated and saved {len(characters_profiles)} detailed character profiles.")
            # The 'characters' field in state should now hold List[DetailedCharacterProfile]
            return {"characters": characters_profiles, "history": history, "error_message": None}
        else:
            msg = "Character Sculptor Agent failed to generate characters."
            return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}
    except Exception as e:
        msg = f"Error in Character Sculptor Agent node: {e}"
        return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}

def execute_lore_keeper_initialize(state: NovelWorkflowState) -> Dict[str, Any]:
    history = _log_and_update_history(state.get("history", []), "Executing Node: Lore Keeper Initialize")
    try:
        novel_id = state["novel_id"]
        outline = state["outline_data"]
        worldview_db_object = state["worldview_data"]
        plot_db_object = state.get("plot_data")
        if not plot_db_object and state.get("plot_id"):
            db_manager = DatabaseManager()
            plot_db_object = db_manager.get_plot_by_id(state["plot_id"])

        # characters state now holds List[DetailedCharacterProfile]
        # LoreKeeperAgent's initialize_knowledge_base expects List[Character] (the DB model)
        # We need to adapt this. For now, we can create basic Character objects for KB init
        # or update LoreKeeperAgent to handle DetailedCharacterProfile.
        # For this step, let's pass the detailed profiles, assuming LoreKeeper can extract name/role/description.
        character_details_for_kb = state["characters"]

        if not all([novel_id, outline, worldview_db_object, plot_db_object, character_details_for_kb is not None]):
            msg = "Missing data for Lore Keeper initialization."
            return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}

        lore_keeper = LoreKeeperAgent(db_name="novel_mvp.db")
        # TODO: Adapt LoreKeeperAgent to handle List[DetailedCharacterProfile] if its initialize_knowledge_base expects List[Character]
        # For now, assuming it can work with the richer structure or a transformation happens inside.
        # If initialize_knowledge_base strictly needs List[Character], we'd convert here:
        # temp_characters_for_kb = [Character(id=dp['character_id'], novel_id=dp['novel_id'], name=dp['name'], description="See detailed profile.", role_in_story=dp['role_in_story'], creation_date=dp['creation_date']) for dp in character_details_for_kb]
        # lore_keeper.initialize_knowledge_base(novel_id, outline, worldview_db_object, plot_db_object, temp_characters_for_kb)

        # Assuming LoreKeeperAgent.initialize_knowledge_base is adapted to use DetailedCharacterProfile
        # or extracts necessary info from it. This might require changes in LoreKeeperAgent.
        # For now, we'll pass the detailed profiles.
        lore_keeper.initialize_knowledge_base(novel_id, outline, worldview_db_object, plot_db_object, character_details_for_kb) # type: ignore

        history = _log_and_update_history(history, "Lore Keeper knowledge base initialized.")
        return {"lore_keeper_initialized": True, "history": history, "error_message": None}
    except Exception as e:
        msg = f"Error in Lore Keeper Initialize node: {e}"
        return {"error_message": msg, "history": _log_and_update_history(history, msg, True), "lore_keeper_initialized": False}

def prepare_for_chapter_loop(state: NovelWorkflowState) -> Dict[str, Any]:
    history = _log_and_update_history(state.get("history", []), "Executing Node: Prepare for Chapter Loop")
    detailed_plot = state.get("detailed_plot_data")
    if not detailed_plot:
        msg = "Detailed plot data not found, cannot determine total chapters for loop."
        return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}
    total_chapters = len(detailed_plot)
    if total_chapters == 0:
        total_chapters = 3
        history = _log_and_update_history(history, f"Warning: detailed_plot_data list is empty. Defaulting to {total_chapters} chapters.")
    history = _log_and_update_history(history, f"Preparing for chapter loop. Total chapters to generate: {total_chapters}")
    return {
        "current_chapter_number": 1, "generated_chapters": [], "total_chapters_to_generate": total_chapters,
        "history": history, "error_message": None
    }

def execute_context_synthesizer_agent(state: NovelWorkflowState) -> Dict[str, Any]:
    current_chapter_num = state['current_chapter_number']
    history = _log_and_update_history(state.get("history", []), f"Executing Node: Context Synthesizer for Chapter {current_chapter_num}")
    try:
        novel_id = state["novel_id"]
        detailed_plot = state.get("detailed_plot_data")
        # characters state now holds List[DetailedCharacterProfile]
        character_profiles = state.get("characters", [])

        if not all([novel_id is not None, detailed_plot, character_profiles is not None]):
            msg = "Missing data for Context Synthesizer (novel_id, detailed_plot_data, characters)."
            return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}
        if not (0 < current_chapter_num <= len(detailed_plot)):
            msg = f"Invalid current_chapter_number {current_chapter_num} for {len(detailed_plot)} detailed plot entries."
            return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}

        current_chapter_detail: PlotChapterDetail = detailed_plot[current_chapter_num - 1]
        brief_plot_summary = current_chapter_detail.get('key_events_and_plot_progression') or \
                             current_chapter_detail.get('core_scene_summary') or \
                             f"Plot for Chapter {current_chapter_num} needs to be developed based on title: {current_chapter_detail.get('title', 'N/A')}."

        # Pass IDs of characters present in the current chapter's plot details, if available
        # Otherwise, default to first few characters from the main list.
        active_char_names_from_plot = current_chapter_detail.get("characters_present", [])
        active_char_ids: List[int] = []
        if active_char_names_from_plot:
            for char_prof in character_profiles:
                if char_prof.get("name") in active_char_names_from_plot:
                    if char_prof.get("character_id") is not None:
                         active_char_ids.append(char_prof["character_id"]) # type: ignore
        else: # Fallback if not specified in plot
            active_char_ids = [cp.get('character_id') for cp in character_profiles[:2] if cp.get('character_id') is not None] # type: ignore

        context_agent = ContextSynthesizerAgent(db_name="novel_mvp.db")
        chapter_brief_text = context_agent.generate_chapter_brief(
            novel_id, current_chapter_num, brief_plot_summary, active_char_ids
        )
        history = _log_and_update_history(history, f"Chapter brief generated for Chapter {current_chapter_num}.")
        return {
            "chapter_brief": chapter_brief_text, "current_chapter_plot_summary": brief_plot_summary,
            "history": history, "error_message": None
        }
    except Exception as e:
        msg = f"Error in Context Synthesizer node for Chapter {current_chapter_num}: {e}"
        return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}

def execute_chapter_chronicler_agent(state: NovelWorkflowState) -> Dict[str, Any]:
    current_chapter_num = state['current_chapter_number']
    history = _log_and_update_history(state.get("history", []), f"Executing Node: Chapter Chronicler for Chapter {current_chapter_num}")
    try:
        novel_id = state["novel_id"]
        chapter_brief = state["chapter_brief"]
        current_plot_for_chapter = state["current_chapter_plot_summary"]
        style_prefs = state["user_input"].get("style_preferences", "general fiction")
        if not all([novel_id is not None, chapter_brief, current_plot_for_chapter]):
            msg = "Missing data for Chapter Chronicler."
            return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}
        chronicler_agent = ChapterChroniclerAgent(db_name="novel_mvp.db")
        new_chapter = chronicler_agent.generate_and_save_chapter(
            novel_id, current_chapter_num, chapter_brief, current_plot_for_chapter, style_prefs
        )
        if new_chapter:
            updated_generated_chapters = state.get("generated_chapters", []) + [new_chapter]
            history = _log_and_update_history(history, f"Chapter {current_chapter_num} generated and saved.")
            return {"generated_chapters": updated_generated_chapters, "history": history, "error_message": None}
        else:
            msg = f"Chapter Chronicler failed to generate Chapter {current_chapter_num}."
            return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}
    except Exception as e:
        msg = f"Error in Chapter Chronicler node for Chapter {current_chapter_num}: {e}"
        return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}

def execute_lore_keeper_update_kb(state: NovelWorkflowState) -> Dict[str, Any]:
    current_chapter_num = state['current_chapter_number']
    history = _log_and_update_history(state.get("history", []), f"Executing Node: Lore Keeper Update KB for Chapter {current_chapter_num}")
    try:
        novel_id = state["novel_id"]
        generated_chapters = state.get("generated_chapters", [])
        if novel_id is None or not generated_chapters:
            msg = "Novel ID or generated chapters missing for Lore Keeper KB update."
            return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}
        last_chapter = generated_chapters[-1]
        lore_keeper = LoreKeeperAgent(db_name="novel_mvp.db")
        lore_keeper.update_knowledge_base_with_chapter(novel_id, last_chapter)
        history = _log_and_update_history(history, f"Lore Keeper KB updated with Chapter {last_chapter['chapter_number']}.")
        return {"history": history, "error_message": None}
    except Exception as e:
        msg = f"Error in Lore Keeper Update KB node for Chapter {current_chapter_num}: {e}"
        return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}

def increment_chapter_number(state: NovelWorkflowState) -> Dict[str, Any]:
    current_num = state.get("current_chapter_number", 0)
    new_num = current_num + 1
    history = _log_and_update_history(state.get("history", []), f"Incrementing chapter number from {current_num} to {new_num}")
    return {"current_chapter_number": new_num, "history": history, "error_message": None}

def _check_node_output(state: NovelWorkflowState) -> str:
    if state.get("error_message"):
        print(f"Error detected in previous node. Routing to END. Error: {state.get('error_message')}")
        return "stop_on_error"
    else:
        print("Previous node successful. Routing to continue.")
        return "continue"

def _should_continue_chapter_loop(state: NovelWorkflowState) -> str:
    if state.get("error_message"):
        print(f"Error detected before loop condition. Routing to END. Error: {state.get('error_message')}")
        return "end_loop_on_error"
    current_chapter = state.get("current_chapter_number", 1)
    total_chapters = state.get("total_chapters_to_generate", 0)
    if current_chapter <= total_chapters:
        print(f"Chapter loop: {current_chapter}/{total_chapters}. Continuing loop.")
        return "continue_loop"
    else:
        print(f"Chapter loop: {current_chapter}/{total_chapters}. Ending loop.")
        return "end_loop"

class WorkflowManager:
    def __init__(self, db_name="novel_mvp.db"):
        self.db_name = db_name
        self.workflow = StateGraph(NovelWorkflowState)
        self._build_graph()
        self.app = self.workflow.compile()
        print(f"WorkflowManager initialized (DB: {self.db_name}) and graph compiled.")
        self.initial_history = [f"WorkflowManager initialized (DB: {self.db_name}) and graph compiled."]

    def _build_graph(self):
        self.workflow.add_node("narrative_pathfinder", execute_narrative_pathfinder_agent)
        self.workflow.add_node("present_outlines_cli", present_outlines_for_selection_cli)
        self.workflow.add_node("persist_novel_record", persist_novel_record_node)
        self.workflow.add_node("persist_initial_outline", persist_initial_outline_node)
        self.workflow.add_node("outline_quality_guardian", execute_outline_quality_guardian) # New node
        self.workflow.add_node("world_weaver", execute_world_weaver_agent)
        self.workflow.add_node("present_worldviews_cli", present_worldviews_for_selection_cli)
        self.workflow.add_node("persist_worldview", persist_worldview_node)
        self.workflow.add_node("plot_architect", execute_plot_architect_agent)
        self.workflow.add_node("persist_plot", persist_plot_node)
        self.workflow.add_node("character_sculptor", execute_character_sculptor_agent)
        self.workflow.add_node("lore_keeper_initialize", execute_lore_keeper_initialize)
        self.workflow.add_node("prepare_for_chapter_loop", prepare_for_chapter_loop)
        self.workflow.add_node("context_synthesizer", execute_context_synthesizer_agent)
        self.workflow.add_node("chapter_chronicler", execute_chapter_chronicler_agent)
        self.workflow.add_node("lore_keeper_update_kb", execute_lore_keeper_update_kb)
        self.workflow.add_node("increment_chapter_number", increment_chapter_number)

        self.workflow.set_entry_point("narrative_pathfinder")
        self.workflow.add_conditional_edges("narrative_pathfinder", _check_node_output, {"continue": "present_outlines_cli", "stop_on_error": END})
        self.workflow.add_conditional_edges("present_outlines_cli", _check_node_output, {"continue": "persist_novel_record", "stop_on_error": END})
        self.workflow.add_conditional_edges("persist_novel_record", _check_node_output, {"continue": "persist_initial_outline", "stop_on_error": END})
        # Updated edges for Quality Guardian
        self.workflow.add_conditional_edges("persist_initial_outline", _check_node_output, {"continue": "outline_quality_guardian", "stop_on_error": END})
        self.workflow.add_conditional_edges("outline_quality_guardian", _check_node_output, {"continue": "world_weaver", "stop_on_error": END})

        self.workflow.add_conditional_edges("world_weaver", _check_node_output, {"continue": "present_worldviews_cli", "stop_on_error": END})
        self.workflow.add_conditional_edges("present_worldviews_cli", _check_node_output, {"continue": "persist_worldview", "stop_on_error": END})
        self.workflow.add_conditional_edges("persist_worldview", _check_node_output, {"continue": "plot_architect", "stop_on_error": END})
        self.workflow.add_conditional_edges("plot_architect", _check_node_output, {"continue": "persist_plot", "stop_on_error": END})
        self.workflow.add_conditional_edges("persist_plot", _check_node_output, {"continue": "character_sculptor", "stop_on_error": END})
        self.workflow.add_conditional_edges("character_sculptor", _check_node_output, {"continue": "lore_keeper_initialize", "stop_on_error": END})
        self.workflow.add_conditional_edges("lore_keeper_initialize", _check_node_output, {"continue": "prepare_for_chapter_loop", "stop_on_error": END})
        self.workflow.add_conditional_edges("prepare_for_chapter_loop", _check_node_output, {"continue": "context_synthesizer", "stop_on_error": END})
        self.workflow.add_conditional_edges("context_synthesizer", _check_node_output, {"continue": "chapter_chronicler", "stop_on_error": END})
        self.workflow.add_conditional_edges("chapter_chronicler", _check_node_output, {"continue": "lore_keeper_update_kb", "stop_on_error": END})
        self.workflow.add_conditional_edges("lore_keeper_update_kb", _check_node_output, {"continue": "increment_chapter_number", "stop_on_error": END})
        self.workflow.add_conditional_edges(
            "increment_chapter_number", _should_continue_chapter_loop,
            {"continue_loop": "context_synthesizer", "end_loop": END, "end_loop_on_error": END }
        )
        print("Workflow graph built.")

    def run_workflow(self, user_input_data: Dict[str, Any]) -> NovelWorkflowState:
        current_history = list(self.initial_history)
        current_history.append(f"Starting workflow with input: {user_input_data}")
        print(f"Starting workflow with input: {user_input_data}")
        initial_state = NovelWorkflowState(
            user_input=UserInput(
                theme=user_input_data.get("theme","A default theme if none provided"),
                style_preferences=user_input_data.get("style_preferences")
            ),
            error_message=None, history=current_history,
            novel_id=None, novel_data=None,
            narrative_outline_text=None, all_generated_outlines=None,
            outline_id=None, outline_data=None, outline_review=None, # Added outline_review
            all_generated_worldviews=None, selected_worldview_detail=None,
            worldview_id=None, worldview_data=None,
            plot_id=None, detailed_plot_data=None, plot_data=None,
            characters=None, lore_keeper_initialized=False,
            current_chapter_number=0,
            total_chapters_to_generate=3,
            generated_chapters=[],
            active_character_ids_for_chapter=None,
            current_chapter_plot_summary=None, chapter_brief=None
        )
        final_state = self.app.invoke(initial_state, {"recursion_limit": 50})
        if final_state.get('error_message'):
             print(f"Workflow error: {final_state.get('error_message')}")
        return final_state

if __name__ == "__main__":
    print("--- Workflow Manager Full Integration Test ---")
    if not os.path.exists(".env") and not os.getenv("OPENAI_API_KEY"):
        print("Creating a dummy .env file for WorkflowManager test (for LLMClient dependent agents)...")
        with open(".env", "w") as f:
            f.write("OPENAI_API_KEY=\"sk-dummykeyforworkflowmanagertest\"\n")
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        print("CRITICAL: OPENAI_API_KEY not found. Some agents will fail to initialize.")
    elif "dummykey" in os.getenv("OPENAI_API_KEY","").lower():
        print("INFO: Using a DUMMY OPENAI_API_KEY. Real LLM calls will likely fail or be handled by agent mocks if any.")
    else:
        print("INFO: A potentially valid OPENAI_API_KEY is set. Attempting live LLM calls.")

    default_db_name = "novel_workflow_test.db"
    default_chroma_dir = "./novel_workflow_chroma_db"
    import shutil
    if os.path.exists(default_db_name): os.remove(default_db_name)
    if os.path.exists(default_chroma_dir): shutil.rmtree(default_chroma_dir)
    _ = DatabaseManager(db_name=default_db_name)
    manager = WorkflowManager(db_name=default_db_name)
    sample_user_input = {
        "theme": "a detective investigating anomalies in a city where time flows differently in various districts",
        "style_preferences": "chronopunk mystery with noir elements"
    }
    print(f"\nRunning workflow with: {sample_user_input}")
    final_result_state = manager.run_workflow(sample_user_input)
    print("\n--- Workflow Final State ---")
    for key, value in final_result_state.items():
        if key == "history": print(f"History entries: {len(value)}")
        elif key == "outline_review" and value: # Added to print outline_review
            print("Outline_review:")
            if isinstance(value, dict):
                for r_key, r_value in value.items(): print(f"  {r_key.replace('_',' ').capitalize()}: {r_value}")
            else: print(f"  {value}")
        elif key in ["all_generated_outlines", "all_generated_worldviews", "detailed_plot_data", "generated_chapters", "characters"] and isinstance(value, list):
            print(f"{key.replace('_', ' ').capitalize()}: ({len(value)} items)")
            if value and isinstance(value[0], dict):
                for i, item_dict in enumerate(value):
                    item_summary = item_dict.get('title', item_dict.get('name', f"Item {i+1}"))
                    print(f"  - {item_summary} (details in full state if needed)")
            elif value and isinstance(value[0], str):
                 for i, item_str in enumerate(value): print(f"  - Outline {i+1} Snippet: {item_str[:70]}...")
        elif isinstance(value, dict):
            print(f"{key.capitalize()}:")
            for k_item, v_item in value.items(): print(f"  {k_item}: {str(v_item)[:100]}{'...' if len(str(v_item)) > 100 else ''}")
        else:
            print(f"{key.capitalize()}: {str(value)[:200]}{'...' if len(str(value)) > 200 else ''}")
    print(f"\nError Message at end of workflow: {final_result_state.get('error_message')}")
    if os.path.exists(default_db_name): os.remove(default_db_name)
    if os.path.exists(default_chroma_dir): shutil.rmtree(default_chroma_dir)
    if os.path.exists(".env"):
        with open(".env", "r") as f_env:
            if "dummykeyforworkflowmanagertest" in f_env.read(): os.remove(".env")
    print("\n--- Workflow Manager Full Integration Test Finished ---")

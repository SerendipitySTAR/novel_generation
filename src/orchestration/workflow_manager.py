from langgraph.graph import StateGraph, END
from typing import TypedDict, Any, List, Annotated, Dict, Optional
import operator
import os
from dotenv import load_dotenv

# Agent Imports
from src.agents.narrative_pathfinder_agent import NarrativePathfinderAgent
from src.agents.world_weaver_agent import WorldWeaverAgent
from src.agents.plot_architect_agent import PlotArchitectAgent
from src.agents.character_sculptor_agent import CharacterSculptorAgent
from src.agents.lore_keeper_agent import LoreKeeperAgent
from src.agents.context_synthesizer_agent import ContextSynthesizerAgent
from src.agents.chapter_chronicler_agent import ChapterChroniclerAgent

# Persistence and Core Models
from src.persistence.database_manager import DatabaseManager
from src.core.models import Plot, Character, Chapter, Outline, WorldView, Novel

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
    narrative_outline_text: Optional[str] # This will store the SELECTED outline text
    all_generated_outlines: Optional[List[str]] # To store all outlines from pathfinder
    outline_id: Optional[int]
    outline_data: Optional[Outline]
    worldview_text: Optional[str]
    worldview_id: Optional[int]
    worldview_data: Optional[WorldView]
    plot_id: Optional[int]
    plot_data: Optional[Plot]
    plot_chapter_summaries: Optional[List[str]]
    characters: Optional[List[Character]]
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
    if error:
        print(f"Error: {message}")
    else:
        print(message)
    return updated_history

def execute_narrative_pathfinder_agent(state: NovelWorkflowState) -> Dict[str, Any]:
    history = _log_and_update_history(state.get("history", []), "Executing Node: Narrative Pathfinder Agent")
    try:
        user_input = state["user_input"]
        theme = user_input["theme"]
        style = user_input.get("style_preferences", "general fiction")
        num_outlines_to_generate = 2 # For MVP, let's generate 2 options
        history = _log_and_update_history(history, f"Calling NarrativePathfinderAgent for {num_outlines_to_generate} outlines for theme: '{theme}'")

        agent = NarrativePathfinderAgent()
        all_outlines = agent.generate_outline(
            user_theme=theme,
            style_preferences=style,
            num_outlines=num_outlines_to_generate
        )

        if all_outlines:
            selected_outline = all_outlines[0] # Select the first outline to proceed
            history = _log_and_update_history(history, f"Successfully generated {len(all_outlines)} outlines. Selected the first one to proceed.")
            return {
                "all_generated_outlines": all_outlines,
                "narrative_outline_text": selected_outline, # This key is used by downstream nodes
                "history": history,
                "error_message": None
            }
        else:
            msg = "Narrative Pathfinder Agent returned no outlines."
            return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}
    except Exception as e:
        msg = f"Error in Narrative Pathfinder Agent node: {e}"
        return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}

def persist_novel_record_node(state: NovelWorkflowState) -> Dict[str, Any]:
    history = _log_and_update_history(state.get("history", []), "Executing Node: Persist Novel Record")
    try:
        user_input = state["user_input"]
        db_manager = DatabaseManager()
        theme = user_input["theme"]
        style = user_input.get("style_preferences", "")

        new_novel_id = db_manager.add_novel(user_theme=theme, style_preferences=style)
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
        # Use 'narrative_outline_text' which holds the selected outline
        outline_text_to_persist = state["narrative_outline_text"]
        if novel_id is None or outline_text_to_persist is None:
            msg = "Novel ID or selected outline text missing for outline persistence."
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

def execute_world_weaver_agent(state: NovelWorkflowState) -> Dict[str, Any]:
    history = _log_and_update_history(state.get("history", []), "Executing Node: World Weaver Agent")
    try:
        # World Weaver uses the selected outline text
        outline_text_for_worldview = state["narrative_outline_text"]
        if not outline_text_for_worldview:
            msg = "Selected narrative outline text is required for World Weaver Agent."
            return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}
        history = _log_and_update_history(history, f"Calling WorldWeaverAgent with selected outline: '{outline_text_for_worldview[:50]}...'")

        agent = WorldWeaverAgent()
        worldview_text = agent.generate_worldview(narrative_outline=outline_text_for_worldview)

        if worldview_text:
            history = _log_and_update_history(history, "Successfully generated worldview text.")
            return {"worldview_text": worldview_text, "history": history, "error_message": None}
        else:
            msg = "World Weaver Agent returned empty worldview data."
            return {"worldview_text": None, "error_message": msg, "history": _log_and_update_history(history, msg, True)}
    except Exception as e:
        msg = f"Error in World Weaver Agent node: {e}"
        return {"worldview_text": None, "error_message": msg, "history": _log_and_update_history(history, msg, True)}

def persist_worldview_node(state: NovelWorkflowState) -> Dict[str, Any]:
    history = _log_and_update_history(state.get("history", []), "Executing Node: Persist Worldview")
    try:
        novel_id = state["novel_id"]
        worldview_text = state["worldview_text"]
        if novel_id is None or worldview_text is None:
            msg = "Novel ID or worldview text missing for worldview persistence."
            return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}

        db_manager = DatabaseManager()
        new_worldview_id = db_manager.add_worldview(novel_id=novel_id, description_text=worldview_text)
        db_manager.update_novel_active_worldview(novel_id, new_worldview_id)
        worldview_data = db_manager.get_worldview_by_id(new_worldview_id)

        history = _log_and_update_history(history, f"Worldview saved with ID {new_worldview_id} and linked to novel {novel_id}.")
        return {"worldview_id": new_worldview_id, "worldview_data": worldview_data, "history": history, "error_message": None}
    except Exception as e:
        msg = f"Error in Persist Worldview node: {e}"
        return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}

def execute_plot_architect_agent(state: NovelWorkflowState) -> Dict[str, Any]:
    history = _log_and_update_history(state.get("history", []), "Executing Node: Plot Architect Agent")
    try:
        # Plot Architect uses the selected outline and generated worldview text
        outline_text_for_plot = state["narrative_outline_text"]
        worldview_text_for_plot = state["worldview_text"]
        # Default to 3 chapters if not otherwise set.
        # This value might be refined based on outline length or user input in future versions.
        num_chapters_for_plot = state.get("total_chapters_to_generate", 3)


        if not outline_text_for_plot or not worldview_text_for_plot:
            msg = "Selected outline and worldview text are required for Plot Architect Agent."
            return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}

        history = _log_and_update_history(history, f"Calling PlotArchitectAgent for {num_chapters_for_plot} chapters.")
        agent = PlotArchitectAgent()
        plot_chapter_summaries = agent.generate_plot_points(
            narrative_outline=outline_text_for_plot,
            worldview_data=worldview_text_for_plot,
            num_chapters=num_chapters_for_plot
        )

        if plot_chapter_summaries:
            history = _log_and_update_history(history, f"PlotArchitectAgent generated {len(plot_chapter_summaries)} chapter plot summaries.")
            return {"plot_chapter_summaries": plot_chapter_summaries, "history": history, "error_message": None}
        else:
            msg = "Plot Architect Agent returned no chapter summaries."
            return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}
    except Exception as e:
        msg = f"Error in Plot Architect Agent node: {e}"
        return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}

def persist_plot_node(state: NovelWorkflowState) -> Dict[str, Any]:
    history = _log_and_update_history(state.get("history", []), "Executing Node: Persist Plot")
    try:
        novel_id = state["novel_id"]
        plot_chapter_summaries = state["plot_chapter_summaries"]
        if novel_id is None or not plot_chapter_summaries:
            msg = "Novel ID or plot chapter summaries missing for plot persistence."
            return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}

        db_manager = DatabaseManager()
        main_plot_summary_text = "\n\n".join(plot_chapter_summaries) # Join with double newline for readability

        new_plot_id = db_manager.add_plot(novel_id=novel_id, plot_summary=main_plot_summary_text)
        db_manager.update_novel_active_plot(novel_id, new_plot_id)
        plot_data_obj = db_manager.get_plot_by_id(new_plot_id) # Renamed to avoid conflict

        history = _log_and_update_history(history, f"Plot saved with ID {new_plot_id} and linked to novel {novel_id}.")
        return {"plot_id": new_plot_id, "plot_data": plot_data_obj, "history": history, "error_message": None}
    except Exception as e:
        msg = f"Error in Persist Plot node: {e}"
        return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}

def execute_character_sculptor_agent(state: NovelWorkflowState) -> Dict[str, Any]:
    history = _log_and_update_history(state.get("history", []), "Executing Node: Character Sculptor Agent")
    try:
        novel_id = state["novel_id"]
        # Use the full Outline, WorldView, Plot objects if available and preferred by agent
        # For now, using their text components as per previous agent implementations.
        outline = state["outline_data"]
        worldview = state["worldview_data"]
        plot = state["plot_data"] # This is the Plot object from persist_plot_node

        if not all([novel_id, outline, worldview, plot]):
            msg = "Novel ID, outline data, worldview data, or plot data missing for Character Sculptor."
            return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}

        agent = CharacterSculptorAgent()
        characters = agent.generate_and_save_characters(
            novel_id=novel_id,
            narrative_outline=outline['overview_text'], # From Outline TypedDict
            worldview_data=worldview['description_text'], # From WorldView TypedDict
            plot_summary=plot['plot_summary'], # From Plot TypedDict
            num_characters=2
        )
        if characters:
            history = _log_and_update_history(history, f"Generated and saved {len(characters)} characters.")
            return {"characters": characters, "history": history, "error_message": None}
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
        worldview = state["worldview_data"]
        plot = state["plot_data"]
        characters = state["characters"]

        if not all([novel_id, outline, worldview, plot, characters is not None]):
            msg = "Missing data for Lore Keeper initialization (novel_id, outline, worldview, plot, characters)."
            return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}

        lore_keeper = LoreKeeperAgent(db_name="novel_mvp.db")
        lore_keeper.initialize_knowledge_base(novel_id, outline, worldview, plot, characters)

        history = _log_and_update_history(history, "Lore Keeper knowledge base initialized.")
        return {"lore_keeper_initialized": True, "history": history, "error_message": None}
    except Exception as e:
        msg = f"Error in Lore Keeper Initialize node: {e}"
        return {"error_message": msg, "history": _log_and_update_history(history, msg, True), "lore_keeper_initialized": False}

def prepare_for_chapter_loop(state: NovelWorkflowState) -> Dict[str, Any]:
    history = _log_and_update_history(state.get("history", []), "Executing Node: Prepare for Chapter Loop")
    plot_summaries = state.get("plot_chapter_summaries")

    if not plot_summaries:
        msg = "Plot chapter summaries not found, cannot determine total chapters for loop."
        return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}

    total_chapters = len(plot_summaries)
    if total_chapters == 0:
        total_chapters = 3
        history = _log_and_update_history(history, f"Warning: plot_chapter_summaries list is empty. Defaulting to {total_chapters} chapters.")

    history = _log_and_update_history(history, f"Preparing for chapter loop. Total chapters to generate: {total_chapters}")
    return {
        "current_chapter_number": 1,
        "generated_chapters": [],
        "total_chapters_to_generate": total_chapters,
        "history": history,
        "error_message": None
    }

def execute_context_synthesizer_agent(state: NovelWorkflowState) -> Dict[str, Any]:
    current_chapter_num = state['current_chapter_number']
    history = _log_and_update_history(state.get("history", []), f"Executing Node: Context Synthesizer for Chapter {current_chapter_num}")
    try:
        novel_id = state["novel_id"]
        plot_summaries = state["plot_chapter_summaries"]
        characters = state["characters"]

        if not all([novel_id is not None, plot_summaries, characters is not None]):
            msg = "Missing data for Context Synthesizer (novel_id, plot_summaries, characters)."
            return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}

        if not (0 < current_chapter_num <= len(plot_summaries)):
            msg = f"Invalid current_chapter_number {current_chapter_num} for {len(plot_summaries)} plot summaries."
            return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}
        current_plot = plot_summaries[current_chapter_num - 1]

        active_char_ids: List[int] = [c['id'] for c in characters[:2]] if characters else []

        context_agent = ContextSynthesizerAgent(db_name="novel_mvp.db")
        chapter_brief_text = context_agent.generate_chapter_brief(
            novel_id, current_chapter_num, current_plot, active_char_ids
        )

        history = _log_and_update_history(history, f"Chapter brief generated for Chapter {current_chapter_num}.")
        return {
            "chapter_brief": chapter_brief_text,
            "current_chapter_plot_summary": current_plot,
            "history": history,
            "error_message": None
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
        current_plot = state["current_chapter_plot_summary"]
        style_prefs = state["user_input"].get("style_preferences", "general fiction")

        if not all([novel_id is not None, chapter_brief, current_plot]):
            msg = "Missing data for Chapter Chronicler (novel_id, brief, current_plot)."
            return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}

        chronicler_agent = ChapterChroniclerAgent(db_name="novel_mvp.db")
        new_chapter = chronicler_agent.generate_and_save_chapter(
            novel_id, current_chapter_num, chapter_brief, current_plot, style_prefs
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

# --- Conditional Edges ---
def _check_node_output(state: NovelWorkflowState) -> str:
    current_history = state.get("history", [])
    if state.get("error_message"):
        # This log will be part of the history of the *next* state if we return a new history object
        # However, LangGraph's state updates are based on the dictionary returned by the node.
        # The history is already updated by the node itself before returning.
        # So, just printing here is fine for real-time logging.
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

# --- Workflow Manager Class ---
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
        self.workflow.add_node("persist_novel_record", persist_novel_record_node)
        self.workflow.add_node("persist_initial_outline", persist_initial_outline_node)
        self.workflow.add_node("world_weaver", execute_world_weaver_agent)
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

        self.workflow.add_conditional_edges("narrative_pathfinder", _check_node_output, {"continue": "persist_novel_record", "stop_on_error": END})
        self.workflow.add_conditional_edges("persist_novel_record", _check_node_output, {"continue": "persist_initial_outline", "stop_on_error": END})
        self.workflow.add_conditional_edges("persist_initial_outline", _check_node_output, {"continue": "world_weaver", "stop_on_error": END})
        self.workflow.add_conditional_edges("world_weaver", _check_node_output, {"continue": "persist_worldview", "stop_on_error": END})
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
            "increment_chapter_number",
            _should_continue_chapter_loop,
            {
                "continue_loop": "context_synthesizer",
                "end_loop": END,
                "end_loop_on_error": END
            }
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
            error_message=None,
            history=current_history,
            novel_id=None, novel_data=None,
            narrative_outline_text=None,
            all_generated_outlines=None, # Initialize new field
            outline_id=None, outline_data=None,
            worldview_text=None, worldview_id=None, worldview_data=None,
            plot_id=None, plot_data=None, plot_chapter_summaries=None,
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
    elif "dummykeyforworkflowmanagertest" in os.getenv("OPENAI_API_KEY","") or \
         "dummyclikeyformainexecution" in os.getenv("OPENAI_API_KEY",""):
        print("INFO: Using a DUMMY OPENAI_API_KEY. Real LLM calls will fail.")
    else:
        print("INFO: A potentially valid OPENAI_API_KEY is set. Attempting live LLM calls.")


    default_db_name = "novel_workflow_test.db"
    default_chroma_dir = "./novel_workflow_chroma_db"

    import shutil
    if os.path.exists(default_db_name):
        os.remove(default_db_name)
        print(f"Removed existing test SQL DB: {default_db_name}")
    if os.path.exists(default_chroma_dir):
        shutil.rmtree(default_chroma_dir)
        print(f"Removed existing test Chroma DB directory: {default_chroma_dir}")

    _ = DatabaseManager(db_name=default_db_name)

    manager = WorkflowManager(db_name=default_db_name)

    sample_user_input = {
        "theme": "a space pirate captain searching for a legendary treasure on a lost planet",
        "style_preferences": "action-packed sci-fi with witty dialogue and detailed world-building"
    }
    print(f"\nRunning workflow with: {sample_user_input}")

    final_result_state = manager.run_workflow(sample_user_input)

    print("\n--- Workflow Final State ---")
    for key, value in final_result_state.items():
        if key == "history":
            print(f"History entries: {len(value)}")
        elif isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict):
             print(f"{key.capitalize()}: ({len(value)} items)")
             for i, item in enumerate(value):
                 print(f"  Item {i+1}:")
                 for k, v_item in item.items():
                     print(f"    {k}: {str(v_item)[:100]}{'...' if len(str(v_item)) > 100 else ''}")
        elif isinstance(value, dict):
            print(f"{key.capitalize()}:")
            for k, v_item in value.items():
                print(f"  {k}: {str(v_item)[:100]}{'...' if len(str(v_item)) > 100 else ''}")
        else:
            print(f"{key.capitalize()}: {str(value)[:200]}{'...' if len(str(value)) > 200 else ''}")

    print(f"\nError Message at end of workflow: {final_result_state.get('error_message')}")

    print("\nFinal History Log (Detailed):")
    for entry in final_result_state.get("history", []):
        print(f"  - {entry}")

    if final_result_state.get('novel_id') and not final_result_state.get('error_message'):
        print(f"\nVerifying data in database '{default_db_name}' for Novel ID {final_result_state['novel_id']}...")
        print("  DB verification (conceptual - implement checks as needed).")
    else:
        print("\nSkipping DB verification due to workflow error or no novel_id.")

    if os.path.exists(default_db_name):
        os.remove(default_db_name)
        print(f"\nCleaned up test SQL DB: {default_db_name}")
    if os.path.exists(default_chroma_dir):
        shutil.rmtree(default_chroma_dir)
        print(f"Cleaned up test Chroma DB directory: {default_chroma_dir}")
    if os.path.exists(".env"):
        with open(".env", "r") as f_env:
            if "dummykeyforworkflowmanagertest" in f_env.read():
                print("Removing dummy .env file for WorkflowManager test...")
                os.remove(".env")

    print("\n--- Workflow Manager Full Integration Test Finished ---")

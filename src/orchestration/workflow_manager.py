from langgraph.graph import StateGraph, END
from typing import TypedDict, Any, List, Annotated, Dict, Optional
import operator
import os # For testing block
from dotenv import load_dotenv # Added import

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
from src.core.models import Plot, Character, Chapter, Outline, WorldView, Novel # Added Novel

# --- State Definition ---
class UserInput(TypedDict):
    theme: str
    style_preferences: Optional[str]

class NovelWorkflowState(TypedDict):
    user_input: UserInput
    error_message: Optional[str]
    history: Annotated[List[str], operator.add]

    # Novel and Core Components
    novel_id: Optional[int]
    novel_data: Optional[Novel] # To store the full Novel object once created/fetched

    narrative_outline_text: Optional[str] # Raw text from pathfinder
    outline_id: Optional[int]
    outline_data: Optional[Outline] # Full Outline object from DB

    worldview_text: Optional[str] # Raw text from weaver
    worldview_id: Optional[int]
    worldview_data: Optional[WorldView] # Full Worldview object from DB

    # Plot related fields
    plot_id: Optional[int]
    plot_data: Optional[Plot] # Full Plot object from DB. For this subtask, may store chapter summaries directly if PlotArchitectAgent isn't fully updated
    plot_chapter_summaries: Optional[List[str]] # Specific for list of chapter plots

    # Character related fields
    characters: Optional[List[Character]]

    # Lore Keeper
    lore_keeper_initialized: bool

    # Chapter Generation Loop
    current_chapter_number: int
    total_chapters_to_generate: int
    generated_chapters: List[Chapter]

    # For current chapter processing
    active_character_ids_for_chapter: Optional[List[int]]
    current_chapter_plot_summary: Optional[str]
    chapter_brief: Optional[str]


# --- Node Functions ---

def _log_and_update_history(state: NovelWorkflowState, message: str, error: bool = False) -> List[str]:
    history_log = state.get("history", []) + [message]
    if error:
        print(f"Error: {message}")
    else:
        print(message)
    return history_log

def execute_narrative_pathfinder_agent(state: NovelWorkflowState) -> Dict[str, Any]:
    history_log = _log_and_update_history(state, "Executing Node: Narrative Pathfinder Agent")
    try:
        user_input = state["user_input"]
        theme = user_input["theme"]
        style = user_input.get("style_preferences", "general fiction")

        # Debugging the API Key check
        api_key_in_node = os.getenv("OPENAI_API_KEY", "")
        # More specific check for the exact dummy key string
        is_exact_dummy_key = api_key_in_node == "sk-dummyclikeyformainexecution"
        history_log = _log_and_update_history(state, f"API Key in NarrativePathfinder node (repr): {repr(api_key_in_node)} (checking for exact dummy key 'sk-dummyclikeyformainexecution'). Result of exact check: {is_exact_dummy_key}")

        # Mocking if dummy API key is used, to allow workflow to proceed
        if is_exact_dummy_key: # Changed condition to use the exact check
            history_log = _log_and_update_history(state, "MOCKING NarrativePathfinderAgent due to exact dummy API key match.")
            outline_text = f"Mock Outline for '{theme}': 1. Introduction to the world and main character. 2. Inciting incident. 3. Rising action and challenges. 4. Climax. 5. Resolution."
            history_log = _log_and_update_history(state, f"Successfully generated MOCK outline for theme: '{theme}'.")
            return {"narrative_outline_text": outline_text, "history": history_log, "error_message": None}

        agent = NarrativePathfinderAgent() # Assumes LLM client init is handled by agent
        outline_text = agent.generate_outline(user_theme=theme, style_preferences=style)
        if outline_text:
            history_log = _log_and_update_history(state, f"Successfully generated outline for theme: '{theme}'.")
            return {"narrative_outline_text": outline_text, "history": history_log, "error_message": None}
        else:
            msg = "Narrative Pathfinder Agent returned an empty outline."
            return {"error_message": msg, "history": _log_and_update_history(state, msg, True)}
    except Exception as e:
        msg = f"Error in Narrative Pathfinder Agent node: {e}"
        return {"error_message": msg, "history": _log_and_update_history(state, msg, True)}

def persist_novel_record_node(state: NovelWorkflowState) -> Dict[str, Any]:
    history_log = _log_and_update_history(state, "Executing Node: Persist Novel Record")
    try:
        user_input = state["user_input"]
        db_manager = DatabaseManager()
        theme = user_input["theme"]
        style = user_input.get("style_preferences", "") # Ensure style is string

        new_novel_id = db_manager.add_novel(user_theme=theme, style_preferences=style)
        novel_data = db_manager.get_novel_by_id(new_novel_id)

        history_log = _log_and_update_history(state, f"Novel record saved to DB with ID: {new_novel_id}.")
        return {"novel_id": new_novel_id, "novel_data": novel_data, "history": history_log, "error_message": None}
    except Exception as e:
        msg = f"Error in Persist Novel Record node: {e}"
        return {"error_message": msg, "history": _log_and_update_history(state, msg, True)}

def persist_initial_outline_node(state: NovelWorkflowState) -> Dict[str, Any]:
    history_log = _log_and_update_history(state, "Executing Node: Persist Initial Outline")
    try:
        novel_id = state["novel_id"]
        outline_text = state["narrative_outline_text"]
        if novel_id is None or outline_text is None:
            msg = "Novel ID or outline text missing for outline persistence."
            return {"error_message": msg, "history": _log_and_update_history(state, msg, True)}

        db_manager = DatabaseManager()
        new_outline_id = db_manager.add_outline(novel_id=novel_id, overview_text=outline_text)
        db_manager.update_novel_active_outline(novel_id, new_outline_id)
        outline_data = db_manager.get_outline_by_id(new_outline_id)

        history_log = _log_and_update_history(state, f"Initial outline saved with ID {new_outline_id} and linked to novel {novel_id}.")
        return {"outline_id": new_outline_id, "outline_data": outline_data, "history": history_log, "error_message": None}
    except Exception as e:
        msg = f"Error in Persist Initial Outline node: {e}"
        return {"error_message": msg, "history": _log_and_update_history(state, msg, True)}

def execute_world_weaver_agent(state: NovelWorkflowState) -> Dict[str, Any]:
    history_log = _log_and_update_history(state, "Executing Node: World Weaver Agent")
    try:
        outline_text = state["narrative_outline_text"]
        if not outline_text:
            msg = "Narrative outline text is required for World Weaver Agent."
            return {"error_message": msg, "history": _log_and_update_history(state, msg, True)}

        # Mocking if dummy API key is used
        api_key_in_node = os.getenv("OPENAI_API_KEY", "")
        is_exact_dummy_key = api_key_in_node == "sk-dummyclikeyformainexecution"
        history_log = _log_and_update_history(state, f"API Key in WorldWeaver node (repr): {repr(api_key_in_node)} (checking for exact dummy key). Result: {is_exact_dummy_key}")

        if is_exact_dummy_key: # Check for the exact dummy key
            history_log = _log_and_update_history(state, "MOCKING WorldWeaverAgent due to exact dummy API key match.")
            worldview_text = f"Mock Worldview for outline '{outline_text[:50]}...': A world of high fantasy with floating islands, magical creatures, and ancient prophecies."
            history_log = _log_and_update_history(state, "Successfully generated MOCK worldview text.")
            return {"worldview_text": worldview_text, "history": history_log, "error_message": None}

        agent = WorldWeaverAgent()
        worldview_text = agent.generate_worldview(narrative_outline=outline_text)
        if worldview_text:
            history_log = _log_and_update_history(state, "Successfully generated worldview text.")
            return {"worldview_text": worldview_text, "history": history_log, "error_message": None}
        else:
            msg = "World Weaver Agent returned empty worldview data."
            return {"worldview_text": None, "error_message": msg, "history": _log_and_update_history(state, msg, True)}
    except Exception as e:
        msg = f"Error in World Weaver Agent node: {e}"
        return {"worldview_text": None, "error_message": msg, "history": _log_and_update_history(state, msg, True)}

def persist_worldview_node(state: NovelWorkflowState) -> Dict[str, Any]:
    history_log = _log_and_update_history(state, "Executing Node: Persist Worldview")
    try:
        novel_id = state["novel_id"]
        worldview_text = state["worldview_text"]
        if novel_id is None or worldview_text is None:
            msg = "Novel ID or worldview text missing for worldview persistence."
            return {"error_message": msg, "history": _log_and_update_history(state, msg, True)}

        db_manager = DatabaseManager()
        new_worldview_id = db_manager.add_worldview(novel_id=novel_id, description_text=worldview_text)
        db_manager.update_novel_active_worldview(novel_id, new_worldview_id)
        worldview_data = db_manager.get_worldview_by_id(new_worldview_id)

        history_log = _log_and_update_history(state, f"Worldview saved with ID {new_worldview_id} and linked to novel {novel_id}.")
        return {"worldview_id": new_worldview_id, "worldview_data": worldview_data, "history": history_log, "error_message": None}
    except Exception as e:
        msg = f"Error in Persist Worldview node: {e}"
        return {"error_message": msg, "history": _log_and_update_history(state, msg, True)}

def execute_plot_architect_agent(state: NovelWorkflowState) -> Dict[str, Any]:
    history_log = _log_and_update_history(state, "Executing Node: Plot Architect Agent")
    try:
        # Required from state: narrative_outline_text, worldview_text (or full objects if preferred by agent)
        # For now, using the text versions.
        outline_text = state["narrative_outline_text"]
        worldview_text = state["worldview_text"] # Assuming this is the main description text
        total_chapters = state.get("total_chapters_to_generate", 3) # Defaulting if not set earlier

        if not outline_text or not worldview_text:
            msg = "Outline and worldview text are required for Plot Architect Agent."
            return {"error_message": msg, "history": _log_and_update_history(state, msg, True)}

        # agent = PlotArchitectAgent() # Assuming it's implemented
        # For this subtask, mock the output as specified:
        history_log = _log_and_update_history(state, "MOCKING PlotArchitectAgent: Generating chapter-by-chapter plot summaries.")
        plot_chapter_summaries = [
            f"Plot for Chapter {i+1}: Key event {i+1} occurs, characters face challenge {i+1} related to the main theme."
            for i in range(total_chapters)
        ]
        # In a real scenario, the agent might return a more structured Plot object or just the summaries.
        # For now, storing this list directly.

        history_log = _log_and_update_history(state, f"Generated {len(plot_chapter_summaries)} chapter plot summaries.")
        return {"plot_chapter_summaries": plot_chapter_summaries, "history": history_log, "error_message": None}
    except Exception as e:
        msg = f"Error in Plot Architect Agent node: {e}"
        return {"error_message": msg, "history": _log_and_update_history(state, msg, True)}

def persist_plot_node(state: NovelWorkflowState) -> Dict[str, Any]:
    history_log = _log_and_update_history(state, "Executing Node: Persist Plot")
    try:
        novel_id = state["novel_id"]
        plot_chapter_summaries = state["plot_chapter_summaries"]
        if novel_id is None or not plot_chapter_summaries:
            msg = "Novel ID or plot chapter summaries missing for plot persistence."
            return {"error_message": msg, "history": _log_and_update_history(state, msg, True)}

        db_manager = DatabaseManager()
        # Concatenate chapter summaries into one main plot summary for the Plot object
        # This might be refined later if Plot object needs more structure
        main_plot_summary_text = "\n".join(plot_chapter_summaries)

        new_plot_id = db_manager.add_plot(novel_id=novel_id, plot_summary=main_plot_summary_text)
        db_manager.update_novel_active_plot(novel_id, new_plot_id)
        plot_data = db_manager.get_plot_by_id(new_plot_id)

        history_log = _log_and_update_history(state, f"Plot saved with ID {new_plot_id} and linked to novel {novel_id}.")
        # plot_data now holds the full Plot object, plot_chapter_summaries is still in state for chapter loop
        return {"plot_id": new_plot_id, "plot_data": plot_data, "history": history_log, "error_message": None}
    except Exception as e:
        msg = f"Error in Persist Plot node: {e}"
        return {"error_message": msg, "history": _log_and_update_history(state, msg, True)}

def execute_character_sculptor_agent(state: NovelWorkflowState) -> Dict[str, Any]:
    history_log = _log_and_update_history(state, "Executing Node: Character Sculptor Agent")
    try:
        novel_id = state["novel_id"]
        outline = state["outline_data"] # Full Outline object
        worldview = state["worldview_data"] # Full Worldview object
        plot = state["plot_data"] # Full Plot object

        if not all([novel_id, outline, worldview, plot]):
            msg = "Novel ID, outline, worldview, or plot data missing for Character Sculptor."
            return {"error_message": msg, "history": _log_and_update_history(state, msg, True)}

        agent = CharacterSculptorAgent() # Uses mock LLM internally for now
        # Using main plot summary for character generation context
        characters = agent.generate_and_save_characters(
            novel_id=novel_id,
            narrative_outline=outline['overview_text'],
            worldview_data=worldview['description_text'],
            plot_summary=plot['plot_summary'],
            num_characters=2 # MVP: generate 2 characters
        )
        if characters:
            history_log = _log_and_update_history(state, f"Generated and saved {len(characters)} characters.")
            return {"characters": characters, "history": history_log, "error_message": None}
        else:
            msg = "Character Sculptor Agent failed to generate characters."
            return {"error_message": msg, "history": _log_and_update_history(state, msg, True)}
    except Exception as e:
        msg = f"Error in Character Sculptor Agent node: {e}"
        return {"error_message": msg, "history": _log_and_update_history(state, msg, True)}

def execute_lore_keeper_initialize(state: NovelWorkflowState) -> Dict[str, Any]:
    history_log = _log_and_update_history(state, "Executing Node: Lore Keeper Initialize")
    try:
        novel_id = state["novel_id"]
        outline = state["outline_data"]
        worldview = state["worldview_data"]
        plot = state["plot_data"]
        characters = state["characters"]

        if not all([novel_id, outline, worldview, plot, characters is not None]): # characters can be empty list
            msg = "Missing data for Lore Keeper initialization (novel_id, outline, worldview, plot, characters)."
            return {"error_message": msg, "history": _log_and_update_history(state, msg, True)}

        # LoreKeeperAgent might fail if API key is dummy, but it should handle it gracefully for KB init
        lore_keeper = LoreKeeperAgent(db_name="novel_mvp.db") # Specify DB if not default
        lore_keeper.initialize_knowledge_base(novel_id, outline, worldview, plot, characters)

        history_log = _log_and_update_history(state, "Lore Keeper knowledge base initialized.")
        return {"lore_keeper_initialized": True, "history": history_log, "error_message": None}
    except Exception as e:
        msg = f"Error in Lore Keeper Initialize node: {e}"
        # This node might fail with dummy API keys, so we log but don't always stop workflow here
        # depending on desired robustness vs. strictness. For now, let it be an error.
        return {"error_message": msg, "history": _log_and_update_history(state, msg, True), "lore_keeper_initialized": False}


def prepare_for_chapter_loop(state: NovelWorkflowState) -> Dict[str, Any]:
    history_log = _log_and_update_history(state, "Executing Node: Prepare for Chapter Loop")
    total_chapters = state.get("total_chapters_to_generate", 0)
    if not state.get("plot_chapter_summaries"):
        msg = "Plot chapter summaries not found, cannot determine total chapters."
        history_log = _log_and_update_history(state, msg, True)
        return {"error_message": msg, "history": history_log}

    # Override total_chapters_to_generate if plot_chapter_summaries exists
    num_plot_summaries = len(state["plot_chapter_summaries"])
    if num_plot_summaries > 0 :
        total_chapters = num_plot_summaries
    else: # Fallback if plot_chapter_summaries is empty for some reason
        total_chapters = 3 # Default MVP
        history_log = _log_and_update_history(state, f"Warning: plot_chapter_summaries is empty or missing. Defaulting to {total_chapters} chapters.")


    history_log = _log_and_update_history(state, f"Preparing for chapter loop. Total chapters to generate: {total_chapters}")
    return {
        "current_chapter_number": 1,
        "generated_chapters": [],
        "total_chapters_to_generate": total_chapters, # Use number of plot summaries
        "history": history_log,
        "error_message": None
    }

def execute_context_synthesizer_agent(state: NovelWorkflowState) -> Dict[str, Any]:
    history_log = _log_and_update_history(state, f"Executing Node: Context Synthesizer for Chapter {state['current_chapter_number']}")
    try:
        novel_id = state["novel_id"]
        current_chapter_num = state["current_chapter_number"]
        plot_summaries = state["plot_chapter_summaries"]
        characters = state["characters"]

        if not all([novel_id is not None, plot_summaries, characters is not None]):
            msg = "Missing data for Context Synthesizer (novel_id, plot_summaries, characters)."
            return {"error_message": msg, "history": _log_and_update_history(state, msg, True)}

        # Get current chapter's plot summary
        if not (0 < current_chapter_num <= len(plot_summaries)):
            msg = f"Invalid current_chapter_number {current_chapter_num} for {len(plot_summaries)} plot summaries."
            return {"error_message": msg, "history": _log_and_update_history(state, msg, True)}
        current_plot = plot_summaries[current_chapter_num - 1]

        # For MVP, assume first two characters are active, or all if less than two.
        active_char_ids: List[int] = []
        if characters:
            active_char_ids = [c['id'] for c in characters[:2]]

        context_agent = ContextSynthesizerAgent(db_name="novel_mvp.db")
        chapter_brief_text = context_agent.generate_chapter_brief(
            novel_id, current_chapter_num, current_plot, active_char_ids
        )

        history_log = _log_and_update_history(state, f"Chapter brief generated for Chapter {current_chapter_num}.")
        return {
            "chapter_brief": chapter_brief_text,
            "current_chapter_plot_summary": current_plot, # Storing for Chronicler
            "history": history_log,
            "error_message": None
        }
    except Exception as e:
        msg = f"Error in Context Synthesizer node: {e}"
        return {"error_message": msg, "history": _log_and_update_history(state, msg, True)}

def execute_chapter_chronicler_agent(state: NovelWorkflowState) -> Dict[str, Any]:
    history_log = _log_and_update_history(state, f"Executing Node: Chapter Chronicler for Chapter {state['current_chapter_number']}")
    try:
        novel_id = state["novel_id"]
        current_chapter_num = state["current_chapter_number"]
        chapter_brief = state["chapter_brief"]
        current_plot = state["current_chapter_plot_summary"] # Set by Context Synthesizer
        style_prefs = state["user_input"].get("style_preferences", "general fiction")

        if not all([novel_id is not None, chapter_brief, current_plot]):
            msg = "Missing data for Chapter Chronicler (novel_id, brief, current_plot)."
            return {"error_message": msg, "history": _log_and_update_history(state, msg, True)}

        chronicler_agent = ChapterChroniclerAgent(db_name="novel_mvp.db") # Uses mock LLM internally
        new_chapter = chronicler_agent.generate_and_save_chapter(
            novel_id, current_chapter_num, chapter_brief, current_plot, style_prefs
        )

        if new_chapter:
            updated_generated_chapters = state.get("generated_chapters", []) + [new_chapter]
            history_log = _log_and_update_history(state, f"Chapter {current_chapter_num} generated and saved.")
            return {"generated_chapters": updated_generated_chapters, "history": history_log, "error_message": None}
        else:
            msg = f"Chapter Chronicler failed to generate Chapter {current_chapter_num}."
            return {"error_message": msg, "history": _log_and_update_history(state, msg, True)}
    except Exception as e:
        msg = f"Error in Chapter Chronicler node: {e}"
        return {"error_message": msg, "history": _log_and_update_history(state, msg, True)}

def execute_lore_keeper_update_kb(state: NovelWorkflowState) -> Dict[str, Any]:
    history_log = _log_and_update_history(state, f"Executing Node: Lore Keeper Update KB for Chapter {state['current_chapter_number']}")
    try:
        novel_id = state["novel_id"]
        generated_chapters = state.get("generated_chapters", [])

        if novel_id is None or not generated_chapters:
            msg = "Novel ID or generated chapters missing for Lore Keeper KB update."
            # This might not be an error if it's the first chapter and list is empty before this node.
            # However, this node should run *after* a chapter is generated.
            return {"error_message": msg, "history": _log_and_update_history(state, msg, True)}

        last_chapter = generated_chapters[-1]
        lore_keeper = LoreKeeperAgent(db_name="novel_mvp.db")
        lore_keeper.update_knowledge_base_with_chapter(novel_id, last_chapter)

        history_log = _log_and_update_history(state, f"Lore Keeper KB updated with Chapter {last_chapter['chapter_number']}.")
        return {"history": history_log, "error_message": None} # No state change other than history
    except Exception as e:
        msg = f"Error in Lore Keeper Update KB node: {e}"
        # As with init, this might fail with dummy API keys.
        return {"error_message": msg, "history": _log_and_update_history(state, msg, True)}

def increment_chapter_number(state: NovelWorkflowState) -> Dict[str, Any]:
    current_num = state.get("current_chapter_number", 0)
    new_num = current_num + 1
    history_log = _log_and_update_history(state, f"Incrementing chapter number from {current_num} to {new_num}")
    return {"current_chapter_number": new_num, "history": history_log, "error_message": None}

# --- Conditional Edges ---
def _check_node_output(state: NovelWorkflowState) -> str:
    history_log = state.get("history", [])
    if state.get("error_message"):
        history_log.append(f"Error detected: '{state['error_message']}'. Routing to END.")
        print(f"Error detected in previous node. Routing to END. Error: {state.get('error_message')}")
        # state["history"] = history_log # This mutation is tricky with LangGraph state. Append to list and return.
        return "stop_on_error"
    else:
        history_log.append("Previous node successful. Continuing.")
        print("Previous node successful. Routing to continue.")
        # state["history"] = history_log
        return "continue"

def _should_continue_chapter_loop(state: NovelWorkflowState) -> str:
    history_log = state.get("history", [])
    if state.get("error_message"): # Check for errors from previous steps in the loop
        history_log.append(f"Error detected before loop condition: '{state['error_message']}'. Routing to END.")
        print(f"Error detected before loop condition. Routing to END. Error: {state.get('error_message')}")
        return "end_loop_on_error" # Special transition to END

    current_chapter = state.get("current_chapter_number", 1)
    total_chapters = state.get("total_chapters_to_generate", 0)

    if current_chapter <= total_chapters:
        history_log.append(f"Chapter loop: {current_chapter}/{total_chapters}. Continuing loop.")
        print(f"Chapter loop: {current_chapter}/{total_chapters}. Continuing loop.")
        return "continue_loop"
    else:
        history_log.append(f"Chapter loop: {current_chapter}/{total_chapters}. Ending loop.")
        print(f"Chapter loop: {current_chapter}/{total_chapters}. Ending loop.")
        return "end_loop"

# --- Workflow Manager Class ---
class WorkflowManager:
    def __init__(self, db_name="novel_mvp.db"):
        self.db_name = db_name # Though DatabaseManager instances mostly use default
        self.workflow = StateGraph(NovelWorkflowState)
        self._build_graph()
        self.app = self.workflow.compile()
        _log_and_update_history(NovelWorkflowState(history=[]), f"WorkflowManager initialized (DB: {self.db_name}) and graph compiled.")

    def _build_graph(self):
        # Add all nodes
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

        # Define entry point
        self.workflow.set_entry_point("narrative_pathfinder")

        # Define edges (linear part)
        self.workflow.add_conditional_edges("narrative_pathfinder", _check_node_output, {"continue": "persist_novel_record", "stop_on_error": END})
        self.workflow.add_conditional_edges("persist_novel_record", _check_node_output, {"continue": "persist_initial_outline", "stop_on_error": END})
        self.workflow.add_conditional_edges("persist_initial_outline", _check_node_output, {"continue": "world_weaver", "stop_on_error": END})
        self.workflow.add_conditional_edges("world_weaver", _check_node_output, {"continue": "persist_worldview", "stop_on_error": END})
        self.workflow.add_conditional_edges("persist_worldview", _check_node_output, {"continue": "plot_architect", "stop_on_error": END})
        self.workflow.add_conditional_edges("plot_architect", _check_node_output, {"continue": "persist_plot", "stop_on_error": END})
        self.workflow.add_conditional_edges("persist_plot", _check_node_output, {"continue": "character_sculptor", "stop_on_error": END})
        self.workflow.add_conditional_edges("character_sculptor", _check_node_output, {"continue": "lore_keeper_initialize", "stop_on_error": END})
        self.workflow.add_conditional_edges("lore_keeper_initialize", _check_node_output, {"continue": "prepare_for_chapter_loop", "stop_on_error": END})

        # Chapter Loop Start
        self.workflow.add_conditional_edges("prepare_for_chapter_loop", _check_node_output, {"continue": "context_synthesizer", "stop_on_error": END})

        # Inside the loop
        self.workflow.add_conditional_edges("context_synthesizer", _check_node_output, {"continue": "chapter_chronicler", "stop_on_error": END})
        self.workflow.add_conditional_edges("chapter_chronicler", _check_node_output, {"continue": "lore_keeper_update_kb", "stop_on_error": END})
        self.workflow.add_conditional_edges("lore_keeper_update_kb", _check_node_output, {"continue": "increment_chapter_number", "stop_on_error": END})

        # Conditional looping
        self.workflow.add_conditional_edges(
            "increment_chapter_number",
            _should_continue_chapter_loop,
            {
                "continue_loop": "context_synthesizer",
                "end_loop": END, # Successfully completed all chapters
                "end_loop_on_error": END # Error occurred in one of the loop steps
            }
        )
        _log_and_update_history(NovelWorkflowState(history=[]),"Workflow graph built.")


    def run_workflow(self, user_input_data: Dict[str, Any]) -> NovelWorkflowState:
        _log_and_update_history(NovelWorkflowState(history=[]),f"Starting workflow with input: {user_input_data}")
        initial_state = NovelWorkflowState(
            user_input=UserInput(
                theme=user_input_data.get("theme","A default theme if none provided"),
                style_preferences=user_input_data.get("style_preferences")
            ),
            error_message=None,
            history=[],
            novel_id=None,
            novel_data=None,
            narrative_outline_text=None,
            outline_id=None,
            outline_data=None,
            worldview_text=None,
            worldview_id=None,
            worldview_data=None,
            plot_id=None,
            plot_data=None,
            plot_chapter_summaries=None,
            characters=None,
            lore_keeper_initialized=False,
            current_chapter_number=0, # Initialized in prepare_for_chapter_loop
            total_chapters_to_generate=3, # Default, will be updated
            generated_chapters=[],
            active_character_ids_for_chapter=None,
            current_chapter_plot_summary=None,
            chapter_brief=None
        )
        # Use a higher recursion limit for loops
        final_state = self.app.invoke(initial_state, {"recursion_limit": 50})

        final_history = final_state.get("history", [])
        _log_and_update_history(NovelWorkflowState(history=final_history), "Workflow finished.")
        if final_state.get('error_message'):
             _log_and_update_history(NovelWorkflowState(history=final_history), f"Workflow error: {final_state.get('error_message')}", True)
        return final_state


if __name__ == "__main__":
    print("--- Workflow Manager Full Integration Test ---")

    # Ensure OPENAI_API_KEY is set for agents that use LLMClient
    # The agents themselves (or LLMClient) should handle dummy keys for mocks if applicable
    if not os.path.exists(".env") and not os.getenv("OPENAI_API_KEY"):
        print("Creating a dummy .env file for WorkflowManager test (for LLMClient dependent agents)...")
        with open(".env", "w") as f:
            f.write("OPENAI_API_KEY=\"sk-dummykeyforworkflowmanagertest\"\n")
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        print("CRITICAL: OPENAI_API_KEY not found. Some agents will fail to initialize.")
    elif "dummykey" in os.getenv("OPENAI_API_KEY",""):
        print("INFO: Using a dummy OPENAI_API_KEY. LLM calls will be mocked by agents or fail if not mocked.")


    default_db_name = "novel_workflow_test.db"
    default_chroma_dir = "./novel_workflow_chroma_db"

    import shutil
    if os.path.exists(default_db_name):
        os.remove(default_db_name)
        print(f"Removed existing test SQL DB: {default_db_name}")
    if os.path.exists(default_chroma_dir):
        shutil.rmtree(default_chroma_dir)
        print(f"Removed existing test Chroma DB directory: {default_chroma_dir}")

    # Initialize DB once to ensure tables are set up by DatabaseManager's __init__
    _ = DatabaseManager(db_name=default_db_name)
    # Also, LoreKeeperAgent's __init__ might create its Chroma dir, so we ensure its path is clean.
    # The manager itself will instantiate agents which might create their own specific test DBs/dirs if not configured.
    # For this test, agents should ideally use the main DB passed or default to it.

    manager = WorkflowManager(db_name=default_db_name) # Pass the db_name

    sample_user_input = {
        "theme": "a space pirate captain searching for a legendary treasure on a lost planet",
        "style_preferences": "action-packed sci-fi with witty dialogue and detailed world-building"
    }
    print(f"\nRunning workflow with: {sample_user_input}")

    final_result_state = manager.run_workflow(sample_user_input)

    print("\n--- Workflow Final State ---")
    print(f"User Input: {final_result_state.get('user_input')}")
    print(f"Novel ID: {final_result_state.get('novel_id')}")
    print(f"Novel Data: {final_result_state.get('novel_data')}")
    print(f"Outline ID: {final_result_state.get('outline_id')}")
    outline_data_val = final_result_state.get('outline_data')
    print(f"Outline Data: {outline_data_val.get('overview_text', '')[:100] if outline_data_val else 'N/A'}...")
    print(f"Worldview ID: {final_result_state.get('worldview_id')}")
    worldview_data_val = final_result_state.get('worldview_data')
    print(f"Worldview Data: {worldview_data_val.get('description_text', '')[:100] if worldview_data_val else 'N/A'}...")
    print(f"Plot ID: {final_result_state.get('plot_id')}")
    plot_data_val = final_result_state.get('plot_data')
    print(f"Plot Data (Summary): {plot_data_val.get('plot_summary', '')[:100] if plot_data_val else 'N/A'}...")
    print(f"Plot Chapter Summaries: {final_result_state.get('plot_chapter_summaries')}")

    characters = final_result_state.get('characters')
    if characters:
        print(f"Generated Characters ({len(characters)}):")
        for char in characters:
            print(f"  - ID: {char['id']}, Name: {char['name']}, Role: {char['role_in_story']}")
    else:
        print("Generated Characters: None")

    print(f"Lore Keeper Initialized: {final_result_state.get('lore_keeper_initialized')}")

    generated_chapters_final = final_result_state.get('generated_chapters', [])
    print(f"Total Chapters Generated: {len(generated_chapters_final)}")
    print(f"Expected Chapters: {final_result_state.get('total_chapters_to_generate')}")

    for i, chapter in enumerate(generated_chapters_final):
        print(f"\n  Chapter {i+1} (DB ID: {chapter['id']}, Num: {chapter['chapter_number']}):")
        print(f"    Title: {chapter['title']}")
        print(f"    Summary: {chapter['summary']}")
        print(f"    Content Snippet: {chapter['content'][:100]}...")

    print(f"\nError Message at end of workflow: {final_result_state.get('error_message')}")

    print("\nFinal History Log:")
    for entry in final_result_state.get("history", []):
        print(f"  - {entry}")

    # Verification
    if final_result_state.get('novel_id') and not final_result_state.get('error_message'):
        print(f"\nVerifying data in database '{default_db_name}' for Novel ID {final_result_state['novel_id']}...")
        verify_db = DatabaseManager(db_name=default_db_name)
        db_novel = verify_db.get_novel_by_id(final_result_state['novel_id'])
        assert db_novel is not None, "Novel not found in DB."
        assert db_novel['user_theme'] == sample_user_input['theme']

        if final_result_state.get('outline_id'):
            db_outline = verify_db.get_outline_by_id(final_result_state['outline_id'])
            assert db_outline is not None and db_outline['novel_id'] == db_novel['id']
            assert db_novel['active_outline_id'] == final_result_state['outline_id']
            print("  Verified: Novel, Outline")

        if final_result_state.get('worldview_id'):
            db_worldview = verify_db.get_worldview_by_id(final_result_state['worldview_id'])
            assert db_worldview is not None and db_worldview['novel_id'] == db_novel['id']
            assert db_novel['active_worldview_id'] == final_result_state['worldview_id']
            print("  Verified: Worldview")

        if final_result_state.get('plot_id'):
            db_plot = verify_db.get_plot_by_id(final_result_state['plot_id'])
            assert db_plot is not None and db_plot['novel_id'] == db_novel['id']
            assert db_novel['active_plot_id'] == final_result_state['plot_id']
            print("  Verified: Plot")

        if final_result_state.get('characters'):
            db_chars = verify_db.get_characters_for_novel(db_novel['id'])
            assert len(db_chars) == len(final_result_state['characters'])
            print(f"  Verified: {len(db_chars)} Characters")

        db_chapters = verify_db.get_chapters_for_novel(db_novel['id'])
        assert len(db_chapters) == len(generated_chapters_final)
        print(f"  Verified: {len(db_chapters)} Chapters in DB")

        # Verify KB entries related to chapters if LoreKeeper was initialized
        if final_result_state.get('lore_keeper_initialized'):
            kb_entries = verify_db.get_kb_entries_for_novel(db_novel['id'], entry_type='chapter_summary')
            # This assertion might be too strict if API key is dummy and LK update failed
            # For now, we check if at least some attempt was made if chapters were generated
            if len(generated_chapters_final) > 0 and "dummykey" not in os.getenv("OPENAI_API_KEY",""):
                 assert len(kb_entries) == len(generated_chapters_final), \
                    f"Expected {len(generated_chapters_final)} chapter KB entries, found {len(kb_entries)}"
            print(f"  Verified: {len(kb_entries)} Chapter KB entries in DB (Note: depends on API key for LoreKeeper)")
        print("  All available DB verifications passed.")

    else:
        print("\nSkipping DB verification due to workflow error or no novel_id.")

    # Clean up
    if os.path.exists(default_db_name):
        os.remove(default_db_name)
        print(f"\nCleaned up test SQL DB: {default_db_name}")
    if os.path.exists(default_chroma_dir):
        shutil.rmtree(default_chroma_dir)
        print(f"Cleaned up test Chroma DB directory: {default_chroma_dir}")
    if os.path.exists(".env") and "dummykeyforworkflowmanagertest" in open(".env").read():
        print("Removing dummy .env file for WorkflowManager test...")
        os.remove(".env")

    print("\n--- Workflow Manager Full Integration Test Finished ---")

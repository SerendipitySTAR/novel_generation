from langgraph.graph import StateGraph, END
from typing import TypedDict, Any, List, Annotated, Dict
import operator

from src.agents.narrative_pathfinder_agent import NarrativePathfinderAgent
from src.agents.world_weaver_agent import WorldWeaverAgent
from src.persistence.database_manager import DatabaseManager

# UserInput and NovelWorkflowState remain the same as in the previous step's subtask
class UserInput(TypedDict):
    theme: str
    style_preferences: str | None

class NovelWorkflowState(TypedDict):
    user_input: UserInput
    narrative_outline: str | None
    narrative_id: int | None
    worldview_data: str | None
    error_message: str | None
    history: Annotated[List[str], operator.add]

# execute_narrative_pathfinder_agent remains the same
def execute_narrative_pathfinder_agent(state: NovelWorkflowState):
    print("Executing Node: Narrative Pathfinder Agent")
    history_log = state.get("history", []) + ["Narrative Pathfinder Agent started."]
    try:
        user_input = state.get("user_input")
        if not user_input or not user_input.get("theme"):
            error_msg = "User input with 'theme' is required for Narrative Pathfinder."
            history_log.append(f"Error: {error_msg}")
            return {"error_message": error_msg, "history": history_log}
        theme = user_input["theme"]
        style = user_input.get("style_preferences", "general fiction")
        agent = NarrativePathfinderAgent()
        outline = agent.generate_outline(user_theme=theme, style_preferences=style)
        if outline:
            history_log.append(f"Successfully generated outline for theme: '{theme}'.")
            return {"narrative_outline": outline, "history": history_log, "error_message": None}
        else:
            error_msg = "Narrative Pathfinder Agent returned an empty outline."
            history_log.append(f"Error: {error_msg}")
            return {"narrative_outline": None, "error_message": error_msg, "history": history_log}
    except Exception as e:
        error_msg = f"Error in Narrative Pathfinder Agent node: {e}"
        history_log.append(error_msg)
        return {"narrative_outline": None, "error_message": error_msg, "history": history_log}

# persist_narrative_node remains the same (persists initial narrative outline)
def persist_narrative_node(state: NovelWorkflowState):
    print("Executing Node: Persist Narrative (Initial Outline)")
    history_log = state.get("history", []) + ["Persistence Node (Initial Outline) started."]
    try:
        user_input = state.get("user_input")
        narrative_outline = state.get("narrative_outline")
        if not user_input or not narrative_outline:
            error_msg = "User input or narrative outline missing for persistence."
            history_log.append(f"Error: {error_msg}")
            return {"error_message": error_msg, "history": history_log}
        db_manager = DatabaseManager()
        theme = user_input["theme"]
        style = user_input.get("style_preferences", "general fiction")
        new_id = db_manager.add_narrative(
            user_theme=theme,
            style_preferences=style,
            generated_outline=narrative_outline
            # worldview is not available yet at this stage
        )
        history_log.append(f"Narrative (initial) successfully saved to database with ID: {new_id}.")
        return {"narrative_id": new_id, "history": history_log, "error_message": None}
    except Exception as e:
        error_msg = f"Error in Persist Narrative node: {e}"
        history_log.append(error_msg)
        return {"error_message": error_msg, "history": history_log, "narrative_id": None}

# execute_world_weaver_agent remains the same
def execute_world_weaver_agent(state: NovelWorkflowState):
    print("Executing Node: World Weaver Agent")
    history_log = state.get("history", []) + ["World Weaver Agent started."]
    try:
        narrative_outline = state.get("narrative_outline")
        if not narrative_outline:
            error_msg = "Narrative outline is required for World Weaver Agent."
            history_log.append(f"Error: {error_msg}")
            return {"error_message": state.get("error_message") or error_msg, "history": history_log}
        agent = WorldWeaverAgent()
        worldview = agent.generate_worldview(narrative_outline=narrative_outline)
        if worldview:
            history_log.append("Successfully generated worldview.")
            return {"worldview_data": worldview, "history": history_log, "error_message": None}
        else:
            error_msg = "World Weaver Agent returned empty worldview data."
            history_log.append(f"Error: {error_msg}")
            return {"worldview_data": None, "error_message": error_msg, "history": history_log}
    except Exception as e:
        error_msg = f"Error in World Weaver Agent node: {e}"
        history_log.append(error_msg)
        return {"worldview_data": None, "error_message": error_msg, "history": history_log}

# New Node for Persisting Worldview
def persist_worldview_node(state: NovelWorkflowState):
    print("Executing Node: Persist Worldview")
    history_log = state.get("history", []) + ["Persistence Node (Worldview) started."]
    try:
        narrative_id = state.get("narrative_id")
        worldview_data = state.get("worldview_data")

        if narrative_id is None or worldview_data is None:
            error_msg = "Narrative ID or worldview data missing for worldview persistence."
            print(f"Error: {error_msg}")
            history_log.append(f"Error: {error_msg}")
            # Preserve existing error if one occurred earlier
            return {"error_message": state.get("error_message") or error_msg, "history": history_log}

        db_manager = DatabaseManager() # Default 'novel_mvp.db'
        update_success = db_manager.update_narrative_worldview(
            narrative_id=narrative_id,
            generated_worldview=worldview_data
        )

        if update_success:
            history_log.append(f"Worldview successfully saved to database for narrative ID: {narrative_id}.")
            print(f"Worldview persisted for narrative ID: {narrative_id}")
            return {"history": history_log, "error_message": None} # No change to error_message if successful
        else:
            error_msg = f"Failed to persist worldview for narrative ID: {narrative_id} (DB update failed)."
            print(f"Error: {error_msg}")
            history_log.append(f"Error: {error_msg}")
            return {"error_message": error_msg, "history": history_log}

    except Exception as e:
        error_msg = f"Error in Persist Worldview node: {e}"
        print(error_msg)
        history_log.append(error_msg)
        return {"error_message": error_msg, "history": history_log}


class WorkflowManager:
    def __init__(self, db_name="novel_mvp.db"):
        self.db_name = db_name
        self.workflow = StateGraph(NovelWorkflowState)
        self._build_graph()
        self.app = self.workflow.compile()
        print(f"WorkflowManager initialized (DB: {self.db_name}) and graph compiled.")

    def _build_graph(self):
        self.workflow.add_node("narrative_pathfinder", execute_narrative_pathfinder_agent)
        self.workflow.add_node("persist_narrative_outline", persist_narrative_node) # Clarified name
        self.workflow.add_node("world_weaver", execute_world_weaver_agent)
        self.workflow.add_node("persist_worldview", persist_worldview_node) # New node

        self.workflow.set_entry_point("narrative_pathfinder")

        self.workflow.add_conditional_edges(
            "narrative_pathfinder", self._check_node_output,
            {"continue": "persist_narrative_outline", "stop_on_error": END}
        )
        self.workflow.add_conditional_edges(
            "persist_narrative_outline", self._check_node_output,
            {"continue": "world_weaver", "stop_on_error": END}
        )
        self.workflow.add_conditional_edges(
            "world_weaver", self._check_node_output,
            {"continue": "persist_worldview", "stop_on_error": END} # Route to persist_worldview
        )
        self.workflow.add_conditional_edges( # Add conditional edge for persist_worldview
            "persist_worldview", self._check_node_output,
            {"continue": END, "stop_on_error": END} # END after worldview persistence
        )

    def _check_node_output(self, state: NovelWorkflowState):
        # This generic checker remains the same
        print(f"Checking output of previous node. Current error: {state.get('error_message')}")
        if state.get("error_message"):
            print("Error detected in previous node. Routing to END.")
            return "stop_on_error"
        else:
            print("Previous node successful. Routing to continue.")
            return "continue"

    def run_workflow(self, user_input_data: Dict[str, Any]):
        # This method remains the same
        print(f"Starting workflow with input: {user_input_data}")
        initial_state = NovelWorkflowState(
            user_input=UserInput(
                theme=user_input_data.get("theme",""),
                style_preferences=user_input_data.get("style_preferences")
            ),
            narrative_outline=None, narrative_id=None, worldview_data=None,
            error_message=None, history=[]
        )
        final_state = self.app.invoke(initial_state, {"recursion_limit": 20}) # Increased limit
        print(f"Workflow finished. Final history: {final_state.get('history')}")
        if final_state.get('error_message'):
             print(f"Workflow error: {final_state.get('error_message')}")
        return final_state

if __name__ == "__main__":
    print("--- Workflow Manager Integration Test (with Worldview Persistence) ---")

    default_db_for_test = "novel_mvp.db"
    import os
    if os.path.exists(default_db_for_test):
        os.remove(default_db_for_test)

    manager = WorkflowManager()

    sample_user_input = {"theme": "a detective who is also a talented pastry chef", "style_preferences": "cozy mystery with recipes"}
    print(f"\nRunning workflow with: {sample_user_input}")
    result = manager.run_workflow(sample_user_input)

    print("\nResults for workflow run:")
    print(f"  Error Message: {result.get('error_message')}")
    print(f"  Narrative ID: {result.get('narrative_id')}")
    print(f"  Narrative Outline Snippet: {result.get('narrative_outline', '')[:100]}...")
    print(f"  Worldview Data Snippet: {result.get('worldview_data', '')[:100]}...")

    if result.get('narrative_id') and not result.get('error_message'):
        print(f"  >> Verifying ID {result.get('narrative_id')} in {default_db_for_test} for worldview...")
        try:
            verify_db_manager = DatabaseManager(db_name=default_db_for_test)
            retrieved = verify_db_manager.get_narrative_by_id(result.get('narrative_id'))
            if retrieved:
                print(f"  Verification: Found narrative '{retrieved['user_theme']}' in DB.")
                assert retrieved['user_theme'] == sample_user_input['theme']
                assert retrieved['generated_worldview'] is not None, "Worldview data was not saved to DB"
                assert len(retrieved['generated_worldview']) > 0, "Worldview data saved to DB is empty"
                print(f"  Worldview from DB Snippet: {retrieved['generated_worldview'][:100]}...")
            else:
                print("  Verification failed: Narrative not found in DB for worldview check.")
        except Exception as e:
            print(f"  Error during DB verification for worldview: {e}")
    elif result.get('error_message'):
        print(f"  Workflow ended with error, skipping DB check for worldview: {result.get('error_message')}")
    else:
        print("  Workflow did not produce a narrative_id, skipping DB check for worldview.")


    if os.path.exists(default_db_for_test):
        os.remove(default_db_for_test)
        print(f"Cleaned up '{default_db_for_test}' after test.")

    print("--- Workflow Manager Integration Test (with Worldview Persistence) Finished ---")

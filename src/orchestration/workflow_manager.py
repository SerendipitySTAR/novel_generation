from langgraph.graph import StateGraph, END
from typing import TypedDict, Any, List, Annotated, Dict
import operator

from src.agents.narrative_pathfinder_agent import NarrativePathfinderAgent
from src.persistence.database_manager import DatabaseManager # Import DatabaseManager

# Define a more structured user input type
class UserInput(TypedDict):
    theme: str
    style_preferences: str | None

# Define the state for the overall novel generation workflow
class NovelWorkflowState(TypedDict):
    user_input: UserInput
    narrative_outline: str | None
    narrative_id: int | None # To store the ID of the saved narrative
    worldview_data: Any
    error_message: str | None
    history: Annotated[List[str], operator.add]

# Actual Narrative Pathfinder Node (remains mostly unchanged)
def execute_narrative_pathfinder_agent(state: NovelWorkflowState):
    print("Executing Node: Narrative Pathfinder Agent")
    history_log = state.get("history", []) + ["Narrative Pathfinder Agent started."]
    try:
        user_input = state.get("user_input")
        if not user_input or not user_input.get("theme"):
            error_msg = "User input with 'theme' is required for Narrative Pathfinder."
            print(f"Error: {error_msg}")
            history_log.append(f"Error: {error_msg}")
            return {"error_message": error_msg, "history": history_log}

        theme = user_input["theme"]
        style = user_input.get("style_preferences", "general fiction")

        agent = NarrativePathfinderAgent()
        outline = agent.generate_outline(user_theme=theme, style_preferences=style)

        if outline:
            history_log.append(f"Successfully generated outline for theme: '{theme}'.")
            print(f"Generated outline: {outline[:100]}...")
            return {"narrative_outline": outline, "history": history_log, "error_message": None}
        else:
            error_msg = "Narrative Pathfinder Agent returned an empty outline."
            print(f"Error: {error_msg}")
            history_log.append(f"Error: {error_msg}")
            return {"narrative_outline": None, "error_message": error_msg, "history": history_log}

    except Exception as e:
        error_msg = f"Error in Narrative Pathfinder Agent node: {e}"
        print(error_msg)
        history_log.append(error_msg)
        return {"narrative_outline": None, "error_message": error_msg, "history": history_log}

# New Node for Persisting Narrative
def persist_narrative_node(state: NovelWorkflowState):
    print("Executing Node: Persist Narrative")
    history_log = state.get("history", []) + ["Persistence Node started."]
    try:
        user_input = state.get("user_input")
        narrative_outline = state.get("narrative_outline")

        if not user_input or not narrative_outline:
            error_msg = "User input or narrative outline missing for persistence."
            print(f"Error: {error_msg}")
            history_log.append(f"Error: {error_msg}")
            return {"error_message": error_msg, "history": history_log}

        db_manager = DatabaseManager() # Default 'novel_mvp.db'
        theme = user_input["theme"]
        style = user_input.get("style_preferences", "general fiction")

        new_id = db_manager.add_narrative(
            user_theme=theme,
            style_preferences=style,
            generated_outline=narrative_outline
        )
        history_log.append(f"Narrative successfully saved to database with ID: {new_id}.")
        print(f"Narrative saved with ID: {new_id}")
        return {"narrative_id": new_id, "history": history_log, "error_message": None}

    except Exception as e:
        error_msg = f"Error in Persist Narrative node: {e}"
        print(error_msg)
        history_log.append(error_msg)
        # Decide if this error should halt the workflow or just be logged
        return {"error_message": error_msg, "history": history_log, "narrative_id": None}


# Placeholder Worldview Node (remains unchanged for now)
def worldview_node(state: NovelWorkflowState):
    print("Executing Placeholder: Worldview Node")
    history_log = state.get("history", []) + ["Worldview Node started."]
    if not state.get("narrative_outline"): # Or check narrative_id if it becomes a dependency
        error_msg = "Narrative outline missing for worldview generation."
        print(f"Skipping Worldview Node: {error_msg}")
        history_log.append(f"Skipped: {error_msg}")
        return {"history": history_log, "error_message": state.get("error_message")}

    worldview = f"Detailed worldview based on outline (ID: {state.get('narrative_id', 'N/A')}): {state.get('narrative_outline','')[:100]}..."
    history_log.append("Successfully generated placeholder worldview data.")
    return {"worldview_data": worldview, "history": history_log}


class WorkflowManager:
    def __init__(self, db_name="novel_mvp.db"): # Allow db_name to be passed for testing
        self.db_name = db_name # Store db_name if DatabaseManager needs it consistently
        self.workflow = StateGraph(NovelWorkflowState)
        self._build_graph()
        self.app = self.workflow.compile()
        print(f"WorkflowManager initialized (DB: {self.db_name}) and graph compiled.")

    def _build_graph(self):
        self.workflow.add_node("narrative_pathfinder", execute_narrative_pathfinder_agent)
        self.workflow.add_node("persist_narrative", persist_narrative_node) # Add new node
        self.workflow.add_node("worldview_builder", worldview_node)

        self.workflow.set_entry_point("narrative_pathfinder")

        self.workflow.add_conditional_edges(
            "narrative_pathfinder",
            self._check_node_output, # Generic checker for error_message
            {
                "continue": "persist_narrative", # If successful, go to persist
                "stop_on_error": END
            }
        )

        self.workflow.add_conditional_edges(
            "persist_narrative", # Check output of persistence node
            self._check_node_output,
            {
                "continue": "worldview_builder", # If successful, go to worldview
                "stop_on_error": END
            }
        )
        self.workflow.add_edge("worldview_builder", END)

    def _check_node_output(self, state: NovelWorkflowState):
        # A more generic check for errors after a node execution
        print(f"Checking output of previous node. Current error: {state.get('error_message')}")
        # The last executed node's direct output is not easily accessible here without specific langgraph patterns.
        # We rely on the convention that nodes update 'error_message' in the shared state.
        if state.get("error_message"):
            print("Error detected in previous node. Routing to END.")
            return "stop_on_error"
        else:
            print("Previous node successful. Routing to continue.")
            return "continue"

    def run_workflow(self, user_input_data: Dict[str, Any]):
        print(f"Starting workflow with input: {user_input_data}")
        initial_state = NovelWorkflowState(
            user_input=UserInput(
                theme=user_input_data.get("theme",""),
                style_preferences=user_input_data.get("style_preferences")
            ),
            narrative_outline=None,
            narrative_id=None, # Initialize narrative_id
            worldview_data=None,
            error_message=None,
            history=[]
        )

        final_state = self.app.invoke(initial_state, {"recursion_limit": 10})
        print(f"Workflow finished.")
        print(f"Final history: {final_state.get('history')}")
        if final_state.get('error_message'):
             print(f"Workflow error: {final_state.get('error_message')}")
        return final_state

if __name__ == "__main__":
    print("--- Workflow Manager Integration Test (with Persistence) ---")

    # Use a test-specific database file for this test run
    test_db = "test_workflow_db.sqlite"
    import os
    if os.path.exists(test_db):
        os.remove(test_db) # Clean up before test

    # Pass the test_db name to the manager, and it can pass to DatabaseManager if needed
    # For this example, DatabaseManager in persist_narrative_node will use its default or one set if we modify it.
    # To make it clean, let's assume persist_narrative_node will use the default db_name
    # or we'd have to pass it through the state, which is more complex.
    # For the DatabaseManager used in persist_narrative_node, it will create 'novel_mvp.db'
    # if not specified otherwise. Let's ensure `novel_mvp.db` is cleaned up if it's created by this test.
    default_db_for_test = "novel_mvp.db"
    if os.path.exists(default_db_for_test):
        os.remove(default_db_for_test)

    manager = WorkflowManager() # This will use 'novel_mvp.db' by default for its nodes

    sample_user_input = {"theme": "a knight who is afraid of the dark", "style_preferences": "comedic fantasy"}
    print(f"\nRunning workflow with: {sample_user_input}")
    result = manager.run_workflow(sample_user_input)

    print("\nResults for workflow run:")
    print(f"  Error Message: {result.get('error_message')}")
    print(f"  Narrative Outline Snippet: {result.get('narrative_outline', '')[:100]}...")
    print(f"  Narrative ID: {result.get('narrative_id')}")
    print(f"  Worldview Data: {result.get('worldview_data')}")

    # Verify in DB (manual step for this test, or extend test)
    if result.get('narrative_id'):
        print(f"  >> Verifying ID {result.get('narrative_id')} in {default_db_for_test} (manual check or extend test script)")
        # Example verification (can be part of a more elaborate test script)
        try:
            verify_db_manager = DatabaseManager(db_name=default_db_for_test) # Connect to the same DB
            retrieved = verify_db_manager.get_narrative_by_id(result.get('narrative_id'))
            if retrieved:
                print(f"  Verification successful: Found narrative '{retrieved['user_theme']}' in DB.")
                assert retrieved['user_theme'] == sample_user_input['theme']
            else:
                print("  Verification failed: Narrative not found in DB.")
        except Exception as e:
            print(f"  Error during DB verification: {e}")


    # Test error in agent
    sample_user_input_agent_fail = {"theme": "", "style_preferences": "sci-fi"} # Missing theme
    print(f"\nRunning workflow with input that causes agent error: {sample_user_input_agent_fail}")
    result_agent_fail = manager.run_workflow(sample_user_input_agent_fail)
    print("\nResults for agent error run:")
    print(f"  Error Message: {result_agent_fail.get('error_message')}")
    assert "User input with 'theme' is required" in result_agent_fail.get('error_message', '')


    # Clean up the default database created by the test.
    if os.path.exists(default_db_for_test):
        os.remove(default_db_for_test)
        print(f"Cleaned up '{default_db_for_test}' after test.")

    print("--- Workflow Manager Integration Test (with Persistence) Finished ---")

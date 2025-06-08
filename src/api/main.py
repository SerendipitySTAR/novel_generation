from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
import uvicorn
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uuid
from datetime import datetime
import json # Required for selected_worldview_detail in deprecated endpoint

from src.orchestration.workflow_manager import WorkflowManager, NovelWorkflowState # Added NovelWorkflowState for typing
from src.persistence.database_manager import DatabaseManager # Added DatabaseManager
from src.agents.lore_keeper_agent import LoreKeeperAgent # Added for Knowledge Graph endpoint


# --- Pydantic Models for API Request and Response ---

class NarrativeRequestPayload(BaseModel): # Kept for existing endpoint
    theme: str
    style_preferences: Optional[str] = "general fiction"

class NarrativeResponse(BaseModel): # Kept for existing endpoint
    narrative_id: Optional[int] = None
    narrative_outline: Optional[str] = None
    worldview_data: Optional[str] = None
    error_message: Optional[str] = None
    history: Optional[List[str]] = None

# --- New/Updated Pydantic Models for Novel Generation ---

class NovelGenerationRequest(BaseModel):
    theme: str
    style_preferences: Optional[str] = "general fiction"
    chapters: Optional[int] = 3
    words_per_chapter: Optional[int] = 1000
    mode: Optional[str] = "auto" # Defaulting to auto for background tasks

class NovelMetadataResponse(BaseModel):
    novel_id: int
    theme: str
    status: str
    created_at: datetime # Store as ISO string, FastAPI handles conversion

class NovelStatusResponse(BaseModel):
    novel_id: int
    status: str
    current_step: Optional[str] = None # e.g., "generating_outline", "writing_chapter_2"
    last_history_entry: Optional[str] = None
    error_message: Optional[str] = None
    # Potentially add: created_at, last_updated_at

# --- Pydantic Models for Human Decision Endpoints ---
class DecisionOption(BaseModel):
    id: str # Could be a numerical index as string, or a specific hash/ID
    text_summary: str
    full_data: Optional[Any] = None

class DecisionPromptResponse(BaseModel):
    novel_id: int
    decision_type: Optional[str] = None
    prompt_message: Optional[str] = None
    options: Optional[List[DecisionOption]] = None
    workflow_status: str # e.g. "paused_for_outline_selection", "running", "completed"

class DecisionSubmissionRequest(BaseModel):
    action: str  # e.g., "apply_suggestion", "ignore_conflict", "rewrite_all_auto_remaining", "proceed_with_remaining"
    conflict_id: Optional[str] = None # ID of the specific conflict, if action is conflict-specific
    suggestion_index: Optional[int] = None # Index of the LLM suggestion, if action is "apply_suggestion"
    user_comment: Optional[str] = None # Optional notes from user
    # selected_option_id is removed as conflict_id is more specific for this context.
    # custom_data is removed in favor of specific fields for conflict decisions.
    # If this model is used for other decision types later, it might need to be more generic
    # or have other models for other decision types. For now, tailor to conflict review.

class ResumeWorkflowResponse(BaseModel):
    novel_id: int
    message: str
    status_after_resume_trigger: str


class ChapterContentResponse(BaseModel): # Kept for existing endpoint
    novel_id: int
    chapter_number: int
    title: Optional[str] = "N/A"
    content: Optional[str] = "Content not found or not yet generated."
    review: Optional[Dict[str, Any]] = None # From ContentIntegrityAgent
    error_message: Optional[str] = None

class ConflictReportResponse(BaseModel): # Kept for existing endpoint
    novel_id: int
    chapter_number: int
    conflicts: Optional[List[Dict[str, Any]]] = []
    error_message: Optional[str] = None

class KnowledgeGraphResponse(BaseModel): # Kept for existing endpoint
    novel_id: int
    graph_data: Optional[Dict[str, Any]] = {"nodes": [], "edges": []}
    error_message: Optional[str] = None


app = FastAPI(
    title="Automatic Novel Generator API",
    description="API for managing and interacting with the novel generation process.",
    version="0.2.0", # Incremented version for new features
)

# --- Database and Workflow Manager Initialization ---
# For simplicity in this example, using a global DB name.
# In a real app, this might come from config.
DB_FILE_NAME = "novel_api_main.db"

# This function will run in the background
def run_novel_workflow_task(novel_id: int, user_input_data: dict, db_name_for_task: str):
    print(f"Background task started for novel_id: {novel_id} with db: {db_name_for_task}")
    db_manager_task = DatabaseManager(db_name=db_name_for_task)
    db_manager_task.update_novel_status(novel_id, workflow_status="processing", current_step_details="Workflow started.")

    try:
        # WorkflowManager's mode is now primarily driven by user_input_data's interaction_mode and auto_mode
        manager = WorkflowManager(db_name=db_name_for_task)
        user_input_data_for_wf = user_input_data.copy()
        # Ensure interaction_mode is set if API is used, default to "api" if this task is called by API.
        # However, this task is generic; the caller (API endpoint) should set interaction_mode.
        # For POST /novels/, if mode is "human", interaction_mode should be "api".
        if user_input_data_for_wf.get("mode") == "human" and not user_input_data_for_wf.get("interaction_mode"):
            user_input_data_for_wf["interaction_mode"] = "api"

        final_state: NovelWorkflowState = manager.run_workflow(user_input_data_for_wf)

        final_workflow_status = final_state.get("workflow_status", "unknown_completion")
        final_error_message = final_state.get("error_message")

        # Serialize final state for storage if needed, especially if paused.
        # Simplified serialization:
        final_state_json = json.dumps({
            k: v for k, v in final_state.items()
            if isinstance(v, (type(None), str, int, float, bool, list, dict))
        })

        if final_error_message:
            print(f"Background task for novel_id {novel_id} completed with error: {final_error_message}")
            db_manager_task.update_novel_status_after_resume(novel_id, "failed", final_state_json) # Use a method that also saves state
        elif final_workflow_status.startswith("paused_for_"):
            # The decision node itself should have saved its pause state via update_novel_pause_state.
            # No further action needed here on status, assuming decision node did its job.
            print(f"Background task for novel_id {novel_id} paused: {final_workflow_status}")
        else:
            print(f"Background task for novel_id {novel_id} completed successfully. Status: {final_workflow_status}")
            db_manager_task.update_novel_status_after_resume(novel_id, final_workflow_status, final_state_json)

    except Exception as e:
        print(f"Critical error in background task run_novel_workflow_task for novel_id {novel_id}: {e}")
        import traceback; traceback.print_exc()
        db_manager_task.update_novel_status(novel_id, workflow_status="system_error", error_message=str(e))
    finally:
        print(f"Background task run_novel_workflow_task finished for novel_id: {novel_id}")


@app.get("/")
async def root():
    return {"message": "Welcome to the Automatic Novel Generator API!"}

@app.get("/healthcheck")
async def health_check():
    return {"status": "ok", "message": "API is healthy"}

# --- New Endpoints ---
@app.post("/novels/", response_model=NovelMetadataResponse, status_code=202) # 202 Accepted for background tasks
async def create_novel_generation_task(
    payload: NovelGenerationRequest,
    background_tasks: BackgroundTasks,
    request: Request # To construct full URL
):
    print(f"API: Received request to generate novel: Theme='{payload.theme}', Mode='{payload.mode}'")
    db_manager = DatabaseManager(db_name=DB_FILE_NAME) # Use the global DB name

    try:
        # Add novel to DB with initial "pending" status
        # Assuming add_novel is adapted or a new method add_novel_with_status exists
        # For now, we'll use add_novel and conceptually update status later or assume it adds a default status
        novel_id = db_manager.add_novel(
            user_theme=payload.theme,
            style_preferences=payload.style_preferences or "general fiction"
            # status="pending" # Conceptual
        )
        # db_manager.update_novel_status(novel_id, "pending", "Awaiting workflow start") # Conceptual

        novel_record = db_manager.get_novel_by_id(novel_id)
        if not novel_record:
            raise HTTPException(status_code=500, detail="Failed to create novel record in database.")

        user_input_for_workflow = {
            "theme": payload.theme,
            "style_preferences": payload.style_preferences,
            "chapters": payload.chapters,
            "words_per_chapter": payload.words_per_chapter,
            "auto_mode": payload.mode == "auto" # WorkflowManager expects auto_mode boolean
        }

        background_tasks.add_task(run_novel_workflow_task, novel_id, user_input_for_workflow, DB_FILE_NAME)

        return NovelMetadataResponse(
            novel_id=novel_id,
            theme=novel_record['user_theme'], # Use validated data from DB
            status="pending", # Initial status returned
            created_at=datetime.fromisoformat(novel_record['creation_date']) # Convert from ISO string
        )
    except Exception as e:
        # import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to start novel generation: {e}")


@app.get("/novels/{novel_id}/status", response_model=NovelStatusResponse)
async def get_novel_status(novel_id: int):
    print(f"API: Request for status of Novel ID {novel_id}")
    db_manager = DatabaseManager(db_name=DB_FILE_NAME)
    novel_record = db_manager.get_novel_by_id(novel_id)

    if not novel_record:
        raise HTTPException(status_code=404, detail=f"Novel with ID {novel_id} not found.")

    # Conceptual: Fetch these from the novel_record if the DB schema were updated
    db_data = db_manager.load_workflow_snapshot_and_decision_info(novel_id) # This now fetches all relevant fields

    workflow_status = db_data.get("workflow_status", "unknown") if db_data else "unknown"
    current_step = None
    last_history_entry = None # Placeholder, could parse from full_workflow_state_json if needed
    error_msg = db_data.get("error_message") if db_data else None # Assuming error_message is a direct column or part of state

    if db_data:
        # If there's a pending decision, that's the most current step/status detail
        if db_data.get("pending_decision_type"):
            current_step = f"Awaiting decision for: {db_data['pending_decision_type']}"
            # workflow_status might already be "paused_for_..." which is good.
        elif workflow_status.startswith("resuming_") or workflow_status.startswith("running_"):
             current_step = "Workflow in progress..."
        elif workflow_status == "pending" and not db_data.get("pending_decision_type"): # Initial state before first run
            current_step = "Workflow is pending initiation."
        # Add more specific current_step details based on workflow_status if it's more granular like "outline_generated"
        elif workflow_status == "outline_generated":
            current_step = "Outline generation complete."
        elif workflow_status == "chapters_generated":
            # This is a fallback, ideally status from workflow run is more descriptive
            chapters = db_manager.get_chapters_for_novel(novel_id) # Query only if needed
            current_step = f"Chapter {len(chapters)} generated."
        elif workflow_status in ["completed", "failed", "system_error", "system_error_resuming_task", "resumption_critical_error"]:
            current_step = f"Workflow ended with status: {workflow_status}"
            if error_msg:
                 current_step += f" Error: {error_msg}"


        # Attempt to get last history entry from snapshot if available
        full_state_json = db_data.get("full_workflow_state_json")
        if full_state_json:
            try:
                state_dict = json.loads(full_state_json)
                if state_dict.get("history") and isinstance(state_dict["history"], list) and state_dict["history"]:
                    last_history_entry = str(state_dict["history"][-1]) # Ensure it's a string
            except json.JSONDecodeError:
                print(f"Warning: Could not parse full_workflow_state_json for novel {novel_id} in status check for history.")


    return NovelStatusResponse(
        novel_id=novel_id,
        status=workflow_status,
        current_step=current_step,
        last_history_entry=last_history_entry,
        error_message=error_msg
    )

# --- Human Decision Endpoints ---
@app.get("/novels/{novel_id}/decisions/next", response_model=DecisionPromptResponse)
async def get_next_human_decision(novel_id: int):
    print(f"API: Request for next human decision for Novel ID {novel_id}")
    db_manager = DatabaseManager(db_name=DB_FILE_NAME)
    decision_info = db_manager.load_workflow_snapshot_and_decision_info(novel_id)

    if not decision_info:
        novel_check = db_manager.get_novel_by_id(novel_id)
        if not novel_check:
            raise HTTPException(status_code=404, detail=f"Novel with ID {novel_id} not found.")
        return DecisionPromptResponse(
            novel_id=novel_id,
            decision_type=None,
            prompt_message="No pending human decision found or novel not in a pausable state.",
            options=[],
            workflow_status=novel_check.get("workflow_status", "unknown") # type: ignore
        )

    workflow_status = decision_info.get("workflow_status", "running")
    pending_decision_type = decision_info.get("pending_decision_type")
    options_json = decision_info.get("pending_decision_options_json")
    prompt_message = decision_info.get("pending_decision_prompt")

    options_list: Optional[List[DecisionOption]] = None
    if options_json:
        try:
            options_data = json.loads(options_json)
            options_list = [DecisionOption(**opt) for opt in options_data]
        except json.JSONDecodeError:
            print(f"API Error: Could not parse decision options JSON for novel {novel_id}")
            raise HTTPException(status_code=500, detail="Error processing decision options for novel.")

    if workflow_status and workflow_status.startswith("paused_for_") and pending_decision_type:
        # For conflict_review, options_list might be the conflicts themselves.
        # The API model DecisionOption expects id, text_summary, full_data.
        # The 'pending_decision_options' in DB for conflict_review should be List[ConflictDict].
        api_ready_options: List[DecisionOption] = []
        if options_list and pending_decision_type == "conflict_review":
            for conflict_dict in options_list: # options_list here is List[Dict] from JSON
                api_ready_options.append(DecisionOption(
                    id=str(conflict_dict.get("conflict_id", uuid.uuid4())), # Ensure ID, fallback to new UUID
                    text_summary=conflict_dict.get("description", "N/A")[:150],
                    full_data=conflict_dict
                ))
        elif options_list: # For other decision types like outline/worldview
             api_ready_options = [DecisionOption(**opt) for opt in options_list]


        return DecisionPromptResponse(
            novel_id=novel_id,
            decision_type=pending_decision_type,
            prompt_message=prompt_message or f"Please make a selection for {pending_decision_type}.",
            options=api_ready_options, # Use the transformed list
            workflow_status=workflow_status
        )
    else:
        # If it's not specifically "paused_for_", or if options/type are missing when they shouldn't be.
        return DecisionPromptResponse(
            novel_id=novel_id,
            decision_type=None,
            prompt_message="No active human decision currently pending for this novel.",
            options=[],
            workflow_status=workflow_status
        )

def resume_novel_workflow_task(novel_id: int, decision_type: str, decision_payload_dict: dict, db_name_for_task: str):
    print(f"Background task to RESUME workflow for novel_id: {novel_id}, decision: {decision_type}")
    db_manager_task = DatabaseManager(db_name=db_name_for_task)

    try:
        manager = WorkflowManager(db_name=db_name_for_task)
        final_state_after_resume = manager.resume_workflow(novel_id, decision_type, decision_payload_dict)

        final_status = final_state_after_resume.get("workflow_status", "unknown_after_resume")

        if not final_status.startswith("paused_for_"):
            # If it's not paused again, then it either completed, failed, or hit an unexpected state.
            # The resume_workflow method itself now handles saving the final state snapshot.
            print(f"Novel {novel_id} workflow after resume: Final status '{final_status}'. State saved by resume_workflow.")
        else:
            # If it paused again, the pause state (including snapshot) was already saved by the decision node
            # from within the resume_workflow -> self.app.invoke() call.
            print(f"Novel {novel_id} workflow paused again after resume for: {final_status}. State saved by decision node.")

    except Exception as e:
        print(f"Critical error in resume_novel_workflow_task for novel_id {novel_id}: {e}")
        import traceback
        traceback.print_exc()
        # Ensure the DB reflects this task-level error.
        db_manager_task.update_novel_status(novel_id, workflow_status="system_error_resuming_task", error_message=str(e))
    finally:
        print(f"Background task for resuming novel_id {novel_id} finished.")


@app.post("/novels/{novel_id}/decisions/{decision_type_param}", response_model=ResumeWorkflowResponse)
async def submit_human_decision(
    novel_id: int,
    decision_type_param: str, # From path
    payload: DecisionSubmissionRequest,
    background_tasks: BackgroundTasks
):
    print(f"API: Received decision for Novel ID {novel_id}, Type: {decision_type_param}, Payload: {payload.model_dump_json(exclude_none=True)}")
    db_manager = DatabaseManager(db_name=DB_FILE_NAME)

    # Explicit novel existence check (though load_workflow_snapshot_and_decision_info often implies it)
    novel_check = db_manager.get_novel_by_id(novel_id)
    if not novel_check:
        raise HTTPException(status_code=404, detail=f"Novel with ID {novel_id} not found.")

    # Validate if the novel is actually awaiting this decision
    loaded_info = db_manager.load_workflow_snapshot_and_decision_info(novel_id)
    if not loaded_info or not loaded_info.get("workflow_status"):
        raise HTTPException(status_code=404, detail=f"Workflow state not found for novel ID {novel_id} or novel is in an invalid state (e.g., no status).")

    current_workflow_status = loaded_info["workflow_status"]
    expected_decision_type = loaded_info.get("pending_decision_type")

    if not current_workflow_status.startswith("paused_for_"):
        raise HTTPException(status_code=409, detail=f"Novel {novel_id} is not currently awaiting a decision. Current status: {current_workflow_status}")

    if expected_decision_type != decision_type_param:
        raise HTTPException(status_code=409, detail=f"Novel {novel_id} is awaiting decision type '{expected_decision_type}', but received decision for '{decision_type_param}'.")

    # Action-specific payload validation
    action = payload.action
    if decision_type_param == "conflict_review": # Specific checks for conflict_review actions
        if action == "apply_suggestion":
            if payload.conflict_id is None or payload.suggestion_index is None:
                raise HTTPException(status_code=422, detail="For 'apply_suggestion' action, 'conflict_id' and 'suggestion_index' are required.")
        elif action == "ignore_conflict":
            if payload.conflict_id is None:
                raise HTTPException(status_code=422, detail="For 'ignore_conflict' action, 'conflict_id' is required.")
        # Actions like "rewrite_all_auto_remaining" or "proceed_with_remaining" might not need extra fields from payload here.

    # Generic selected_id check for other decision types (e.g., outline_selection, worldview_selection)
    # The API path decision_type_param should match the expected type.
    # These are conceptual action names; actual names might differ based on API design.
    elif decision_type_param == "outline_selection": # Assuming action in payload distinguishes if needed, or is implicit
        # Example: if payload.action was "select_specific_outline"
        if payload.selected_id is None: # selected_id is on DecisionSubmissionRequest but Optional
            raise HTTPException(status_code=422, detail=f"For '{decision_type_param}' action '{action}', 'selected_id' is required.")
    elif decision_type_param == "worldview_selection":
        if payload.selected_id is None:
            raise HTTPException(status_code=422, detail=f"For '{decision_type_param}' action '{action}', 'selected_id' is required.")

    # Add more decision_type_param checks and their required payload fields as necessary.

    user_decision_payload_json = payload.model_dump_json(exclude_none=True)
    new_db_status = f"resuming_with_decision_{decision_type_param}"

    try:
        db_manager.record_user_decision(novel_id, decision_type_param, user_decision_payload_json, new_workflow_status=new_db_status)
    except Exception as e:
        # Handle potential DB error during recording decision
        raise HTTPException(status_code=500, detail=f"Failed to record decision in database: {e}")

    decision_data_for_workflow = payload.model_dump() # Pass the dict to the task

    background_tasks.add_task(resume_novel_workflow_task, novel_id, decision_type_param, decision_data_for_workflow, DB_FILE_NAME)

    return ResumeWorkflowResponse(
        novel_id=novel_id,
        message=f"Decision for '{decision_type_param}' received. Workflow resumption triggered.",
        status_after_resume_trigger=new_db_status
    )


# --- Existing Endpoints (Kept for now) ---
@app.post("/generate/narrative_outline", response_model=NarrativeResponse, deprecated=True)
async def generate_narrative_outline_endpoint(payload: NarrativeRequestPayload):
    """
    Generates a narrative outline and worldview.
    **Deprecated**: Use `POST /novels/` and then retrieve components.
    """
    print(f"API: Received request to generate narrative outline for theme: '{payload.theme}'")
    try:
        manager = WorkflowManager(db_name=DB_FILE_NAME) # Use global DB name
        workflow_input = {
            "theme": payload.theme,
            "style_preferences": payload.style_preferences,
            "chapters": 1, # Minimal for outline/worldview
            "auto_mode": True # Assume auto for this older endpoint
        }
        final_state = manager.run_workflow(workflow_input)
        response_data = {
            "narrative_id": final_state.get("novel_id"), # Changed from narrative_id to novel_id
            "narrative_outline": final_state.get("narrative_outline_text"), # Key name change
            "worldview_data": json.dumps(final_state.get("selected_worldview_detail")) if final_state.get("selected_worldview_detail") else None,
            "error_message": final_state.get("error_message"),
            "history": final_state.get("history")
        }
        if final_state.get("error_message"):
            print(f"API: Workflow (narrative_outline) completed with error: {final_state.get('error_message')}")
        return NarrativeResponse(**response_data)
    except Exception as e:
        # import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"An unexpected API error occurred: {e}")


@app.get("/novels/{novel_id}/chapters/{chapter_number}", response_model=ChapterContentResponse, deprecated=True)
async def get_chapter_content(novel_id: int, chapter_number: int):
    """
    Retrieves content for a specific chapter.
    **Deprecated**: More specific component endpoints might be added or status endpoint might provide paths.
    """
    print(f"API: Request for content of Novel ID {novel_id}, Chapter {chapter_number}")
    db_manager = DatabaseManager(db_name=DB_FILE_NAME)
    chapter_obj = db_manager.get_chapters_for_novel(novel_id) # Gets all, find specific one
    target_chapter = next((c for c in chapter_obj if c['chapter_number'] == chapter_number), None)

    if target_chapter:
        # Conceptual: Fetch review data if stored separately
        # review_data = db_manager.get_chapter_review(target_chapter['id'])
        return ChapterContentResponse(
            novel_id=novel_id,
            chapter_number=chapter_number,
            title=target_chapter['title'],
            content=target_chapter['content'],
            # review=review_data # Add if available
        )
    raise HTTPException(status_code=404, detail=f"Chapter {chapter_number} for novel {novel_id} not found.")


@app.get("/novels/{novel_id}/chapters/{chapter_number}/conflicts", response_model=ConflictReportResponse, deprecated=True)
async def get_chapter_conflict_report(novel_id: int, chapter_number: int):
    """
    Retrieves conflict report for a specific chapter.
    **Deprecated**: This information might be part of a broader status or quality report.
    """
    print(f"API: Request for conflict report of Novel ID {novel_id}, Chapter {chapter_number}")
    # This endpoint is harder to implement correctly without the workflow actively storing this
    # specific data point per chapter in an easily queryable way by the DB.
    # The current workflow state (`current_chapter_conflicts`) is transient.
    # For now, returning a placeholder.
    # A real implementation would require DB schema changes or a log/event store.
    return ConflictReportResponse(
        novel_id=novel_id,
        chapter_number=chapter_number,
        conflicts=[], # Placeholder
        error_message="Conflict reporting per chapter is conceptual and not fully implemented for direct query."
    )

@app.get("/novels/{novel_id}/knowledge_graph", response_model=KnowledgeGraphResponse)
async def get_novel_knowledge_graph(novel_id: int):
    """
    Retrieves the knowledge graph for a novel.
    This endpoint attempts to generate/retrieve the KG data on-demand.
    """
    print(f"API: Request for knowledge graph of Novel ID {novel_id}")
    db_manager = DatabaseManager(db_name=DB_FILE_NAME)
    novel_record = db_manager.get_novel_by_id(novel_id)

    if not novel_record:
        raise HTTPException(status_code=404, detail=f"Novel with ID {novel_id} not found.")

    # Optional: Check novel status if desired (e.g., only allow if "completed")
    # For now, we proceed if the novel exists.

    try:
        agent = LoreKeeperAgent(db_name=DB_FILE_NAME)
        # Assuming get_knowledge_graph_data is designed to be called post-generation
        # and can derive the graph from persisted KB entries.
        graph_data = agent.get_knowledge_graph_data(novel_id=novel_id)

        if graph_data and ("nodes" in graph_data or "edges" in graph_data): # Basic check for valid graph structure
            # Check if the agent itself reported an error within the graph_data
            if isinstance(graph_data.get("error"), str):
                 print(f"API: LoreKeeperAgent reported an error for KG novel {novel_id}: {graph_data['error']}")
                 return KnowledgeGraphResponse(
                    novel_id=novel_id,
                    graph_data={"nodes": graph_data.get("nodes",[]), "edges": graph_data.get("edges",[])}, # return partial data if available
                    error_message=f"Error from knowledge graph generation: {graph_data['error']}"
                )
            return KnowledgeGraphResponse(novel_id=novel_id, graph_data=graph_data)
        else:
            # This case handles if graph_data is None or not in the expected format
            print(f"API: Knowledge graph data for novel {novel_id} was empty or invalid from LoreKeeperAgent.")
            return KnowledgeGraphResponse(
                novel_id=novel_id,
                graph_data={"nodes": [], "edges": []}, # Return empty graph
                error_message="Knowledge graph data is empty or could not be generated."
            )
    except ImportError as ie: # Catch specific error if LoreKeeperAgent or its deps are missing
        print(f"API: ImportError during LoreKeeperAgent instantiation for KG novel {novel_id}: {ie}")
        # import traceback; traceback.print_exc(); # For server logs
        raise HTTPException(status_code=501, detail=f"Knowledge Graph feature is not fully available due to missing dependencies: {ie}")
    except Exception as e:
        print(f"API: Error retrieving knowledge graph for novel {novel_id}: {e}")
        # import traceback; traceback.print_exc(); # For server logs
        # Consider if this should be a 500 or a specific response indicating KG failure
        return KnowledgeGraphResponse(
            novel_id=novel_id,
            graph_data=None,
            error_message=f"An unexpected error occurred while generating the knowledge graph: {str(e)}"
        )


if __name__ == "__main__":
    # Create a default DB if it doesn't exist for local testing
    print(f"Initializing database '{DB_FILE_NAME}' for API...")
    _ = DatabaseManager(db_name=DB_FILE_NAME) # This will create tables if they don't exist

    print("Starting FastAPI server with Uvicorn...")
    print(f"Run with: uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000")
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)

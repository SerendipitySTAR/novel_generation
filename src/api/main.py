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

# --- Pydantic Models for KB Validation ---
class KBValidationRequestItem(BaseModel):
    id: str
    novel_id: int
    request_type: str
    source_reference: Optional[str] = None
    source_text_snippet: Optional[str] = None
    item_under_review_json: str
    validation_question: str
    system_suggestion_json: Optional[str] = None
    status: str
    creation_date: str

class KBValidationRequestDetail(KBValidationRequestItem): # Inherits all fields, can add more if needed
    user_decision: Optional[str] = None
    user_corrected_value_json: Optional[str] = None
    user_comment: Optional[str] = None
    resolution_date: Optional[str] = None

class KBValidationResolutionPayload(BaseModel):
    decision: str # e.g., "confirmed", "rejected", "edited"
    corrected_value_json: Optional[str] = None # JSON string of user's correction
    user_comment: Optional[str] = None
    # Status will be determined server-side based on decision

# --- Pydantic Models for Outline and Worldview Editing ---
class OutlineUpdatePayload(BaseModel):
    overview_text: str

class OutlineResponse(BaseModel):
    id: int
    novel_id: int
    overview_text: str
    creation_date: str # Keep as string for API consistency, FastAPI handles datetime conversion

class WorldviewUpdatePayload(BaseModel):
    description_text: str # Core concept

class WorldviewResponse(BaseModel):
    id: int
    novel_id: int
    description_text: str
    creation_date: str

# --- Pydantic Models for Character Editing ---
class CharacterUpdatePayload(BaseModel):
    name: Optional[str] = None
    role_in_story: Optional[str] = None
    # Client sends the full JSON string of profile attributes (DetailedCharacterProfile fields)
    description_json: Optional[str] = None

# Re-using DetailedCharacterProfile from src.core.models for response.
# If it were complex or needed API-specific views, a CharacterResponse Pydantic model would be made here.
# For now, we'll assume DetailedCharacterProfile can be returned directly by FastAPI.
# If DetailedCharacterProfile is a TypedDict, FastAPI might handle it, or we might need a Pydantic version.
# For robustness, let's define a Pydantic version of DetailedCharacterProfile for responses.

class CharacterResponse(BaseModel):
    character_id: Optional[int] = None
    novel_id: Optional[int] = None
    creation_date: Optional[str] = None
    name: str
    gender: Optional[str] = None
    age: Optional[str] = None
    race_or_species: Optional[str] = None
    appearance_summary: Optional[str] = None
    clothing_style: Optional[str] = None
    background_story: Optional[str] = None
    personality_traits: Optional[str] = None
    values_and_beliefs: Optional[str] = None
    strengths: Optional[List[str]] = None
    weaknesses: Optional[List[str]] = None
    quirks_or_mannerisms: Optional[List[str]] = None
    catchphrase_or_verbal_style: Optional[str] = None
    skills_and_abilities: Optional[List[str]] = None
    special_powers: Optional[List[str]] = None
    power_level_assessment: Optional[str] = None
    motivations_deep_drive: Optional[str] = None
    goal_short_term: Optional[str] = None
    goal_long_term: Optional[str] = None
    character_arc_potential: Optional[str] = None
    relationships_initial_notes: Optional[str] = None
    role_in_story: Optional[str] = None
    raw_llm_output_for_character: Optional[str] = None


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


# --- FastAPI App Initialization ---
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


# --- KB Validation Endpoints ---
@app.get("/novels/{novel_id}/kb_validation_requests", response_model=List[KBValidationRequestItem])
async def list_pending_kb_validation_requests(novel_id: int):
    print(f"API: Request for pending KB validation requests for Novel ID {novel_id}")
    db_manager = DatabaseManager(db_name=DB_FILE_NAME)
    novel_check = db_manager.get_novel_by_id(novel_id)
    if not novel_check:
        raise HTTPException(status_code=404, detail=f"Novel with ID {novel_id} not found.")

    try:
        pending_requests_db = db_manager.get_pending_kb_validation_requests(novel_id)
        # Convert list of dicts from DB to list of Pydantic models
        response_items = [KBValidationRequestItem(**req) for req in pending_requests_db]
        return response_items
    except Exception as e:
        print(f"API: Error retrieving pending KB validation requests for novel {novel_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve KB validation requests.")

@app.post("/novels/{novel_id}/kb_validation_requests/{validation_id}/resolve", response_model=KBValidationRequestDetail)
async def resolve_kb_validation_request_endpoint(
    novel_id: int,
    validation_id: str,
    payload: KBValidationResolutionPayload
):
    print(f"API: Request to resolve KB validation ID {validation_id} for Novel ID {novel_id} with decision: {payload.decision}")
    db_manager = DatabaseManager(db_name=DB_FILE_NAME)

    # Check if novel and validation request exist
    novel_check = db_manager.get_novel_by_id(novel_id)
    if not novel_check:
        raise HTTPException(status_code=404, detail=f"Novel with ID {novel_id} not found.")

    validation_request = db_manager.get_kb_validation_request_by_id(validation_id)
    if not validation_request:
        raise HTTPException(status_code=404, detail=f"KB Validation Request with ID {validation_id} not found.")

    if validation_request['novel_id'] != novel_id:
        raise HTTPException(status_code=400, detail=f"Validation request {validation_id} does not belong to novel {novel_id}.")

    if validation_request['status'] != 'pending_review':
        raise HTTPException(status_code=409, detail=f"Validation request {validation_id} is not pending review. Current status: {validation_request['status']}.")

    # Determine new status based on decision
    new_status = "unknown"
    if payload.decision == "confirmed":
        new_status = "user_confirmed"
    elif payload.decision == "rejected":
        new_status = "user_rejected"
    elif payload.decision == "edited":
        new_status = "user_edited"
        if payload.corrected_value_json is None:
            raise HTTPException(status_code=422, detail="For 'edited' decision, 'corrected_value_json' is required.")
    else:
        raise HTTPException(status_code=422, detail=f"Invalid decision type: '{payload.decision}'. Must be 'confirmed', 'rejected', or 'edited'.")

    try:
        success = db_manager.resolve_kb_validation_request(
            validation_id=validation_id,
            decision=payload.decision,
            status=new_status,
            corrected_value_json=payload.corrected_value_json,
            user_comment=payload.user_comment
        )
        if not success:
            # This might happen if rowcount was 0, e.g., validation_id disappeared
            raise HTTPException(status_code=500, detail="Failed to update validation request in database (e.g. not found or no change made).")

        updated_request = db_manager.get_kb_validation_request_by_id(validation_id)
        if not updated_request: # Should not happen if success was true
            raise HTTPException(status_code=500, detail="Failed to retrieve updated validation request.")

        # Placeholder: Trigger LoreKeeperAgent processing of this decision
        # This would ideally be a background task or part of a larger workflow step.
        # For now, just logging it.
        print(f"TODO: Trigger LoreKeeperAgent to process validation ID {validation_id} with decision '{payload.decision}' and new status '{new_status}'.")
        # Example (conceptual, actual call might differ):
        # lore_keeper = LoreKeeperAgent(db_name=DB_FILE_NAME)
        # background_tasks.add_task(lore_keeper.process_user_kb_validation_decision, validation_id, payload.decision, json.loads(payload.corrected_value_json) if payload.corrected_value_json else None)

        return KBValidationRequestDetail(**updated_request)

    except Exception as e:
        print(f"API: Error resolving KB validation request {validation_id}: {e}")
        # import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to resolve KB validation request: {str(e)}")


# --- Character Editing Endpoints ---
@app.get("/novels/{novel_id}/characters/{character_id}", response_model=CharacterResponse)
async def get_character_details(novel_id: int, character_id: int):
    db_manager = DatabaseManager(db_name=DB_FILE_NAME)
    novel = db_manager.get_novel_by_id(novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail=f"Novel with ID {novel_id} not found.")

    character_profile_dict = db_manager.get_character_by_id(character_id) # This returns DetailedCharacterProfile (a TypedDict)
    if not character_profile_dict or character_profile_dict['novel_id'] != novel_id:
        raise HTTPException(status_code=404, detail=f"Character with ID {character_id} not found for novel {novel_id}.")

    # Convert TypedDict to Pydantic model for response
    return CharacterResponse(**character_profile_dict)


@app.put("/novels/{novel_id}/characters/{character_id}", response_model=CharacterResponse)
async def update_novel_character(novel_id: int, character_id: int, payload: CharacterUpdatePayload):
    db_manager = DatabaseManager(db_name=DB_FILE_NAME)

    if payload.name is None and payload.role_in_story is None and payload.description_json is None:
        raise HTTPException(status_code=422, detail="No update data provided. At least one of 'name', 'role_in_story', or 'description_json' must be supplied.")

    novel = db_manager.get_novel_by_id(novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail=f"Novel with ID {novel_id} not found.")

    # Check if character exists and belongs to the novel
    existing_character = db_manager.get_character_by_id(character_id) # Returns DetailedCharacterProfile
    if not existing_character or existing_character['novel_id'] != novel_id:
        raise HTTPException(status_code=404, detail=f"Character with ID {character_id} not found for novel {novel_id}.")

    # Validate description_json if provided
    if payload.description_json is not None:
        try:
            json.loads(payload.description_json) # Validate if it's proper JSON
        except json.JSONDecodeError:
            raise HTTPException(status_code=422, detail="Invalid 'description_json' format. Must be a valid JSON string.")

    try:
        success = db_manager.update_character(
            character_id=character_id,
            name=payload.name,
            description=payload.description_json, # Pass the JSON string directly
            role_in_story=payload.role_in_story
        )
        if not success:
            # This could mean character_id not found, or no actual change in data resulted in 0 affected rows.
            # The db_manager.update_character fetches novel_id before update attempt,
            # so if character_id was invalid, it would have returned False from there.
            # If data is same, rowcount is 0, but it's not an error. We can re-fetch to confirm.
            # For simplicity, if update returns False but no exception, assume data was same or ID invalid (already checked).
             pass # Allow re-fetch to return current state

        updated_character_data = db_manager.get_character_by_id(character_id)
        if not updated_character_data: # Should not happen if initial checks passed
             raise HTTPException(status_code=500, detail="Failed to retrieve updated character after update attempt.")
        return CharacterResponse(**updated_character_data)
    except Exception as e:
        # import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"An error occurred while updating character: {str(e)}")


# --- Outline and Worldview Editing Endpoints ---
@app.get("/novels/{novel_id}/outlines/{outline_id}", response_model=OutlineResponse)
async def get_outline_details(novel_id: int, outline_id: int):
    db_manager = DatabaseManager(db_name=DB_FILE_NAME)
    novel = db_manager.get_novel_by_id(novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail=f"Novel with ID {novel_id} not found.")

    outline = db_manager.get_outline_by_id(outline_id)
    if not outline or outline['novel_id'] != novel_id:
        raise HTTPException(status_code=404, detail=f"Outline with ID {outline_id} not found for novel {novel_id}.")
    return OutlineResponse(**outline)

@app.put("/novels/{novel_id}/outlines/{outline_id}", response_model=OutlineResponse)
async def update_novel_outline(novel_id: int, outline_id: int, payload: OutlineUpdatePayload):
    db_manager = DatabaseManager(db_name=DB_FILE_NAME)
    novel = db_manager.get_novel_by_id(novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail=f"Novel with ID {novel_id} not found.")

    # Check if outline exists and belongs to the novel
    existing_outline = db_manager.get_outline_by_id(outline_id)
    if not existing_outline or existing_outline['novel_id'] != novel_id:
        raise HTTPException(status_code=404, detail=f"Outline with ID {outline_id} not found for novel {novel_id}.")

    try:
        success = db_manager.update_outline(outline_id, payload.overview_text)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update outline in database.")

        updated_outline_data = db_manager.get_outline_by_id(outline_id)
        if not updated_outline_data: # Should not happen if update was successful
             raise HTTPException(status_code=500, detail="Failed to retrieve updated outline.")
        return OutlineResponse(**updated_outline_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred while updating outline: {str(e)}")

@app.get("/novels/{novel_id}/worldviews/{worldview_id}", response_model=WorldviewResponse)
async def get_worldview_details(novel_id: int, worldview_id: int):
    db_manager = DatabaseManager(db_name=DB_FILE_NAME)
    novel = db_manager.get_novel_by_id(novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail=f"Novel with ID {novel_id} not found.")

    worldview = db_manager.get_worldview_by_id(worldview_id)
    if not worldview or worldview['novel_id'] != novel_id:
        raise HTTPException(status_code=404, detail=f"Worldview with ID {worldview_id} not found for novel {novel_id}.")
    return WorldviewResponse(**worldview)

@app.put("/novels/{novel_id}/worldviews/{worldview_id}", response_model=WorldviewResponse)
async def update_novel_worldview(novel_id: int, worldview_id: int, payload: WorldviewUpdatePayload):
    db_manager = DatabaseManager(db_name=DB_FILE_NAME)
    novel = db_manager.get_novel_by_id(novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail=f"Novel with ID {novel_id} not found.")

    existing_worldview = db_manager.get_worldview_by_id(worldview_id)
    if not existing_worldview or existing_worldview['novel_id'] != novel_id:
        raise HTTPException(status_code=404, detail=f"Worldview with ID {worldview_id} not found for novel {novel_id}.")

    try:
        success = db_manager.update_worldview(worldview_id, payload.description_text)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update worldview in database.")

        updated_worldview_data = db_manager.get_worldview_by_id(worldview_id)
        if not updated_worldview_data:
             raise HTTPException(status_code=500, detail="Failed to retrieve updated worldview.")
        return WorldviewResponse(**updated_worldview_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred while updating worldview: {str(e)}")


# --- Main Application Execution ---
if __name__ == "__main__":
    # Create a default DB if it doesn't exist for local testing
    print(f"Initializing database '{DB_FILE_NAME}' for API...")
    _ = DatabaseManager(db_name=DB_FILE_NAME) # This will create tables if they don't exist

    print("Starting FastAPI server with Uvicorn...")
    print(f"Run with: uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000")
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)

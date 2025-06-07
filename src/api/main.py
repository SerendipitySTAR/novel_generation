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
    # Conceptually update status to "processing"
    # db_manager_task = DatabaseManager(db_name=db_name_for_task)
    # db_manager_task.update_novel_status(novel_id, "processing", "Workflow started.")

    try:
        manager = WorkflowManager(db_name=db_name_for_task, mode=user_input_data.get("mode", "auto"))
        final_state: NovelWorkflowState = manager.run_workflow(user_input_data)

        if final_state.get("error_message"):
            print(f"Background task for novel_id {novel_id} completed with error: {final_state['error_message']}")
            # Conceptually update status to "failed" and store error
            # db_manager_task.update_novel_status(novel_id, "failed", final_state['error_message'], final_state.get('history', []))
        else:
            print(f"Background task for novel_id {novel_id} completed successfully.")
            # Conceptually update status to "completed"
            # db_manager_task.update_novel_status(novel_id, "completed", "Workflow finished.", final_state.get('history', []))

    except Exception as e:
        print(f"Critical error in background task for novel_id {novel_id}: {e}")
        # import traceback; traceback.print_exc()
        # Conceptually update status to "system_error"
        # db_manager_task.update_novel_status(novel_id, "system_error", str(e))
    finally:
        print(f"Background task finished for novel_id: {novel_id}")
        # Here, you could also store the final_state.json or relevant parts if needed for detailed status
        # For example: with open(f"novel_{novel_id}_final_state.json", "w") as f: json.dump(final_state, f, indent=2, default=str)


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

    # Simplified status logic for now:
    # This part needs to be more robust by querying a dedicated status field
    # updated by the background task.
    status = "processing" # Default assumption if no other info
    current_step = "details_not_available_yet"
    last_history = None
    error_msg = None

    # Conceptual: Query the 'status', 'current_step_details', 'error_message', 'history_log' from novel_record
    # if novel_record.get('status'): status = novel_record['status']
    # if novel_record.get('current_step_details'): current_step = novel_record['current_step_details']
    # if novel_record.get('error_message'): error_msg = novel_record['error_message']
    # if novel_record.get('history_log'): last_history = novel_record['history_log'] # e.g. last few entries

    # For this subtask, let's simulate some progress based on DB content if no explicit status field is used yet
    # This is a fallback and less ideal than the background task updating a status field.
    # if status == "processing": # Only if status is not yet "completed" or "failed" from DB
    chapters = db_manager.get_chapters_for_novel(novel_id)
    if chapters:
        status = "chapters_generated"
        current_step = f"Chapter {len(chapters)} generated."
        last_history = f"Chapter {chapters[-1].title} completed." # Mock history
    else:
        outline = db_manager.get_outline_by_id(novel_record.get("active_outline_id")) if novel_record.get("active_outline_id") else None
        if outline:
            status = "outline_generated"
            current_step = "Outline generation complete."
            last_history = "Outline created." # Mock history
        # else: status remains "processing" or could be "pending" if that was the initial DB state

    # This is where you would ideally get the status directly from the DB
    # E.g., status = novel_record.get("status", "unknown")
    # current_step = novel_record.get("current_step_details", "N/A")
    # error_message = novel_record.get("error_message")
    # For now, the above logic is a placeholder.
    # The actual "status" should be updated by the background task.

    return NovelStatusResponse(
        novel_id=novel_id,
        status=status, # This will be more accurate once background task updates DB status
        current_step=current_step,
        last_history_entry=last_history,
        error_message=error_msg
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

from fastapi import FastAPI, HTTPException
import uvicorn
from pydantic import BaseModel
from typing import List, Dict, Any, Optional # Ensure Optional is imported
import uuid # Added for conflict report endpoint

from src.orchestration.workflow_manager import WorkflowManager
# UserInput from workflow_manager is not directly used here if new Pydantic models are made

# Potentially for type hinting or direct use in a full implementation
# from src.core.models import Chapter
# from src.agents.content_integrity_agent import ContentIntegrityAgent
# from src.agents.conflict_detection_agent import ConflictDetectionAgent


# --- Pydantic Models for API Request and Response ---

class NarrativeRequestPayload(BaseModel):
    theme: str
    style_preferences: Optional[str] = "general fiction"

class NarrativeResponse(BaseModel): # Updated model
    narrative_id: Optional[int] = None
    narrative_outline: Optional[str] = None
    worldview_data: Optional[str] = None # Added worldview_data
    error_message: Optional[str] = None
    history: Optional[List[str]] = None

# New Pydantic Models
class NovelGenerationRequest(BaseModel):
    theme: str
    style_preferences: Optional[str] = "general fiction"
    chapters: int = 3 # Default to 3 chapters
    words_per_chapter: Optional[int] = 1000
    mode: Optional[str] = "human" # "human" or "auto"

class NovelGenerationResponse(BaseModel):
    novel_id: Optional[int] = None # Would be the ID from the database
    message: str
    status_url: Optional[str] = None # For async polling in a real app
    error_message: Optional[str] = None

class ChapterContentResponse(BaseModel):
    novel_id: int
    chapter_number: int
    title: Optional[str] = "N/A"
    content: Optional[str] = "Content not found or not yet generated."
    review: Optional[Dict[str, Any]] = None # From ContentIntegrityAgent
    error_message: Optional[str] = None

class ConflictReportResponse(BaseModel):
    novel_id: int
    chapter_number: int
    conflicts: Optional[List[Dict[str, Any]]] = []
    error_message: Optional[str] = None

class KnowledgeGraphResponse(BaseModel):
    novel_id: int
    graph_data: Optional[Dict[str, Any]] = {"nodes": [], "edges": []}
    error_message: Optional[str] = None


app = FastAPI(
    title="Automatic Novel Generator API",
    description="API for managing and interacting with the novel generation process.",
    version="0.1.1", # Incremented version
)

@app.get("/")
async def root():
    return {"message": "Welcome to the Automatic Novel Generator API!"}

@app.get("/healthcheck")
async def health_check():
    return {"status": "ok", "message": "API is healthy"}


@app.post("/generate/narrative_outline", response_model=NarrativeResponse)
async def generate_narrative_outline_endpoint(payload: NarrativeRequestPayload):
    print(f"API: Received request to generate narrative outline for theme: '{payload.theme}'")

    try:
        manager = WorkflowManager()
        workflow_input = {
            "theme": payload.theme,
            "style_preferences": payload.style_preferences
        }

        final_state = manager.run_workflow(workflow_input)

        # Construct response, now including worldview_data
        response_data = {
            "narrative_id": final_state.get("narrative_id"),
            "narrative_outline": final_state.get("narrative_outline"),
            "worldview_data": final_state.get("worldview_data"), # Include worldview_data
            "error_message": final_state.get("error_message"),
            "history": final_state.get("history")
        }

        if final_state.get("error_message") and not final_state.get("narrative_id"):
            print(f"API: Workflow completed with error: {final_state.get('error_message')}")
        elif final_state.get("narrative_id"):
            print(f"API: Workflow successful. Narrative ID: {final_state.get('narrative_id')}")

        return NarrativeResponse(**response_data)

    except Exception as e:
        print(f"API: Unexpected error in generate_narrative_outline_endpoint: {e}")
        # In a real app, log the full traceback e.g. using logging module
        # import traceback; traceback.print_exc();
        raise HTTPException(status_code=500, detail=f"An unexpected API error occurred.") # Generic message to client

# --- New Placeholder Endpoints ---

@app.post("/generate/full_novel", response_model=NovelGenerationResponse)
async def start_full_novel_generation(payload: NovelGenerationRequest):
    print(f"API: Received request to generate full novel: Theme='{payload.theme}', Mode='{payload.mode}'")
    # Placeholder logic:
    # In a real app, this would:
    # 1. Validate input
    # 2. Create a new novel record in the DB to get a novel_id
    # 3. Initiate the WorkflowManager.run_workflow in a background task (e.g., Celery)
    # 4. Return the novel_id and a way to check status.

    # For this placeholder, we'll simulate a synchronous start and immediate (mocked) response.
    # We won't actually run the full workflow here as it can be long.
    mock_novel_id = 123 # Simulate a new novel ID

    # Simulate passing relevant parts to WorkflowManager if it were run
    user_input_for_workflow = {
        "theme": payload.theme,
        "style_preferences": payload.style_preferences,
        "chapters": payload.chapters,
        "words_per_chapter": payload.words_per_chapter,
        "auto_mode": payload.mode == "auto"
    }
    print(f"API: Placeholder - Would run workflow with: {user_input_for_workflow}")

    # This is where you would call manager.run_workflow(user_input_for_workflow)
    # For now, just return a success message.
    return NovelGenerationResponse(
        novel_id=mock_novel_id,
        message=f"Placeholder: Novel generation started for theme '{payload.theme}' with ID {mock_novel_id}. Check status for actual progress.",
        status_url=f"/novels/{mock_novel_id}/status" # Example status URL
    )

@app.get("/novels/{novel_id}/chapters/{chapter_number}", response_model=ChapterContentResponse)
async def get_chapter_content(novel_id: int, chapter_number: int):
    print(f"API: Request for content of Novel ID {novel_id}, Chapter {chapter_number}")
    # Placeholder logic:
    # 1. Query DatabaseManager for the chapter content and its review.
    # db_manager = DatabaseManager() # Assuming a way to get a DB manager instance
    # chapter_data = db_manager.get_chapter(novel_id, chapter_number)
    # review_data = db_manager.get_chapter_review(novel_id, chapter_number) # Hypothetical

    # Mocked response for placeholder:
    if novel_id == 123 and chapter_number == 1:
        return ChapterContentResponse(
            novel_id=novel_id,
            chapter_number=chapter_number,
            title="The Beginning (Mocked)",
            content="Once upon a time, in a mocked land...",
            review={"overall_score": 8.0, "justification": "This is a mocked review."}
        )
    return ChapterContentResponse(
        novel_id=novel_id,
        chapter_number=chapter_number,
        error_message="Placeholder: Chapter not found or functionality not implemented."
    )

@app.get("/novels/{novel_id}/chapters/{chapter_number}/conflicts", response_model=ConflictReportResponse)
async def get_chapter_conflict_report(novel_id: int, chapter_number: int):
    print(f"API: Request for conflict report of Novel ID {novel_id}, Chapter {chapter_number}")
    # Placeholder logic:
    # 1. Query DatabaseManager or workflow state storage for conflict data.
    # conflict_data = db_manager.get_conflicts_for_chapter(novel_id, chapter_number) # Hypothetical

    # Mocked response:
    if novel_id == 123 and chapter_number == 1:
        # Simulate a conflict found by ConflictDetectionAgent
        mock_conflicts = [{
            "conflict_id": str(uuid.uuid4()), # Requires import uuid
            "type": "Plot Contradiction (Mocked)",
            "description": "A character was said to be asleep but was also flying a kite.",
            "severity": "Medium",
            "chapter_source": chapter_number,
            "problematic_excerpt": "He was fast asleep. Outside, he flew his kite."
        }]
        return ConflictReportResponse(novel_id=novel_id, chapter_number=chapter_number, conflicts=mock_conflicts)

    return ConflictReportResponse(
        novel_id=novel_id,
        chapter_number=chapter_number,
        error_message="Placeholder: Conflict report not available or functionality not implemented."
    )

@app.get("/novels/{novel_id}/knowledge_graph", response_model=KnowledgeGraphResponse)
async def get_novel_knowledge_graph(novel_id: int):
    print(f"API: Request for knowledge graph of Novel ID {novel_id}")
    # Placeholder logic:
    # 1. Call LoreKeeperAgent.get_knowledge_graph_data(novel_id)
    # This might involve running a mini-workflow or directly calling the agent method
    # if the agent can be instantiated with just a novel_id or db access.

    # Mocked response:
    if novel_id == 123:
        mock_graph_data = {
            "nodes": [
                {"id": "char_1", "label": "Hero (Mocked)", "type": "character"},
                {"id": "event_1", "label": "The Quest Begins (Mocked)", "type": "plot_event"}
            ],
            "edges": []
        }
        return KnowledgeGraphResponse(novel_id=novel_id, graph_data=mock_graph_data)

    return KnowledgeGraphResponse(
        novel_id=novel_id,
        error_message="Placeholder: Knowledge graph data not available or functionality not implemented."
    )


if __name__ == "__main__":
    print("Starting FastAPI server with Uvicorn...")
    print("Run with: uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000")
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)

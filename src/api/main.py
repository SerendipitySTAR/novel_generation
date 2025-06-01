from fastapi import FastAPI, HTTPException
import uvicorn
from pydantic import BaseModel
from typing import List, Dict, Any, Optional # Ensure Optional is imported

from src.orchestration.workflow_manager import WorkflowManager
# UserInput from workflow_manager is not directly used here if new Pydantic models are made

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


if __name__ == "__main__":
    print("Starting FastAPI server with Uvicorn...")
    print("Run with: uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000")
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)

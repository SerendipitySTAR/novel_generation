from fastapi import FastAPI
import uvicorn

# Create a FastAPI application instance
app = FastAPI(
    title="Automatic Novel Generator API",
    description="API for managing and interacting with the novel generation process.",
    version="0.0.1", # Start with an early version
)

@app.get("/")
async def root():
    return {"message": "Welcome to the Automatic Novel Generator API!"}

@app.get("/healthcheck")
async def health_check():
    """
    Simple health check endpoint to confirm the API is running.
    """
    return {"status": "ok", "message": "API is healthy"}

# Placeholder for future API routers
# from .routers import project_router, generation_router # Example
# app.include_router(project_router.router, prefix="/projects", tags=["Projects"])
# app.include_router(generation_router.router, prefix="/generate", tags=["Generation"])


if __name__ == "__main__":
    # This block allows running the app directly with uvicorn for development.
    # Command to run from the project root directory (where .env might be):
    # python -m src.api.main
    # Or, more commonly, using uvicorn directly:
    # uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
    print("Starting FastAPI server with Uvicorn...")
    print("Run with: uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000")
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)

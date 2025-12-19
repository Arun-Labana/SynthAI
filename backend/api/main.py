"""
FastAPI Main Application.

Entry point for the Autonomous Tech Lead API server.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.api.routes import router
from backend.api.websocket import websocket_endpoint


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    
    Handles startup and shutdown events.
    """
    # Startup
    settings = get_settings()
    print(f"⚡ SynthAI starting...")
    print(f"   - API: http://{settings.api_host}:{settings.api_port}")
    print(f"   - Docs: http://{settings.api_host}:{settings.api_port}/docs")
    
    # Initialize database
    try:
        from backend.database.connection import init_db
        init_db()
        print(f"   - Database: ✅ Connected")
    except Exception as e:
        print(f"   - Database: ❌ Error - {e}")
    
    # Verify critical dependencies
    try:
        # Check Docker availability
        from backend.sandbox.docker_runner import DockerSandbox
        sandbox = DockerSandbox()
        docker_status = sandbox.health_check()
        if docker_status.get("docker_available"):
            print(f"   - Docker: ✅ Available (v{docker_status.get('docker_version', 'unknown')})")
        else:
            print(f"   - Docker: ⚠️ Not available - sandbox execution will fail")
    except Exception as e:
        print(f"   - Docker: ❌ Error - {e}")
    
    yield
    
    # Shutdown
    print("👋 SynthAI shutting down...")


# Create FastAPI application
app = FastAPI(
    title="SynthAI API",
    description="""
    ⚡ **SynthAI** - Multi-Agent Code Synthesis Platform
    
    Synthesize production-ready code from natural language specifications.
    
    ## Workflow
    
    1. **Create Task**: Describe what you want to build
    2. **PM Agent**: Generates technical specification
    3. **Dev Agent**: Synthesizes code using RAG context
    4. **QA Agent**: Generates comprehensive test suite
    5. **Sandbox**: Executes code in Docker isolation
    6. **Reviewer**: Validates and decides next steps
    7. **Human Approval**: You review and approve/reject
    8. **GitHub PR**: Automatically created on approval
    """,
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",  # Vite default
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include REST API routes
app.include_router(router)


# WebSocket endpoint
@app.websocket("/ws/{task_id}")
async def websocket_route(websocket: WebSocket, task_id: str):
    """WebSocket endpoint for real-time task updates."""
    await websocket_endpoint(websocket, task_id)


# Root endpoint
@app.get("/")
async def root():
    """API root - returns basic info."""
    return {
        "name": "SynthAI",
        "tagline": "Synthesize production-ready code from natural language",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/api/v1/health",
    }


def run_server():
    """Run the API server."""
    import uvicorn
    
    settings = get_settings()
    
    uvicorn.run(
        "backend.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )


if __name__ == "__main__":
    run_server()


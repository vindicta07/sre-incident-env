"""FastAPI Application Factory for SRE Incident Environment"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import env_routes, task_routes, grader_routes, baseline_routes


# Global environment instance (per-session in production you'd use proper state management)
env_state = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    env_state["environments"] = {}
    yield
    # Shutdown
    env_state.clear()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application"""
    app = FastAPI(
        title="SRE Incident Environment",
        description=(
            "A real-world SRE Incident Response environment for training AI agents "
            "to diagnose and resolve production outages."
        ),
        version="1.0.0",
        lifespan=lifespan,
        docs_url=None,      # Disable Swagger UI
        redoc_url="/",    # Serve ReDoc at root
    )

    # Add CORS middleware for HuggingFace Spaces
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(env_routes.router, tags=["Environment"])
    app.include_router(task_routes.router, tags=["Tasks"])
    app.include_router(grader_routes.router, tags=["Grader"])
    app.include_router(baseline_routes.router, tags=["Baseline"])

    # Root endpoint removed; ReDoc will be served at '/'

    @app.get("/health", tags=["Health"])
    async def health():
        """Health check endpoint"""
        return {"status": "healthy"}

    return app


# Create the app instance
app = create_app()


def run_server():
    """Entry point for running the server via CLI"""
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=7860, reload=True)

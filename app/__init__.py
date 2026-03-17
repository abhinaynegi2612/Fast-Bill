"""
Main FastAPI Application
Bill Analyzer API - Production-ready setup
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from pathlib import Path
import logging

from app.core.config import settings
from app.api.routes import router

# Setup logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    logger.info(f"Starting {settings.APP_NAME} v{settings.VERSION}")
    
    # Startup
    logger.info(f"Upload directory: {settings.UPLOAD_DIR}")
    logger.info(f"Temp directory: {settings.TEMP_DIR}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="Production-level Bill Analyzer with Forgery Detection and Intelligent Query",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Include API routers
app.include_router(router, prefix="/api/v1", tags=["Bill Analyzer"])


@app.get("/")
async def dashboard():
    """Serve the dashboard HTML"""
    dashboard_file = static_dir / "index.html"
    if dashboard_file.exists():
        return FileResponse(dashboard_file)
    return {"app": settings.APP_NAME, "version": settings.VERSION, "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        workers=1 if settings.DEBUG else 2
    )

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import logging
from contextlib import asynccontextmanager

from app.core.logging import setup_logging
from app.routers import crawl, generate, questions, dashboard, snippets
from app.routers.chrome_extension import router as chrome_extension_router
from app.routers import rag as rag_router
from app.services.scheduler import init_scheduler

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Initialize scheduler on startup
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Job Scout AI")
    scheduler = init_scheduler()
    scheduler.start()
    yield
    # Shutdown
    logger.info("Shutting down Job Scout AI")
    scheduler.shutdown()

app = FastAPI(
    title="Job Scout AI",
    description="AI-powered job discovery and application tracker",
    version="0.1.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", 
        "http://localhost:8000",
        "chrome-extension://*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(crawl.router, prefix="/api/crawl", tags=["Crawler"])
app.include_router(generate.router, prefix="/api/generate", tags=["Generator"])
app.include_router(questions.router, prefix="/api/questions", tags=["Q&A"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(chrome_extension_router, prefix="/api/extension", tags=["Chrome Extension"])
app.include_router(rag_router.router, prefix="/api/rag", tags=["RAG"])
app.include_router(snippets.router, prefix="/api/snippets", tags=["Snippets"])

# Health check
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "Job Scout AI Backend",
        "version": "0.1.0"
    }

@app.get("/")
async def root():
    return {
        "message": "Welcome to Job Scout AI Backend",
        "docs": "/docs",
        "openapi_schema": "/openapi.json"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)



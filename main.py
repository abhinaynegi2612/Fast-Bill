"""
Main entry point for Bill Analyzer API
"""
from app import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="localhost",
        port=8000,
        reload=True,
        workers=1
    )

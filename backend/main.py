import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
from routers import auth, admin, doctor, patient

app = FastAPI(
    title="Healthcare Portal API",
    description="Backend API for Doctor-Patient-Admin Healthcare Portal",
    version="1.0.0"
)

# Configure CORS for frontend access
# In development: allow all origins. In production: restrict to deployed URL
env = os.getenv("ENV", "development")
if env == "production":
    # Get the deployed URL from environment (set this in Render)
    frontend_url = os.getenv("FRONTEND_URL", "https://your-app.onrender.com")
    allowed_origins = [frontend_url, "https://your-app.onrender.com"]
else:
    allowed_origins = ["*"]  # Development: allow localhost and all origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(doctor.router)
app.include_router(patient.router)

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "message": "Healthcare Portal API is running successfully"}

# Serve the frontend (HTML/CSS/JS) from the same server
# Use absolute path to handle both local and production environments
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(os.path.dirname(BACKEND_DIR), "frontend")

# If frontend directory doesn't exist, try alternative paths
if not os.path.exists(FRONTEND_DIR):
    # Try from root if running from backend directory
    FRONTEND_DIR = os.path.join("/app", "frontend") if os.path.exists("/app") else "frontend"

app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

if __name__ == "__main__":
    # In production (Render), host must be 0.0.0.0 to accept external connections
    # Use PORT env var if set (Render provides this), otherwise default to 8000
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    reload = os.getenv("ENV", "development") == "development"

    uvicorn.run("main:app", host=host, port=port, reload=reload)

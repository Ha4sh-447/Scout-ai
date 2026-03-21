from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.auth.router import router as auth_router
from api.users.router import router as users_router
from api.jobs.router import router as jobs_router
from api.scrapers.router import router as scrapers_router
import os
print(f"DEBUG: API REDIS_URL: {os.environ.get('REDIS_URL')}")
app = FastAPI(
    title="Agentic Job Finder API",
    description="Backend API",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(jobs_router)
app.include_router(scrapers_router)

@app.get("/debug/env")
async def debug_env():
    import os
    s = os.environ.get("JWT_SECRET_KEY", "MISSING")
    masked_s = f"{s[0]}...{s[-1]}" if len(s) > 2 else s
    return {
        "REDIS_URL": os.environ.get("REDIS_URL"), 
        "DATABASE_URL": os.environ.get("DATABASE_URL"),
        "JWT_SECRET_KEY_MASKED": masked_s
    }

@app.get("/")
async def root():
    return {
        "message": "Get a job.",
        "docs": "/docs",
        "status": "online"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8001, reload=True)

import os
import sys
from contextlib import asynccontextmanager

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import api_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db_url = os.environ.get("QUERYNEST_DATABASE_URL")
    mode = os.environ.get("QUERYNEST_STORAGE_MODE", "supabase")

    if db_url:
        from core.index import get_vector_store

        store = get_vector_store()
        store.setup()

        host = db_url.split("@")[-1].split("/")[0] if "@" in db_url else "unknown"
        print("\n  QueryNest API  —  http://localhost:8000")
        print(f"  Storage:       pgvector ({mode}) @ {host}\n")
    else:
        print("\n  QueryNest API  —  http://localhost:8000")
        print("  Storage:       local (in-memory, no database)\n")

    yield


app = FastAPI(title="QueryNest API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

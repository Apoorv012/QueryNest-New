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
    from core.index.config import get_storage_mode, is_store_configured

    mode = get_storage_mode()

    if is_store_configured():
        from core.index import get_vector_store

        store = get_vector_store()
        store.setup()

        db_url = os.environ.get(
            "QUERYNEST_LOCAL_DATABASE_URL" if mode == "local" else "QUERYNEST_DATABASE_URL"
        )
        host = db_url.split("@")[-1].split("/")[0] if db_url and "@" in db_url else "unknown"
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

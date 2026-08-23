"""The public, internet-facing QueryNest API.

Deliberately a separate FastAPI app from core.api.main:app, not a flag on it.
It mounts only health + golden-user search + golden-user PDF fetch — upload,
eval seeding, and document mutation are simply never imported here, so there
is no route to lock down and no way for public traffic to reach them.
"""

import os
import sys
from contextlib import asynccontextmanager

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes.health import router as health_router
from .routes.public_documents import router as public_documents_router
from .routes.public_search import router as public_search_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from core.index.config import is_store_configured

    if is_store_configured():
        from core.index import get_vector_store

        get_vector_store().setup()

    yield


app = FastAPI(title="QueryNest Public API", lifespan=lifespan)

_allowed_origins = [
    o.strip() for o in os.environ.get("QUERYNEST_DEMO_ORIGIN", "").split(",") if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

app.include_router(health_router)
app.include_router(public_search_router)
app.include_router(public_documents_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8001)

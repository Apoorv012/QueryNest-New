import sys

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import api_router

app = FastAPI(title="QueryNest API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

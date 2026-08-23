from fastapi import APIRouter

router = APIRouter()


@router.get("/")
def root():
    return {"name": "QueryNest API", "version": "0.1.0"}


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/check-backend")
def check_backend():
    """Same payload as /health, under a name ad-blockers don't filter.

    Browser extensions (Brave Shields included) commonly block generic paths
    like /health, /ping, /beacon as tracking pings — the request never
    leaves the browser, so the frontend's connectivity check silently fails
    even though the API is reachable. See apps/demo/src/demo/lib/api.ts.
    """
    return {"status": "ok"}

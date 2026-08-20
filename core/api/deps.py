from __future__ import annotations

import re

from fastapi import HTTPException

# user_id reaches the filesystem (upload dir, PDF path) so it must be
# constrained to a safe charset before it is used to build any path.
USER_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def validate_user_id(user_id: str = "dev-user") -> str:
    """Shared FastAPI dependency: reject any user_id that isn't a plain token.

    Used by every route (documents, upload) that turns user_id into a
    filesystem path component, to close the path-traversal hole where
    values like ".." or "../.." escape UPLOAD_DIR.
    """
    if not USER_ID_PATTERN.match(user_id):
        raise HTTPException(status_code=400, detail="Invalid user_id")
    return user_id

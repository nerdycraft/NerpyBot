"""Auth routes — login, callback, me."""

from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login")
async def login():
    """Redirect to Discord OAuth2 — implemented in Task 7."""
    return {"message": "not yet implemented"}

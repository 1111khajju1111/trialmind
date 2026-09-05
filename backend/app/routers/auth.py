from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app import auth

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str

    class Config:
        extra = "forbid"


@router.post("/login")
def login(body: LoginRequest):
    user = auth.verify_credentials(body.username, body.password)
    if not user:
        # 401, not a 200 with an {"error": ...} body, so the frontend (and
        # any other client) can reliably distinguish "login failed" from a
        # successful response without having to inspect the payload shape.
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    username = body.username.strip().lower()
    token = auth.issue_token(username, user["role"])
    return {
        "token": token,
        "username": username,
        "display_name": user["display_name"],
        "role": user["role"],
    }


@router.post("/logout")
def logout(session: dict = Depends(auth.get_current_session)):
    # Find and drop the token that resolved to this session.
    for token, s in list(auth.ACTIVE_SESSIONS.items()):
        if s is session:
            auth.revoke_token(token)
            break
    return {"status": "logged out"}


@router.get("/me")
def me(session: dict = Depends(auth.get_current_session)):
    user = auth.DEMO_USERS.get(session["username"])
    return {
        "username": session["username"],
        "role": session["role"],
        "display_name": user["display_name"] if user else session["username"],
    }

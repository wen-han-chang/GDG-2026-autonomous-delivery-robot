from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register")
def register_user(email: str, password: str):
    return {"token": "demo-token-123", "user": {"id": "u1", "email": email}}

@router.post("/login")
def login_user(email: str, password: str):
    return {"token": "demo-token-123", "user": {"id": "u1", "email": email}}

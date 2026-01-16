from fastapi import APIRouter, Header, HTTPException

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/me")
def get_current_user(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {"id": "u1", "email": "demo@test.com"}

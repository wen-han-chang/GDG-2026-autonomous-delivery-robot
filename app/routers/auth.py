import os
from fastapi import APIRouter, HTTPException, status, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from app.models import UserCreate, UserLogin
from app.sql_models import User
from app.database import get_db

load_dotenv()

router = APIRouter(prefix="/auth", tags=["auth"])

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("JWT_SECRET_KEY 環境變數未設定")
REFRESH_SECRET_KEY = os.getenv("REFRESH_TOKEN_SECRET_KEY", SECRET_KEY)

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7

IS_PRODUCTION = os.getenv("ENVIRONMENT", "development") == "production"
COOKIE_SECURE = IS_PRODUCTION
# dev: samesite="none" 允許 Vite:5173 跨域 POST 帶 cookie
# prod: samesite="lax"（nginx 反代後同源）
# 長期建議：前端設定 Vite proxy，即可統一使用 samesite="lax"
COOKIE_SAMESITE = "lax" if IS_PRODUCTION else "none"

ACCESS_COOKIE_NAME = "access_token"
REFRESH_COOKIE_NAME = "refresh_token"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, REFRESH_SECRET_KEY, algorithm=ALGORITHM)


def _set_auth_cookies(response, access_token: str, refresh_token: str) -> None:
    response.set_cookie(
        key=ACCESS_COOKIE_NAME,
        value=access_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/auth/refresh",
    )


@router.post("/register")
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == user_in.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="此 Email 已經註冊過")

    new_user = User(
        email=user_in.email,
        username=user_in.name,
        hashed_password=get_password_hash(user_in.password),
        created_at=datetime.utcnow()
    )
    db.add(new_user)
    db.flush()

    access_token = create_access_token(data={"sub": new_user.email})
    refresh_token = create_refresh_token(data={"sub": new_user.email})

    new_user.refresh_token = refresh_token
    db.commit()
    db.refresh(new_user)

    response = JSONResponse(content={
        "success": True,
        "user": {
            "id": new_user.email,
            "email": new_user.email,
            "name": new_user.username,
            "createdAt": new_user.created_at.isoformat(),
        }
    })
    _set_auth_cookies(response, access_token, refresh_token)
    return response


@router.post("/token", include_in_schema=False)
def login_form(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Swagger UI OAuth2 form 相容端點"""
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="帳號或密碼錯誤")
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/login")
def login(user_in: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == user_in.email).first()
    if not user:
        raise HTTPException(status_code=400, detail="帳號或密碼錯誤")

    if not verify_password(user_in.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="帳號或密碼錯誤")

    access_token = create_access_token(data={"sub": user.email})
    refresh_token = create_refresh_token(data={"sub": user.email})

    user.refresh_token = refresh_token
    db.commit()

    response = JSONResponse(content={
        "success": True,
        "user": {
            "id": user.email,
            "email": user.email,
            "name": user.username,
            "createdAt": user.created_at.isoformat(),
        }
    })
    _set_auth_cookies(response, access_token, refresh_token)
    return response


@router.post("/refresh")
def refresh_tokens(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="refresh token 不存在")

    credentials_exception = HTTPException(status_code=401, detail="refresh token 無效或已過期")
    try:
        payload = jwt.decode(token, REFRESH_SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise credentials_exception
        email: str = payload.get("sub")
        if not email:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise credentials_exception

    if user.refresh_token != token:
        # 偵測到 replay attack，清除所有 session
        user.refresh_token = None
        db.commit()
        raise HTTPException(status_code=401, detail="refresh token 已被使用，請重新登入")

    new_access_token = create_access_token(data={"sub": email})
    new_refresh_token = create_refresh_token(data={"sub": email})

    user.refresh_token = new_refresh_token
    db.commit()

    response = JSONResponse(content={"success": True})
    _set_auth_cookies(response, new_access_token, new_refresh_token)
    return response


@router.post("/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get(REFRESH_COOKIE_NAME)
    if token:
        try:
            payload = jwt.decode(token, REFRESH_SECRET_KEY, algorithms=[ALGORITHM])
            email = payload.get("sub")
            if email:
                user = db.query(User).filter(User.email == email).first()
                if user:
                    user.refresh_token = None
                    db.commit()
        except JWTError:
            pass

    response = JSONResponse(content={"success": True})
    response.delete_cookie(key=ACCESS_COOKIE_NAME, path="/", samesite=COOKIE_SAMESITE)
    response.delete_cookie(key=REFRESH_COOKIE_NAME, path="/auth/refresh", samesite=COOKIE_SAMESITE)
    return response

import os
from fastapi import APIRouter, HTTPException, status, Depends
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from dotenv import load_dotenv
from app.models import UserCreate, UserLogin, UserResponse, Token
from app.state import fake_users_db, fake_orders_db # 引入模擬資料庫

load_dotenv()

router = APIRouter(prefix="/auth", tags=["auth"])

# --- 設定 ---
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("JWT_SECRET_KEY 環境變數未設定")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 # Token 有效期 1 天

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- 工具函式 ---
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# --- API ---

@router.post("/register")
def register(user_in: UserCreate):
    # 1. 檢查 Email 是否已存在
    if user_in.email in fake_users_db:
        raise HTTPException(status_code=400, detail="此 Email 已經註冊過")
    
    # 2. 建立新用戶
    user_id = f"u_{int(datetime.now().timestamp())}"
    new_user = {
        "id": user_id,
        "email": user_in.email,
        "name": user_in.name,
        "hashed_password": get_password_hash(user_in.password),
        "createdAt": datetime.now().isoformat()
    }
    
    # 3. 存入 "資料庫"
    fake_users_db[user_in.email] = new_user
    
    # 4. 產生 Token
    access_token = create_access_token(data={"sub": user_in.email})
    
    # 5. 回傳格式 (符合前端 authStore.js 預期)
    return {
        "success": True,
        "token": access_token,
        "user": {
            "id": new_user["id"],
            "email": new_user["email"],
            "name": new_user["name"],
            "createdAt": new_user["createdAt"]
        }
    }

@router.post("/login")
def login(user_in: UserLogin):
    # 1. 找用戶
    user = fake_users_db.get(user_in.email)
    if not user:
        raise HTTPException(status_code=400, detail="帳號或密碼錯誤")
    
    # 2. 驗證密碼
    if not verify_password(user_in.password, user["hashed_password"]):
        raise HTTPException(status_code=400, detail="帳號或密碼錯誤")
    
    # 3. 產生 Token
    access_token = create_access_token(data={"sub": user["email"]})
    
    # 4. 回傳
    return {
        "success": True,
        "token": access_token,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "createdAt": user["createdAt"]
        }
    }
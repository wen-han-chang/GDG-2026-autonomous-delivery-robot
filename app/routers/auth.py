import os
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordRequestForm
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from dotenv import load_dotenv
from sqlalchemy.orm import Session # 👈 新增：用於資料庫連線

# 引入你的 SQL 模型與資料庫依賴
from app.models import UserCreate, UserLogin
from app.sql_models import User # 👈 這是 SQL 的 User 表格
from app.database import get_db # 👈 這是取得資料庫連線的工具

load_dotenv()

router = APIRouter(prefix="/auth", tags=["auth"])

# --- 設定 ---
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("JWT_SECRET_KEY 環境變數未設定")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15

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

# --- API (已全面改寫為 SQL 版本) ---

@router.post("/register")
def register(user_in: UserCreate, db: Session = Depends(get_db)): # 👈 注入 db
    # 1. 檢查 Email 是否已存在 (查 SQL)
    existing_user = db.query(User).filter(User.email == user_in.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="此 Email 已經註冊過")
    
    # 2. 建立新用戶 (SQL Model)
    # 注意：這裡要把 Pydantic 的 name 轉成 SQL Model 的 username
    new_user = User(
        email=user_in.email,
        username=user_in.name,  
        hashed_password=get_password_hash(user_in.password),
        created_at=datetime.utcnow()
    )
    
    # 3. 存入真正的資料庫
    db.add(new_user)
    db.commit()      # 👈 關鍵：提交變更
    db.refresh(new_user) # 刷新以取得 ID 等自動生成的欄位
    
    # 4. 產生 Token
    access_token = create_access_token(data={"sub": new_user.email})
    
    # 5. 回傳格式
    return {
        "success": True,
        "token": access_token,
        "user": {
            "id": new_user.email, # 在 SQL 模型中 email 是 primary key
            "email": new_user.email,
            "name": new_user.username,
            "createdAt": new_user.created_at.isoformat()
        }
    }

@router.post("/token", include_in_schema=False)
def login_form(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Swagger UI OAuth2 form 相容端點"""
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="帳號或密碼錯誤")
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/login")
def login(user_in: UserLogin, db: Session = Depends(get_db)): # 👈 注入 db
    # 1. 找用戶 (查 SQL)
    user = db.query(User).filter(User.email == user_in.email).first()
    if not user:
        raise HTTPException(status_code=400, detail="帳號或密碼錯誤")
    
    # 2. 驗證密碼
    if not verify_password(user_in.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="帳號或密碼錯誤")
    
    # 3. 產生 Token
    access_token = create_access_token(data={"sub": user.email})
    
    # 4. 回傳
    return {
        "success": True,
        "token": access_token,
        "user": {
            "id": user.email,
            "email": user.email,
            "name": user.username,
            "createdAt": user.created_at.isoformat()
        }
    }
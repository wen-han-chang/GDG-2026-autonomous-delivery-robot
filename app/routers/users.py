from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from typing import List
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.routers.auth import SECRET_KEY, ALGORITHM, verify_password, get_password_hash
from app.models import UserResponse, UserUpdate, OrderHistoryItem
from app.database import get_db
from app.sql_models import User, OrderDB


class AvatarUpdate(BaseModel):
    avatar: str  # base64 data URL

router = APIRouter(prefix="/users", tags=["users"])

# --- JWT 驗證依賴 ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="無法驗證憑證",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # 從資料庫查詢使用者
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception
    return user

# --- API ---

# 3. 取得當前用戶資訊
@router.get("/me", response_model=UserResponse)
def read_users_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.email,
        "email": current_user.email,
        "name": current_user.username,
        "createdAt": current_user.created_at.isoformat(),
        "avatar": current_user.avatar
    }

# 4. 修改姓名或密碼
@router.put("/me")
def update_user_me(
    update_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 修改姓名
    if update_data.name:
        current_user.username = update_data.name

    # 修改密碼
    if update_data.new_password:
        if not update_data.old_password:
             raise HTTPException(status_code=400, detail="請提供舊密碼以進行驗證")

        if not verify_password(update_data.old_password, current_user.hashed_password):
             raise HTTPException(status_code=400, detail="舊密碼錯誤")

        current_user.hashed_password = get_password_hash(update_data.new_password)

    db.commit()
    db.refresh(current_user)

    return {
        "success": True,
        "user": {
            "id": current_user.email,
            "email": current_user.email,
            "name": current_user.username,
            "createdAt": current_user.created_at.isoformat(),
            "avatar": current_user.avatar
        }
    }


# 6. 更新頭像
@router.put("/me/avatar")
def update_avatar(
    body: AvatarUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    current_user.avatar = body.avatar
    db.commit()
    db.refresh(current_user)
    return {
        "success": True,
        "avatar": current_user.avatar
    }

# 5. 取得訂單歷史
@router.get("/me/orders", response_model=List[OrderHistoryItem])
def get_my_orders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 從資料庫查詢該使用者的訂單
    orders = db.query(OrderDB).filter(OrderDB.user_email == current_user.email).all()

    # 轉換成前端需要的格式
    result = []
    for order in orders:
        result.append({
            "id": order.id,
            "date": order.created_at.strftime("%Y-%m-%d") if order.created_at else "",
            "store": order.store_name or "",
            "items": order.items or [],
            "total": int(order.total_amount) if order.total_amount else 0,
            "status": "已完成" if order.status == "DELIVERED" else "處理中"
        })

    return result

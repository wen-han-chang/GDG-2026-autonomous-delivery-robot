from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from typing import List
from app.routers.auth import SECRET_KEY, ALGORITHM, verify_password, get_password_hash
from app.models import UserResponse, UserUpdate, OrderHistoryItem
from app.state import fake_users_db, fake_orders_db

router = APIRouter(prefix="/users", tags=["users"])

# --- JWT 驗證依賴 ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def get_current_user(token: str = Depends(oauth2_scheme)):
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
    
    user = fake_users_db.get(email)
    if user is None:
        raise credentials_exception
    return user

# --- API ---

# 3. 取得當前用戶資訊
@router.get("/me", response_model=UserResponse)
def read_users_me(current_user: dict = Depends(get_current_user)):
    return current_user

# 4. 修改姓名或密碼 (支援前端 Profile.jsx 的呼叫)
@router.put("/me")
def update_user_me(update_data: UserUpdate, current_user: dict = Depends(get_current_user)):
    email = current_user["email"]
    
    # 修改姓名
    if update_data.name:
        fake_users_db[email]["name"] = update_data.name
        
    # 修改密碼 (如果有傳 old_password 和 new_password)
    if update_data.new_password:
        if not update_data.old_password:
             raise HTTPException(status_code=400, detail="請提供舊密碼以進行驗證")
        
        if not verify_password(update_data.old_password, current_user["hashed_password"]):
             raise HTTPException(status_code=400, detail="舊密碼錯誤")
             
        fake_users_db[email]["hashed_password"] = get_password_hash(update_data.new_password)
    
    # 回傳更新後的 user 物件
    updated_user = fake_users_db[email]
    return {
        "success": True, 
        "user": {
            "id": updated_user["id"],
            "email": updated_user["email"],
            "name": updated_user["name"],
            "createdAt": updated_user["createdAt"]
        }
    }

# 5. 取得訂單歷史
@router.get("/me/orders", response_model=List[OrderHistoryItem])
def get_my_orders(current_user: dict = Depends(get_current_user)):
    # 過濾出屬於目前登入者的訂單
    my_orders = [
        order for order in fake_orders_db 
        if order["user_email"] == current_user["email"]
    ]
    return my_orders
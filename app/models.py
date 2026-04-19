from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Literal
from datetime import datetime

# ==========================================
# 1. 地圖與機器人導航 (保留原本的)
# ==========================================
class Node(BaseModel):
    id: str
    x: float
    y: float

class Edge(BaseModel):
    from_: str = Field(alias="from")
    to: str
    bidirectional: bool = True
    length: Optional[float] = None  # cm, optional

class MapData(BaseModel):
    map_id: str
    unit: Literal["cm", "m"] = "cm"
    nodes: List[Node]
    edges: List[Edge]

class CreateOrderReq(BaseModel):
    map_id: str
    # 新格式：提供 store_id，系統自動推導 from_node（店家節點）與 to_node（HOME）
    store_id: Optional[str] = None
    # 舊格式（向後相容）：直接指定節點
    from_node: Optional[str] = None
    to_node: Optional[str] = None
    algorithm: Literal["dijkstra", "astar"] = "dijkstra"
    # 購物車資訊 (可選，用於訂單歷史)
    store_name: Optional[str] = None
    items: Optional[List[str]] = None  # ["招牌便當 x1", "紅茶 x2"]
    total: Optional[int] = None
    user_email: Optional[str] = None

class CreateOrderResp(BaseModel):
    order_id: str
    map_id: str
    route: List[str]
    total_distance_cm: float
    eta_sec: float

class Telemetry(BaseModel):
    robot_id: str
    order_id: str
    node: str
    progress: float = Field(ge=0.0, le=1.0)
    speed: float = Field(gt=0.0)  # cm/s
    state: Literal["IDLE", "ASSIGNED", "MOVING", "ARRIVED", "DELIVERED"] = "MOVING"


# ==========================================
# 2. 商店與商品 (新增的)
# ==========================================
class StoreBase(BaseModel):
    id: str
    name: str
    description: str
    category: str
    rating: float
    deliveryTime: str
    image: str
    location_node: str

class ProductBase(BaseModel):
    id: str
    store_id: str
    name: str
    price: int
    description: str
    image: str


# ==========================================
# 3. 使用者與認證 (Auth & User)
# ==========================================
# Token 相關
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

# 使用者基礎模型
class UserBase(BaseModel):
    email: EmailStr
    name: str

# 註冊用
class UserCreate(UserBase):
    password: str

# 登入用
class UserLogin(BaseModel):
    email: EmailStr
    password: str

# 回傳給前端用 (不含密碼)
class UserResponse(UserBase):
    id: str
    createdAt: str  # 前端是用 String (ISO format)
    avatar: Optional[str] = None

# 修改資料用
class UserUpdate(BaseModel):
    name: Optional[str] = None
    old_password: Optional[str] = None
    new_password: Optional[str] = None


# ==========================================
# 4. 訂單歷史
# ==========================================
class OrderHistoryItem(BaseModel):
    id: str
    date: str       # "2026-01-18"
    store: str      # "讚野烤肉飯"
    items: List[str] # ["招牌便當 x1", "紅茶 x2"]
    total: int
    status: str     # "已完成"
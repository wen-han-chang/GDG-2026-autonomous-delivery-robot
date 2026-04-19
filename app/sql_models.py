from sqlalchemy import Column, Integer, String, DateTime, Float, JSON, ForeignKey
from .database import Base
from datetime import datetime

# 1. 使用者模型
class User(Base):
    __tablename__ = "users"

    email = Column(String, primary_key=True, index=True)
    username = Column(String)
    hashed_password = Column(String)
    name = Column(String) # 補齊註冊需要的 name 欄位
    created_at = Column(DateTime, default=datetime.utcnow)
    avatar = Column(String, nullable=True)  # base64 圖片資料

# 2. 店家模型
class StoreDB(Base):
    __tablename__ = "stores"

    id = Column(String, primary_key=True, index=True)
    name = Column(String)
    description = Column(String)
    category = Column(String)
    rating = Column(Float)
    deliveryTime = Column(String)
    image = Column(String)
    location_node = Column(String)

# 3. 商品模型
class ProductDB(Base):
    __tablename__ = "products"

    id = Column(String, primary_key=True, index=True)
    store_id = Column(String, ForeignKey("stores.id"))
    name = Column(String)
    price = Column(Integer)
    description = Column(String)
    image = Column(String)

# 4. 訂單模型
class OrderDB(Base):
    __tablename__ = "orders"

    id = Column(String, primary_key=True, index=True)
    map_id = Column(String, index=True)
    status = Column(String, default="CREATED")
    created_at = Column(DateTime, default=datetime.utcnow)

    # 導航數據
    total_distance_cm = Column(Float)
    eta_sec = Column(Float)
    route = Column(JSON) 

    # 訂單商業邏輯
    user_email = Column(String, index=True)
    store_name = Column(String)
    items = Column(JSON)
    total_amount = Column(Float)
    assigned_robot_id = Column(String, nullable=True, index=True)


# 5. 小車狀態模型（持久化 GlobalPlannerState）
class RobotStateDB(Base):
    __tablename__ = "robot_states"

    robot_id = Column(String, primary_key=True, index=True)
    current_node = Column(String)
    next_deliver_k = Column(Integer, default=1)
    picked_mask = Column(Integer, default=0)
    plan_actions = Column(JSON, default=list)
    plan_stops = Column(JSON, default=list)
    last_plan_cost = Column(Integer, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

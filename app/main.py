from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import os
import uuid
import json
from pathlib import Path

# 資料庫相關
from .database import engine, Base, get_db
from .sql_models import OrderDB

# Pydantic Models & Logic
from .models import MapData, CreateOrderReq, CreateOrderResp
from .graph import build_graph, dijkstra, astar
from .services import estimate_eta_sec
from .state import MAP_STORE, GRAPH_STORE

# Router
from .routers import stores, products, auth, users
from .routers.users import get_current_user
from .ws import ws_router

app = FastAPI(title="ESP32 Car Backend")

# --- CORS 設定 ---
allowed_origins = os.getenv(
    "ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:8000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 掛載路由 ---
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(stores.router)
app.include_router(products.router)
app.include_router(ws_router)


# ===============================
# 輔助函式: 載入地圖
# ===============================
def load_map_logic(path: str = "data/map.json"):
    """讀取 JSON 並建立 Graph 的核心邏輯"""
    try:
        print(f"📍 Loading map from: {path}")
        if not Path(path).exists():
            print(f"⚠️ Map file not found: {path}")
            return

        raw = Path(path).read_text(encoding="utf-8")
        data = json.loads(raw)
        map_data = MapData.model_validate(data)
        g = build_graph(map_data)

        MAP_STORE[map_data.map_id] = map_data
        GRAPH_STORE[map_data.map_id] = g

        print(f"✅ Map loaded: {map_data.map_id} | nodes={len(map_data.nodes)} edges={len(map_data.edges)}")
    except Exception as e:
        print(f"❌ Failed to load map: {e}")


# ===============================
# Server Startup Event
# ===============================
@app.on_event("startup")
def startup_event():
    # 1. 自動建立資料表
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables created (if not exist).")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")

    # 2. 載入預設地圖
    load_map_logic()


# ===============================
# API: Create Order
# ===============================
@app.post("/orders", response_model=CreateOrderResp, tags=["訂單"])
def create_order(req: CreateOrderReq, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    # 1. 檢查地圖是否載入
    if req.map_id not in GRAPH_STORE:
        raise HTTPException(status_code=404, detail="map_id not loaded")

    g = GRAPH_STORE[req.map_id]

    # 2. 路徑規劃演算法
    try:
        if req.algorithm == "astar":
            route, dist = astar(g, req.from_node, req.to_node)
        else:
            route, dist = dijkstra(g, req.from_node, req.to_node)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    eta = estimate_eta_sec(route, dist)
    order_id = "O" + uuid.uuid4().hex[:8]

    # 3. 寫入 PostgreSQL 資料庫
    new_order = OrderDB(
        id=order_id,
        map_id=req.map_id,
        status="CREATED",
        total_distance_cm=dist,
        eta_sec=eta,
        route=route,
        user_email=current_user.email,
        store_name=req.store_name,
        items=req.items or [],
        total_amount=req.total or 0.0
    )

    try:
        db.add(new_order)
        db.commit()
        db.refresh(new_order)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    # 4. 回傳結果
    return CreateOrderResp(
        order_id=order_id,
        map_id=req.map_id,
        route=route,
        total_distance_cm=dist,
        eta_sec=eta,
    )


# ===============================
# API: Get Order
# ===============================
@app.get("/orders/{order_id}", tags=["訂單"])
def get_order(order_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    order = db.query(OrderDB).filter(OrderDB.id == order_id).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.user_email != current_user.email:
        raise HTTPException(status_code=403, detail="Forbidden")

    return order


@app.get("/")
def read_root():
    return {"message": "Autonomous Delivery Robot API is running!"}

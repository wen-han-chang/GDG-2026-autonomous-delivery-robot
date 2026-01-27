from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.routers import stores, products, auth, users, cart
from typing import Dict
import uuid
import json
from pathlib import Path

from .models import MapData, CreateOrderReq, CreateOrderResp
from .graph import build_graph, dijkstra, astar
from .services import estimate_eta_sec
from .ws import ws_router
from .state import MAP_STORE, GRAPH_STORE, ORDER_STORE, fake_orders_db
from datetime import datetime

app = FastAPI(title="ESP32 Car Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 開發階段允許所有來源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 掛載路由 (這是關鍵！) ---
app.include_router(auth.router)      # 登入註冊
app.include_router(users.router)     # 使用者資訊
app.include_router(stores.router)    # 商店
app.include_router(products.router)  # 商品
app.include_router(ws_router)        # WebSocket
# app.include_router(cart.router)    # 購物車 (如果你還沒建立 cart.py，這行先註解掉以免報錯)

# ===============================
# Server Startup Event
# ===============================
@app.on_event("startup")
def load_default_map():
    """Server 啟動時自動載入預設地圖"""
    path = "data/map.json"
    try:
        print(f"📍 Loading map: {path}")
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
# API: Import Map Manually
# ===============================
@app.post("/maps/import")
def import_map(path: str = "data/map.json"):
    try:
        raw = Path(path).read_text(encoding="utf-8")
        data = json.loads(raw)
        map_data = MapData.model_validate(data)
        g = build_graph(map_data)

        MAP_STORE[map_data.map_id] = map_data
        GRAPH_STORE[map_data.map_id] = g

        return {
            "ok": True,
            "map_id": map_data.map_id,
            "nodes": len(map_data.nodes),
            "edges": len(map_data.edges),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ===============================
# API: Create Order
# ===============================
@app.post("/orders", response_model=CreateOrderResp)
def create_order(req: CreateOrderReq):
    if req.map_id not in GRAPH_STORE:
        raise HTTPException(status_code=404, detail="map_id not loaded; call /maps/import first")

    g = GRAPH_STORE[req.map_id]

    try:
        if req.algorithm == "astar":
            route, dist = astar(g, req.from_node, req.to_node)
        else:
            route, dist = dijkstra(g, req.from_node, req.to_node)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    eta = estimate_eta_sec(route, dist)
    order_id = "O" + uuid.uuid4().hex[:8]

    ORDER_STORE[order_id] = {
        "order_id": order_id,
        "map_id": req.map_id,
        "route": route,
        "total_distance_cm": dist,
        "eta_sec": eta,
        "state": "CREATED",
    }

    # 如果有提供用戶資訊，將訂單加入訂單歷史
    if req.user_email and req.store_name:
        fake_orders_db.append({
            "user_email": req.user_email,
            "id": order_id,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "store": req.store_name,
            "items": req.items or [],
            "total": req.total or 0,
            "status": "配送中"
        })

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
@app.get("/orders/{order_id}")
def get_order(order_id: str):
    if order_id not in ORDER_STORE:
        raise HTTPException(status_code=404, detail="order not found")
    return ORDER_STORE[order_id]


@app.get("/")
def read_root():
    return {"message": "Autonomous Delivery Robot API is running!"}

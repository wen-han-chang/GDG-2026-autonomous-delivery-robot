from fastapi import FastAPI, HTTPException
from typing import Dict
import uuid
import json
from pathlib import Path

from .models import MapData, CreateOrderReq, CreateOrderResp
from .graph import build_graph, dijkstra, astar
from .services import estimate_eta_sec
from .ws import ws_router
from .state import MAP_STORE, GRAPH_STORE, ORDER_STORE

app = FastAPI(title="ESP32 Car Backend")

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


# ===============================
# WebSocket
# ===============================
app.include_router(ws_router)
from .routers import stores, products, auth, users

app.include_router(stores.router)
app.include_router(products.router)
app.include_router(auth.router)
app.include_router(users.router)

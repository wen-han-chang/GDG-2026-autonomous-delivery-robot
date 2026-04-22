from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import asyncio
import os
import uuid
import json
from pathlib import Path
from typing import List, Tuple

# 資料庫相關
from .database import engine, Base, get_db, SessionLocal
from .sql_models import OrderDB, StoreDB, ProductDB, RobotStateDB

# Pydantic Models & Logic
from .models import (
    MapData,
    CreateOrderReq,
    CreateOrderResp,
    CreateMultiOrderReq,
    CreateMultiOrderResp,
    SingleOrderSummary,
)
from .graph import build_graph, dijkstra, astar
from .services import estimate_eta_sec
from .state import MAP_STORE, GRAPH_STORE

# Router
from .routers import stores, products, auth, users, planner
from .routers.users import get_current_user
from .ws import ws_router
from .dispatcher import dispatch_order_to_robot
from .mqtt_bridge import get_mqtt_bridge, set_main_event_loop
from .planner_state import get_global_state

# 匯入寫死的資料用於初始化資料庫
from .routers.stores import STORE_STORE, PRODUCT_STORE

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. 自動建立資料表
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables verified.")

        with SessionLocal() as db:
            if db.query(StoreDB).count() == 0:
                for info in STORE_STORE.values():
                    db.add(StoreDB(**info))
                db.commit()
                print("✅ Default stores imported to RDS.")

            if db.query(ProductDB).count() == 0:
                for info in PRODUCT_STORE.values():
                    db.add(ProductDB(**info))
                db.commit()
                print("✅ Default products imported to RDS.")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")

    load_map_logic()

    # 2. 還原小車狀態（從 DB 重建 GlobalPlannerState）
    try:
        with SessionLocal() as db:
            robot_states = db.query(RobotStateDB).all()
            planner_state = get_global_state()
            for rs in robot_states:
                active_orders_count = (
                    db.query(OrderDB)
                    .filter(
                        OrderDB.assigned_robot_id == rs.robot_id,
                        OrderDB.status != "DELIVERED",
                    )
                    .count()
                )

                # 若沒有任何未完成訂單，清掉殘留規劃，避免重啟後看到舊 action/stop
                if active_orders_count == 0:
                    rs.next_deliver_k = 1
                    rs.picked_mask = 0
                    rs.plan_actions = []
                    rs.plan_stops = []
                    rs.last_plan_cost = 0

                robot = planner_state.add_robot(rs.robot_id, rs.current_node)
                robot.next_deliver_k = rs.next_deliver_k
                robot.picked_mask = rs.picked_mask
                robot.plan_actions = rs.plan_actions or []
                robot.plan_stops = rs.plan_stops or []
                robot.last_plan_cost = rs.last_plan_cost

            if robot_states:
                db.commit()
            if robot_states:
                print(f"✅ Restored {len(robot_states)} robot state(s) from DB.")
    except Exception as e:
        print(f"⚠️ Could not restore robot states: {e}")

    # 3. 啟動 MQTT 橋接
    loop = asyncio.get_event_loop()
    set_main_event_loop(loop)
    mqtt_host = os.getenv("MQTT_BROKER_URL", "localhost")
    mqtt_port = int(os.getenv("MQTT_BROKER_PORT", "1883"))
    use_mock = os.getenv("MQTT_USE_MOCK", "true").lower() == "true"
    bridge = get_mqtt_bridge(broker_url=mqtt_host, broker_port=mqtt_port, use_mock=use_mock)
    bridge.start()
    print(f"✅ MQTT bridge started (mock={use_mock}, host={mqtt_host}:{mqtt_port})")

    yield  # 應用程式運行中

    # Shutdown
    bridge.stop()
    print("✅ MQTT bridge stopped.")


app = FastAPI(title="ESP32 Car Backend", lifespan=lifespan)

# --- CORS 設定 ---
# 開發環境預設允許 localhost；生產環境必須透過 ALLOWED_ORIGINS 環境變數明確設定
_default_origins = "http://localhost:5173,http://localhost:8000" if os.getenv("ENV", "development") != "production" else ""
raw_origins = os.getenv("ALLOWED_ORIGINS", _default_origins)
allowed_origins = [o.strip() for o in raw_origins.split(",") if o.strip()]

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
app.include_router(planner.router)
app.include_router(ws_router)

# 載入地圖邏輯
def load_map_logic(path: str = "data/map.json"):
    try:
        print(f"📍 Loading map from: {path}")
        if not Path(path).exists():
            return
        raw = Path(path).read_text(encoding="utf-8")
        data = json.loads(raw)
        map_data = MapData.model_validate(data)
        g = build_graph(map_data)
        MAP_STORE[map_data.map_id] = map_data
        GRAPH_STORE[map_data.map_id] = g
        print(f"✅ Map loaded: {map_data.map_id}")
    except Exception as e:
        print(f"❌ Failed to load map: {e}")


# HOME 節點（機器人停靠/送達點）
HOME_NODE = "A"


def _calculate_route(g, algorithm: str, from_node: str, to_node: str):
    """固定節點版路徑計算：僅允許 map 內既有節點，不做虛擬節點吸附。"""
    if from_node not in g.nodes or to_node not in g.nodes:
        raise HTTPException(status_code=400, detail="from_node/to_node must be existing map nodes")

    try:
        if algorithm == "astar":
            return astar(g, from_node, to_node)
        return dijkstra(g, from_node, to_node)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


def _resolve_order_nodes(req: CreateOrderReq, db: Session) -> Tuple[str, str]:
    """解析單店訂單 from/to 節點，保留向後相容格式。"""
    from_node = req.from_node
    to_node = req.to_node

    if req.store_id:
        store = db.query(StoreDB).filter(StoreDB.id == req.store_id).first()
        if not store:
            raise HTTPException(status_code=404, detail=f"store_id '{req.store_id}' not found")
        from_node = store.location_node
        if not to_node:
            to_node = HOME_NODE
    elif not from_node:
        raise HTTPException(status_code=400, detail="Provide either from_node or store_id")
    elif not to_node:
        to_node = HOME_NODE

    return from_node, to_node


def _create_and_dispatch_order(
    *,
    db: Session,
    map_id: str,
    from_node: str,
    to_node: str,
    algorithm: str,
    current_user_email: str,
    store_name: str | None,
    items: List[str] | None,
    total_amount: float,
):
    """建立單筆 DB 訂單並觸發派單。"""
    g = GRAPH_STORE[map_id]
    route, dist = _calculate_route(g, algorithm, from_node, to_node)
    eta = estimate_eta_sec(route, dist)

    order_id = "O" + uuid.uuid4().hex[:8]
    new_order = OrderDB(
        id=order_id,
        map_id=map_id,
        status="CREATED",
        total_distance_cm=dist,
        eta_sec=eta,
        route=route,
        user_email=current_user_email,
        store_name=store_name,
        items=items or [],
        total_amount=total_amount,
    )

    db.add(new_order)
    db.flush()

    dispatch_order_to_robot(
        order_id=order_id,
        shop_node=from_node,
        drop_node=to_node,
        db=db,
    )

    return new_order

# API: Create Order
@app.post("/orders", response_model=CreateOrderResp, tags=["訂單"])
def create_order(req: CreateOrderReq, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if req.map_id not in GRAPH_STORE:
        raise HTTPException(status_code=404, detail="map_id not loaded")

    # 避免在舊端點混用多店 payload
    if req.store_ids:
        raise HTTPException(status_code=400, detail="Use /orders/multi for multi-store orders")

    from_node, to_node = _resolve_order_nodes(req, db)

    try:
        new_order = _create_and_dispatch_order(
            db=db,
            map_id=req.map_id,
            from_node=from_node,
            to_node=to_node,
            algorithm=req.algorithm,
            current_user_email=current_user.email,
            store_name=req.store_name,
            items=req.items,
            total_amount=req.total or 0.0,
        )

        db.commit()
        db.refresh(new_order)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Order creation failed: {str(e)}")

    return CreateOrderResp(
        order_id=new_order.id,
        map_id=req.map_id,
        route=new_order.route,
        total_distance_cm=new_order.total_distance_cm,
        eta_sec=new_order.eta_sec,
        assigned_robot_id=new_order.assigned_robot_id,
    )


@app.post("/orders/multi", response_model=CreateMultiOrderResp, tags=["訂單"])
def create_multi_store_order(
    req: CreateMultiOrderReq,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """一次下多店訂單：每個店建立一筆實體訂單並加入同一批派送流程。"""
    if req.map_id not in GRAPH_STORE:
        raise HTTPException(status_code=404, detail="map_id not loaded")

    # 去重後保留順序
    dedup_store_ids: List[str] = list(dict.fromkeys(req.store_ids))
    if not dedup_store_ids:
        raise HTTPException(status_code=400, detail="store_ids cannot be empty")

    to_node = req.to_node or HOME_NODE

    stores = db.query(StoreDB).filter(StoreDB.id.in_(dedup_store_ids)).all()
    store_by_id = {s.id: s for s in stores}
    missing = [sid for sid in dedup_store_ids if sid not in store_by_id]
    if missing:
        raise HTTPException(status_code=404, detail=f"store_ids not found: {missing}")

    created_orders: List[OrderDB] = []
    try:
        split_total = float(req.total or 0) / len(dedup_store_ids)
        for store_id in dedup_store_ids:
            store = store_by_id[store_id]
            store_items = []
            if req.items_by_store and store_id in req.items_by_store:
                store_items = req.items_by_store[store_id]
            elif req.items:
                store_items = req.items

            order = _create_and_dispatch_order(
                db=db,
                map_id=req.map_id,
                from_node=store.location_node,
                to_node=to_node,
                algorithm=req.algorithm,
                current_user_email=current_user.email,
                store_name=store.name,
                items=store_items,
                total_amount=split_total,
            )
            created_orders.append(order)

        db.commit()
        for order in created_orders:
            db.refresh(order)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Multi-store order creation failed: {str(e)}")

    summaries: List[SingleOrderSummary] = []
    total_distance = 0.0
    max_eta = 0.0
    for store_id, order in zip(dedup_store_ids, created_orders):
        summaries.append(
            SingleOrderSummary(
                order_id=order.id,
                store_id=store_id,
                route=order.route,
                total_distance_cm=order.total_distance_cm,
                eta_sec=order.eta_sec,
                assigned_robot_id=order.assigned_robot_id,
            )
        )
        total_distance += float(order.total_distance_cm or 0.0)
        max_eta = max(max_eta, float(order.eta_sec or 0.0))

    return CreateMultiOrderResp(
        map_id=req.map_id,
        order_ids=[o.id for o in created_orders],
        orders=summaries,
        total_distance_cm=total_distance,
        max_eta_sec=max_eta,
    )

@app.get("/orders/{order_id}", tags=["訂單"])
def get_order(order_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    order = db.query(OrderDB).filter(OrderDB.id == order_id).first()
    if not order: raise HTTPException(status_code=404, detail="Order not found")
    if order.user_email != current_user.email: raise HTTPException(status_code=403, detail="Forbidden")
    return order

@app.get("/")
def read_root():
    return {"message": "Autonomous Delivery Robot API is running!"}

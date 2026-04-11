"""
規劃 API 路由層

提供端點供小車、前端、後端服務查詢路徑規劃結果。

主要端點：
  POST /planner/replan   - 從當前狀態重新規劃
  GET  /planner/plan     - 取得最新規劃結果
  POST /planner/update-location  - 更新小車位置（可用於測試或模擬）

不動原有的前端架構：
  - 前端仍透過 /orders 端點下訂單
  - /planner 是新增的服務層，僅供後端與小車內部使用
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime
import logging

from sqlalchemy.orm import Session

from ..algorithm import MapGraph, Planner, pack_state, unpack_state
from ..planner_state import get_global_state, RobotState
from ..graph import build_graph
from ..state import GRAPH_STORE, MAP_STORE
from ..models import MapData
from ..ws import update_order_in_db, broadcast
from ..database import get_db
from ..sql_models import RobotStateDB

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/planner", tags=["planner"])


# ==================== Pydantic Models ====================


class ReplanRequest(BaseModel):
    """重新規劃請求"""

    robot_id: str
    # 可選：指定當前位置（若不提供則使用最後更新的位置）
    current_node: Optional[str] = None


class ReplanResponse(BaseModel):
    """重新規劃回應"""

    robot_id: str
    success: bool
    total_cost: int  # cm
    actions: List[str]
    stops: List[str]
    timestamp: datetime


class RobotStatusResponse(BaseModel):
    """小車狀態回應"""

    robot_id: str
    current_node: str
    next_deliver_k: int
    picked_mask: int
    orders_count: int
    pending_count: int
    last_plan_cost: Optional[int]
    plan_actions: List[str]
    plan_stops: List[str]


class UpdateLocationRequest(BaseModel):
    """更新位置請求"""

    robot_id: str
    node: str


class InitRobotRequest(BaseModel):
    """初始化小車"""

    robot_id: str
    start_node: str = "A"  # 預設起點


# ==================== 輔助函數 ====================


def _get_map_data():
    """取得當前載入的地圖資料（單地圖部署）"""
    map_data = next(iter(MAP_STORE.values()), None)
    if map_data is None or not map_data.nodes:
        raise HTTPException(status_code=500, detail="Map not loaded")
    return map_data


def get_node_id_mapping() -> Dict[str, int]:
    """
    取得節點名稱到 ID 的映射

    algorithm.py 使用整數 ID，需要與資料庫的字串節點名稱做轉換

    映射順序必須與 MAP_STORE nodes 在 build_algorithm_graph 中添加的順序相同
    """
    map_data = _get_map_data()
    return {node.id: idx for idx, node in enumerate(map_data.nodes)}


def build_algorithm_graph() -> MapGraph:
    """建立演算法用的圖結構"""
    map_data = _get_map_data()
    mp = MapGraph()
    node_mapping = get_node_id_mapping()

    # 添加所有節點（順序必須與 node_mapping 一致）
    for node in map_data.nodes:
        mp.add_node(node.x, node.y)

    # 添加邊
    for edge in map_data.edges:
        from_id = node_mapping[edge.from_]
        to_id = node_mapping[edge.to]
        if edge.length is not None:
            length = int(edge.length)
        else:
            fx, fy = map_data.nodes[from_id].x, map_data.nodes[from_id].y
            tx, ty = map_data.nodes[to_id].x, map_data.nodes[to_id].y
            length = int(((fx - tx) ** 2 + (fy - ty) ** 2) ** 0.5)

        mp.add_undirected_edge(from_id, to_id, length)

    return mp


# ==================== DB 持久化輔助函數 ====================


def _persist_robot_state(robot: RobotState, db: Session):
    """將小車狀態 upsert 到 RobotStateDB"""
    try:
        existing = db.query(RobotStateDB).filter(RobotStateDB.robot_id == robot.robot_id).first()
        if existing:
            existing.current_node = robot.current_node
            existing.next_deliver_k = robot.next_deliver_k
            existing.picked_mask = robot.picked_mask
            existing.plan_actions = robot.plan_actions
            existing.plan_stops = robot.plan_stops
            existing.last_plan_cost = robot.last_plan_cost
            existing.updated_at = datetime.utcnow()
        else:
            db.add(RobotStateDB(
                robot_id=robot.robot_id,
                current_node=robot.current_node,
                next_deliver_k=robot.next_deliver_k,
                picked_mask=robot.picked_mask,
                plan_actions=robot.plan_actions,
                plan_stops=robot.plan_stops,
                last_plan_cost=robot.last_plan_cost,
            ))
        db.commit()
    except Exception as e:
        logger.error(f"Failed to persist robot state for {robot.robot_id}: {e}")
        db.rollback()


# ==================== API Endpoints ====================


@router.post("/init")
async def init_robot(req: InitRobotRequest, db: Session = Depends(get_db)):
    """
    初始化小車

    :param robot_id: 小車 ID（例如 "R001"）
    :param start_node: 起始節點（預設 "A"）
    """
    state = get_global_state()
    robot = state.add_robot(req.robot_id, req.start_node)
    _persist_robot_state(robot, db)

    logger.info(f"Robot {req.robot_id} initialized at node {req.start_node}")

    return {
        "robot_id": req.robot_id,
        "start_node": req.start_node,
        "message": "Robot initialized",
    }


@router.get("/status")
async def get_robot_status(robot_id: str = Query(...)):
    """
    取得小車的當前規劃狀態

    :param robot_id: 小車 ID
    """
    state = get_global_state()
    robot = state.get_robot(robot_id)

    if robot is None:
        raise HTTPException(status_code=404, detail=f"Robot {robot_id} not found")

    return RobotStatusResponse(
        robot_id=robot.robot_id,
        current_node=robot.current_node,
        next_deliver_k=robot.next_deliver_k,
        picked_mask=robot.picked_mask,
        orders_count=len(robot.all_orders),
        pending_count=robot.get_pending_count(),
        last_plan_cost=robot.last_plan_cost,
        plan_actions=robot.plan_actions,
        plan_stops=robot.plan_stops,
    )


@router.post("/replan")
async def replan(req: ReplanRequest, db: Session = Depends(get_db)) -> ReplanResponse:
    """
    從當前狀態開始重新規劃

    流程：
    1. 取得小車的當前訂單清單
    2. 建立演算法圖
    3. 執行 Planner.solve_from_state()
    4. 保存結果

    :param robot_id: 小車 ID
    :param current_node: （可選）更新當前位置
    """
    state = get_global_state()
    robot = state.get_robot(req.robot_id)

    if robot is None:
        raise HTTPException(status_code=404, detail=f"Robot {req.robot_id} not found")

    # 若提供當前位置，先更新
    if req.current_node:
        robot.current_node = req.current_node

    # 取得訂單清單
    orders_list = robot.get_pending_orders()
    if not orders_list:
        logger.warning(f"Robot {req.robot_id} has no pending orders")
        return ReplanResponse(
            robot_id=req.robot_id,
            success=False,
            total_cost=0,
            actions=[],
            stops=[],
            timestamp=datetime.now(),
        )

    try:
        # 建立演算法圖
        mp = build_algorithm_graph()
        node_mapping = get_node_id_mapping()

        # 轉換 orders 為演算法輸入格式
        algo_orders = []
        for k, order in orders_list:
            shop_id = node_mapping[order.shop_node]
            drop_id = node_mapping[order.drop_node]
            algo_orders.append((shop_id, drop_id))

        # 起始節點
        start_id = node_mapping[robot.current_node]

        # 執行規劃
        planner = Planner(mp, start_id, algo_orders)
        ok, actions, stops, cost = planner.solve_from_state(
            robot.next_deliver_k, robot.picked_mask
        )

        if not ok:
            logger.error(f"Planner failed for robot {req.robot_id}")
            return ReplanResponse(
                robot_id=req.robot_id,
                success=False,
                total_cost=0,
                actions=[],
                stops=[],
                timestamp=datetime.now(),
            )

        # 轉換 stops 回節點名稱
        reverse_mapping = {v: k for k, v in node_mapping.items()}
        stops_names = [reverse_mapping.get(s, str(s)) for s in stops]

        # 保存規劃結果並持久化到 DB
        state.update_plan(req.robot_id, actions, stops_names, cost)
        _persist_robot_state(robot, db)

        logger.info(
            f"Replanning succeeded for robot {req.robot_id}: cost={cost}, actions={len(actions)}"
        )

        return ReplanResponse(
            robot_id=req.robot_id,
            success=True,
            total_cost=cost,
            actions=actions,
            stops=stops_names,
            timestamp=datetime.now(),
        )

    except Exception as e:
        logger.exception(f"Error during replanning: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/update-location")
async def update_location(req: UpdateLocationRequest):
    """
    更新小車位置

    此端點用於測試與模擬；生產環境應透過 MQTT 更新
    """
    state = get_global_state()
    if not state.update_robot_location(req.robot_id, req.node):
        raise HTTPException(status_code=404, detail=f"Robot {req.robot_id} not found")

    logger.info(f"Robot {req.robot_id} moved to {req.node}")
    await broadcast({"type": "robot_location", "robot_id": req.robot_id, "node": req.node})

    return {
        "robot_id": req.robot_id,
        "current_node": req.node,
        "message": "Location updated",
    }


@router.post("/mark-picked")
async def mark_order_picked(robot_id: str = Query(...), order_k: int = Query(...)):
    """
    標記訂單已取

    :param robot_id: 小車 ID
    :param order_k: 訂單編號（1-indexed）
    """
    state = get_global_state()
    robot = state.get_robot(robot_id)
    if robot is None:
        raise HTTPException(status_code=404, detail=f"Robot {robot_id} not found")

    order = robot.all_orders.get(order_k)
    if not state.mark_order_picked(robot_id, order_k):
        raise HTTPException(status_code=400, detail="Cannot mark order as picked")

    # 同步更新 DB 訂單狀態
    if order and order.order_id:
        update_order_in_db(order.order_id, "PICKED")
        await broadcast({"type": "order_status", "order_id": order.order_id, "status": "PICKED", "robot_id": robot_id})

    logger.info(f"Robot {robot_id} picked order {order_k}")

    return {
        "robot_id": robot_id,
        "order_k": order_k,
        "message": "Order marked as picked",
    }


@router.post("/mark-delivered")
async def mark_order_delivered(robot_id: str = Query(...), order_k: int = Query(...)):
    """
    標記訂單已送

    :param robot_id: 小車 ID
    :param order_k: 訂單編號（1-indexed）
    """
    state = get_global_state()
    robot = state.get_robot(robot_id)
    if robot is None:
        raise HTTPException(status_code=404, detail=f"Robot {robot_id} not found")

    order = robot.all_orders.get(order_k)
    if not state.mark_order_delivered(robot_id, order_k):
        raise HTTPException(status_code=400, detail="Cannot mark order as delivered")

    # 同步更新 DB 訂單狀態
    if order and order.order_id:
        update_order_in_db(order.order_id, "DELIVERED")
        await broadcast({"type": "order_status", "order_id": order.order_id, "status": "DELIVERED", "robot_id": robot_id})

    logger.info(f"Robot {robot_id} delivered order {order_k}")

    return {
        "robot_id": robot_id,
        "order_k": order_k,
        "message": "Order marked as delivered",
    }

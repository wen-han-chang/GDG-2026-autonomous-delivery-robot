"""
訂單派送器

職責：
1. 當前端建立新訂單後，自動指派給可用的小車
2. 觸發小車重新規劃路線
3. 透過 MQTT 將規劃結果推送給小車

派送策略：選擇待送訂單數最少的小車（負載均衡）
若沒有已初始化的小車，訂單保持 CREATED 狀態等待手動指派
"""

import logging
from typing import Optional
import os
import threading
import time
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from .planner_state import get_global_state
from .sql_models import OrderDB, RobotStateDB
from .mqtt_bridge import get_mqtt_bridge, _schedule_ws_broadcast
from .database import SessionLocal
from .state import GRAPH_STORE
from .graph import dijkstra

logger = logging.getLogger(__name__)

ROBOT_ONLINE_TTL_SEC = int(os.getenv("ROBOT_ONLINE_TTL_SEC", "15"))
SIMULATION_AUTO_CLEAR_ENABLED = os.getenv("SIMULATION_AUTO_CLEAR_ENABLED", "true").lower() == "true"
SIMULATION_SPEED_CM_S = float(os.getenv("SIMULATION_SPEED_CM_S", "12.0"))

_SIM_WORKERS: dict[str, threading.Thread] = {}
_SIM_EVENTS: dict[str, threading.Event] = {}
_SIM_LOCK = threading.Lock()


def _is_robot_online(robot) -> bool:
    """以最近 telemetry 時間判斷小車是否在線。"""
    if robot is None or robot.last_telemetry_at is None:
        return False
    return datetime.now() - robot.last_telemetry_at <= timedelta(seconds=ROBOT_ONLINE_TTL_SEC)


def _edge_distance_cm(g, u: str, v: str) -> float:
    for nxt, w in g.adj.get(u, []):
        if nxt == v:
            return float(w)
    return 0.0


def _persist_robot_state_snapshot(robot_id: str):
    state = get_global_state()
    robot = state.get_robot(robot_id)
    if not robot:
        return

    db = SessionLocal()
    try:
        existing = db.query(RobotStateDB).filter(RobotStateDB.robot_id == robot_id).first()
        if existing:
            existing.current_node = robot.current_node
            existing.next_deliver_k = robot.next_deliver_k
            existing.picked_mask = robot.picked_mask
            existing.plan_actions = robot.plan_actions
            existing.plan_stops = robot.plan_stops
            existing.last_plan_cost = robot.last_plan_cost
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
    except Exception:
        db.rollback()
    finally:
        db.close()


def _set_db_order_status(order_id: str, status: str):
    db = SessionLocal()
    try:
        order = db.query(OrderDB).filter(OrderDB.id == order_id).first()
        if order:
            order.status = status
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _delete_delivered_orders_for_robot(robot_id: str):
    db = SessionLocal()
    try:
        db.query(OrderDB).filter(
            OrderDB.assigned_robot_id == robot_id,
            OrderDB.status == "DELIVERED",
        ).delete(synchronize_session=False)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _process_arrival_events(robot_id: str, node: str):
    state = get_global_state()
    robot = state.get_robot(robot_id)
    if not robot:
        return

    # 先處理可送達（需遵守下單順序）
    while True:
        k = robot.next_deliver_k
        order = robot.all_orders.get(k)
        if not order or order.status != "picked" or order.drop_node != node:
            break

        if state.mark_order_delivered(robot_id, k):
            _set_db_order_status(order.order_id, "DELIVERED")
            _schedule_ws_broadcast({
                "type": "order_status",
                "order_id": order.order_id,
                "status": "DELIVERED",
                "robot_id": robot_id,
                "simulated": True,
            })

    # 再處理取貨（可同節點一次取多單）
    for k, order in sorted(robot.all_orders.items(), key=lambda x: x[0]):
        if k < robot.next_deliver_k:
            continue
        if order.status != "pending" or order.shop_node != node:
            continue

        if state.mark_order_picked(robot_id, k):
            _set_db_order_status(order.order_id, "PICKED")
            _schedule_ws_broadcast({
                "type": "order_status",
                "order_id": order.order_id,
                "status": "PICKED",
                "robot_id": robot_id,
                "simulated": True,
            })


def _simulation_worker(robot_id: str, wake_event: threading.Event):
    state = get_global_state()
    g = next(iter(GRAPH_STORE.values()), None)
    if g is None:
        logger.warning("Simulation worker cannot start: graph not loaded")
        return

    try:
        while True:
            robot = state.get_robot(robot_id)
            if not robot:
                return

            if robot.get_pending_count() == 0:
                _delete_delivered_orders_for_robot(robot_id)
                state.reset_robot_after_completion(robot_id)
                _persist_robot_state_snapshot(robot_id)
                return

            ok, _actions, stops, _cost = _run_replan(robot_id)
            if not ok or not stops:
                wake_event.wait(timeout=0.5)
                wake_event.clear()
                continue

            target = stops[0]
            current = robot.current_node

            if current != target:
                try:
                    path, _ = dijkstra(g, current, target)
                except Exception as e:
                    logger.warning(f"Simulation path search failed {current}->{target}: {e}")
                    wake_event.wait(timeout=0.5)
                    wake_event.clear()
                    continue

                for nxt in path[1:]:
                    seg = _edge_distance_cm(g, current, nxt)
                    sleep_sec = max(0.05, seg / max(1.0, SIMULATION_SPEED_CM_S))
                    time.sleep(sleep_sec)

                    state.update_robot_location(robot_id, nxt)
                    _persist_robot_state_snapshot(robot_id)
                    current = nxt

                    # 每到節點都允許插單觸發重規劃（模擬在黑線停車點重算）
                    if wake_event.is_set():
                        wake_event.clear()
                        break

                if current != target:
                    continue

            # 到站後先處理取/送，再進入下一輪重規劃
            _process_arrival_events(robot_id, target)
            _persist_robot_state_snapshot(robot_id)
    finally:
        with _SIM_LOCK:
            _SIM_WORKERS.pop(robot_id, None)
            _SIM_EVENTS.pop(robot_id, None)


def _start_simulation_auto_clear(robot_id: str, order_id: str, db: Session):
    """啟動或喚醒離線模擬執行器（每台車單一 worker）。"""
    if not SIMULATION_AUTO_CLEAR_ENABLED:
        return

    with _SIM_LOCK:
        worker = _SIM_WORKERS.get(robot_id)
        event = _SIM_EVENTS.get(robot_id)

        if event is None:
            event = threading.Event()
            _SIM_EVENTS[robot_id] = event

        # 新訂單到達：喚醒 worker，讓其在下一節點前重算
        event.set()

        if worker and worker.is_alive():
            return

        thread = threading.Thread(
            target=_simulation_worker,
            args=(robot_id, event),
            daemon=True,
        )
        _SIM_WORKERS[robot_id] = thread
        thread.start()


def _run_replan(robot_id: str) -> tuple:
    """
    執行重新規劃（內部共用邏輯，與 /planner/replan 端點共用）

    :return: (ok, actions, stops, cost)
    """
    from .routers.planner import build_algorithm_graph, get_node_id_mapping, get_robot_start_node

    state = get_global_state()
    robot = state.get_robot(robot_id)
    if not robot:
        return False, [], [], 0

    pending_orders = robot.get_pending_orders()
    if not pending_orders:
        state.update_plan(robot_id, [], [], 0)
        return True, [], [], 0

    try:
        from .algorithm import Planner

        mp = build_algorithm_graph()
        node_mapping = get_node_id_mapping()

        # 針對 pending 訂單重建連續索引，避免 next_deliver_k / picked_mask 與 pending 子集合錯位
        pending_sorted = sorted(pending_orders, key=lambda x: x[0])
        remap = {old_k: i + 1 for i, (old_k, _o) in enumerate(pending_sorted)}

        algo_orders = []
        remapped_mask = 0
        for old_k, order in pending_sorted:
            shop_id = node_mapping[order.shop_node]
            drop_id = node_mapping[order.drop_node]
            algo_orders.append((shop_id, drop_id))
            if robot.picked_mask & (1 << (old_k - 1)):
                remapped_k = remap[old_k]
                remapped_mask |= 1 << (remapped_k - 1)

        start_node = get_robot_start_node(robot, node_mapping)

        start_id = node_mapping[start_node]
        planner = Planner(mp, start_id, algo_orders)
        ok, actions, stops, cost = planner.solve_from_state(
            1, remapped_mask
        )

        if ok:
            reverse_mapping = {v: k for k, v in node_mapping.items()}
            stops_names = [reverse_mapping.get(s, str(s)) for s in stops]
            state.update_plan(robot_id, actions, stops_names, cost)
            return True, actions, stops_names, cost

        return False, [], [], 0

    except Exception as e:
        logger.exception(f"Replan failed for robot {robot_id}: {e}")
        return False, [], [], 0


def dispatch_order_to_robot(
    order_id: str,
    shop_node: str,
    drop_node: str,
    db: Session,
) -> Optional[str]:
    """
    將訂單指派給最適合的小車並觸發重新規劃

    :param order_id: DB 訂單 ID（例如 "Oabc12345"）
    :param shop_node: 取貨節點（例如 "A"）
    :param drop_node: 送達節點（例如 "D"）
    :param db: SQLAlchemy DB session（由呼叫方提供）
    :return: 已指派的 robot_id，若沒有可用小車則回傳 None
    """
    state = get_global_state()
    bridge = get_mqtt_bridge()

    # 優先分配給在線小車；若都離線，分配給負載最小的小車並啟動模擬清單
    online_candidates = []
    offline_candidates = []
    for rid, robot in state.robots.items():
        if _is_robot_online(robot):
            online_candidates.append((rid, robot.get_pending_count()))
        else:
            offline_candidates.append((rid, robot.get_pending_count()))

    best_robot_id: Optional[str] = None
    selected_online = False
    if online_candidates:
        best_robot_id = min(online_candidates, key=lambda x: x[1])[0]
        selected_online = True
    elif offline_candidates:
        best_robot_id = min(offline_candidates, key=lambda x: x[1])[0]

    if best_robot_id is None:
        logger.warning(f"No robots available to dispatch order {order_id}")
        return None

    # 加入規劃狀態
    state.add_order(
        robot_id=best_robot_id,
        shop_node=shop_node,
        drop_node=drop_node,
        order_id=order_id,
    )

    # 更新 DB 訂單狀態（flush only — caller owns the commit）
    order = db.query(OrderDB).filter(OrderDB.id == order_id).first()
    if order:
        order.status = "ASSIGNED"
        order.assigned_robot_id = best_robot_id
        db.flush()

    # 廣播 order_assigned 事件給前端
    _schedule_ws_broadcast({
        "type": "order_assigned",
        "order_id": order_id,
        "robot_id": best_robot_id,
    })

    # 觸發重新規劃
    ok, actions, stops, cost = _run_replan(best_robot_id)
    if ok:
        logger.info(
            f"Order {order_id} dispatched to {best_robot_id}, "
            f"replan cost={cost}, stops={stops}"
        )
        # 真實 MQTT 模式：不管 telemetry 在線與否，直接推送計畫給小車
        if bridge.is_connected() and not bridge.use_mock:
            try:
                bridge.publish_plan(best_robot_id, actions, stops)
                logger.info(f"MQTT plan published to {best_robot_id}")
            except Exception as e:
                logger.warning(f"MQTT publish failed (non-fatal): {e}")
        # Mock/離線模式：啟動模擬取送流程，自動清 pending
        else:
            logger.info(
                f"Robot {best_robot_id} offline/mock; "
                f"starting simulation auto-clear for order {order_id}"
            )
            _start_simulation_auto_clear(best_robot_id, order_id, db)
    else:
        logger.warning(
            f"Order {order_id} assigned to {best_robot_id} but replan failed"
        )

    return best_robot_id

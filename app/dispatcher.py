"""
訂單派送器

職責：
1. 當前端建立新訂單後，自動指派給可用的小車
2. 觸發小車重新規劃路線
3. 透過 MQTT 將規劃結果推送給小車

派送策略：選擇待送訂單數最少的小車（負載均衡）
若沒有已初始化的小車，訂單保持 CREATED 狀態等待手動指派
"""

import asyncio
import logging
from typing import Optional
from sqlalchemy.orm import Session

from .planner_state import get_global_state
from .sql_models import OrderDB
from .mqtt_bridge import get_mqtt_bridge, _schedule_ws_broadcast

logger = logging.getLogger(__name__)


def _run_replan(robot_id: str) -> tuple:
    """
    執行重新規劃（內部共用邏輯，與 /planner/replan 端點共用）

    :return: (ok, actions, stops, cost)
    """
    from .routers.planner import build_algorithm_graph, get_node_id_mapping

    state = get_global_state()
    robot = state.get_robot(robot_id)
    if not robot:
        return False, [], [], 0

    orders_list = robot.get_pending_orders()
    if not orders_list:
        return False, [], [], 0

    try:
        from .algorithm import Planner

        mp = build_algorithm_graph()
        node_mapping = get_node_id_mapping()

        algo_orders = []
        for k, order in orders_list:
            shop_id = node_mapping[order.shop_node]
            drop_id = node_mapping[order.drop_node]
            algo_orders.append((shop_id, drop_id))

        start_id = node_mapping[robot.current_node]
        planner = Planner(mp, start_id, algo_orders)
        ok, actions, stops, cost = planner.solve_from_state(
            robot.next_deliver_k, robot.picked_mask
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

    # 選擇待送訂單最少的小車
    best_robot_id: Optional[str] = None
    best_count = float("inf")
    for rid, robot in state.robots.items():
        count = robot.get_pending_count()
        if count < best_count:
            best_count = count
            best_robot_id = rid

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
        # 透過 MQTT 推送規劃結果給小車
        try:
            bridge = get_mqtt_bridge()
            bridge.publish_plan(best_robot_id, actions, stops)
        except Exception as e:
            logger.warning(f"MQTT publish failed (non-fatal): {e}")
    else:
        logger.warning(
            f"Order {order_id} assigned to {best_robot_id} but replan failed"
        )

    return best_robot_id

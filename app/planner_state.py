"""
全局規劃狀態管理

職責：
1. 管理小車當前位置、已取訂單、已送訂單
2. 支援輸入新訂單並自動重新規劃
3. 生成可供小車執行的規劃結果

不依賴資料庫，運行時狀態存儲在記憶體中；
未來可搭配資料庫實現持久化。
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import json
import threading


@dataclass
class Order:
    """單筆訂單"""

    order_id: str
    shop_node: str  # 商店的 location_node（例如 "A", "X1"）
    drop_node: str  # 收貨點（例如 "D"，可能是虛擬節點後的實際位置）
    drop_coords: Optional[Tuple[float, float]] = None  # 原始座標 (x, y)，若使用 snap
    created_at: datetime = field(default_factory=datetime.now)
    picked_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    status: str = "pending"  # pending, picked, delivered


@dataclass
class RobotState:
    """小車狀態"""

    robot_id: str
    current_node: str  # 當前所在節點
    next_deliver_k: int = 1  # 下一個必須送的訂單號（1-indexed）
    picked_mask: int = 0  # 已取未送的掩碼
    all_orders: Dict[int, Order] = field(
        default_factory=dict
    )  # k -> Order (1-indexed)
    last_replan_time: Optional[datetime] = None
    last_plan_cost: Optional[int] = None  # cm
    plan_actions: List[str] = field(default_factory=list)
    plan_stops: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """序列化為 dict"""
        return {
            "robot_id": self.robot_id,
            "current_node": self.current_node,
            "next_deliver_k": self.next_deliver_k,
            "picked_mask": self.picked_mask,
            "orders_count": len(self.all_orders),
            "last_plan_cost": self.last_plan_cost,
            "plan_actions": self.plan_actions,
            "plan_stops": self.plan_stops,
            "last_replan_time": self.last_replan_time.isoformat() if self.last_replan_time else None,
        }

    def get_pending_orders(self) -> List[Tuple[int, Order]]:
        """取得所有未送的訂單"""
        return [(k, o) for k, o in self.all_orders.items() if o.status != "delivered"]

    def get_picked_orders(self) -> List[Tuple[int, Order]]:
        """取得所有已取未送的訂單"""
        return [(k, o) for k, o in self.all_orders.items() if o.status == "picked"]

    def get_pending_count(self) -> int:
        """取得待送訂單數"""
        return sum(1 for o in self.all_orders.values() if o.status != "delivered")


class GlobalPlannerState:
    """全局規劃狀態管理（線程安全）"""

    def __init__(self):
        self._lock = threading.RLock()  # 保護所有狀態變更
        self.robots: Dict[str, RobotState] = {}
        self.order_counter: int = 0  # 生成訂單 ID

    def add_robot(self, robot_id: str, start_node: str) -> RobotState:
        """初始化小車"""
        with self._lock:
            state = RobotState(robot_id=robot_id, current_node=start_node)
            self.robots[robot_id] = state
            return state

    def get_robot(self, robot_id: str) -> Optional[RobotState]:
        """取得小車狀態（唯讀，不需鎖）"""
        return self.robots.get(robot_id)

    def add_order(
        self,
        robot_id: str,
        shop_node: str,
        drop_node: str,
        order_id: Optional[str] = None,
        drop_coords: Optional[Tuple[float, float]] = None,
    ) -> Optional[str]:
        """
        添加新訂單到小車的待執行列表

        :param order_id: DB 訂單 ID（若提供則直接使用，否則自動生成）
        :return: order_id（若成功）或 None（若失敗）
        """
        with self._lock:
            robot = self.get_robot(robot_id)
            if not robot:
                return None

            if order_id is None:
                self.order_counter += 1
                order_id = f"ORDER-{self.order_counter:06d}"

            # 訂單編號（1-indexed）
            k = len(robot.all_orders) + 1
            order = Order(
                order_id=order_id,
                shop_node=shop_node,
                drop_node=drop_node,
                drop_coords=drop_coords,
            )
            robot.all_orders[k] = order
            return order_id

    def update_robot_location(self, robot_id: str, node: str) -> bool:
        """更新小車位置"""
        with self._lock:
            robot = self.get_robot(robot_id)
            if not robot:
                return False
            robot.current_node = node
            return True

    def mark_order_picked(self, robot_id: str, k: int) -> bool:
        """標記訂單已取"""
        with self._lock:
            robot = self.get_robot(robot_id)
            if not robot or k not in robot.all_orders:
                return False

            order = robot.all_orders[k]
            order.status = "picked"
            order.picked_at = datetime.now()

            # 更新 picked_mask
            robot.picked_mask |= 1 << (k - 1)
            return True

    def mark_order_delivered(self, robot_id: str, k: int) -> bool:
        """標記訂單已送"""
        with self._lock:
            robot = self.get_robot(robot_id)
            if not robot or k not in robot.all_orders:
                return False

            order = robot.all_orders[k]
            order.status = "delivered"
            order.delivered_at = datetime.now()

            # 更新 picked_mask（移除該位）
            robot.picked_mask &= ~(1 << (k - 1))

            # 更新 next_deliver_k
            robot.next_deliver_k = k + 1
            return True

    def update_plan(
        self,
        robot_id: str,
        plan_actions: List[str],
        plan_stops: List[str],
        plan_cost: int,
    ) -> bool:
        """更新規劃結果"""
        with self._lock:
            robot = self.get_robot(robot_id)
            if not robot:
                return False

            robot.plan_actions = plan_actions
            robot.plan_stops = plan_stops
            robot.last_plan_cost = plan_cost
            robot.last_replan_time = datetime.now()
            return True

    def get_robot_orders_as_algorithm_input(
        self, robot_id: str
    ) -> Optional[List[Tuple[int, int]]]:
        """
        取得小車的訂單，以 algorithm 輸入格式返回

        :return: 訂單列表 [(shop_node_id, drop_node_id), ...] 或 None
        
        注意：需要由上層提供 node_id 映射（例如 {"A": 0, "X1": 1, ...}）
        """
        robot = self.get_robot(robot_id)
        if not robot:
            return None

        # 返回 (shop_node, drop_node) 的簡單列表
        # 注意：這裡返回的是節點名稱字串，上層需負責轉換為節點 ID
        orders = []
        for k in sorted(robot.all_orders.keys()):
            order = robot.all_orders[k]
            orders.append((order.shop_node, order.drop_node))

        return orders


# 全局實例（單線程 dev 模式）
_global_planner_state = GlobalPlannerState()


def get_global_state() -> GlobalPlannerState:
    """取得全局規劃狀態"""
    return _global_planner_state

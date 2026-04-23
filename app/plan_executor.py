"""
Plan Executor

Bridges robot/{robot_id}/plan → car/cmd

Flow:
  1. Receive plan (stops + actions) from planner via MQTT
  2. Expand stops into full node path using dijkstra (prepends current position)
  3. When car reports position via car/node_id (AprilTag confirmed):
     a. Map AprilTag numeric ID → node name using map.json apriltag_id field
     b. Advance position in full_path
     c. If at a PICKUP stop  → send wait_weight + auto mark-picked
     d. If at a DELIVER stop → auto mark-delivered + clear + replan
     e. Otherwise (transit)  → compute turn and send car/cmd
"""

import logging
import re
import threading
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

_PICKUP_RE = re.compile(r"PICKUP order (\d+)")
_DELIVER_RE = re.compile(r"DELIVER order (\d+)")

# Lazy cache: AprilTag integer ID → node name string ("A", "B", ...)
_tag_to_node_cache: Dict[int, str] = {}


def _get_tag_to_node() -> Dict[int, str]:
    global _tag_to_node_cache
    if not _tag_to_node_cache:
        from .state import MAP_STORE
        map_data = next(iter(MAP_STORE.values()), None)
        if map_data:
            for node in map_data.nodes:
                if node.apriltag_id is not None:
                    _tag_to_node_cache[node.apriltag_id] = node.id
    return _tag_to_node_cache


def _parse_stop_actions(actions: List[str]) -> List[dict]:
    """Parse action strings into per-stop metadata: [{type, order_k}]."""
    result = []
    for action in actions:
        m = _PICKUP_RE.search(action)
        if m:
            result.append({"type": "PICKUP", "order_k": int(m.group(1))})
            continue
        m = _DELIVER_RE.search(action)
        if m:
            result.append({"type": "DELIVER", "order_k": int(m.group(1))})
            continue
        result.append({"type": "NONE", "order_k": None})
    return result


class PlanExecutor:
    def __init__(self):
        self._lock = threading.Lock()
        self.full_path: List[str] = []      # expanded path including start node
        self.stops: List[str] = []           # action stops from plan
        self.stop_actions: List[dict] = []   # [{type, order_k}] aligned with stops
        self.stop_pointer: int = 0           # next stop index to process
        self.current_step: int = 0           # current index in full_path
        self.prev_node: Optional[str] = None
        self.current_node: Optional[str] = None
        self.robot_id: Optional[str] = None
        self._active: bool = False

    # ------------------------------------------------------------------ #
    # MQTT callbacks                                                       #
    # ------------------------------------------------------------------ #

    def on_new_plan(self, topic: str, payload: dict):
        """Called when robot/{robot_id}/plan is received."""
        stops: List[str] = payload.get("stops", [])
        actions: List[str] = payload.get("actions", [])
        robot_id: str = (
            payload.get("robot_id")
            or (topic.split("/")[1] if "/" in topic else "unknown")
        )

        if not stops:
            logger.warning("PlanExecutor: received empty plan, ignoring")
            return

        stop_actions = _parse_stop_actions(actions)

        # Prepend robot's current node so full_path covers the whole journey
        from .planner_state import get_global_state
        robot = get_global_state().get_robot(robot_id)
        start_node = robot.current_node if robot else None
        full_path = self._compute_full_path(start_node, stops)

        with self._lock:
            self.robot_id = robot_id
            self.full_path = full_path
            self.stops = stops
            self.stop_actions = stop_actions
            self.stop_pointer = 0
            self.current_step = 0
            self.prev_node = None
            self.current_node = start_node  # init so first turn uses correct heading
            self._active = True

        logger.info(
            f"PlanExecutor: new plan robot={robot_id} "
            f"path={full_path} stops={stops} actions={stop_actions}"
        )
        self._publish("car/cmd", {"cmd": "forward", "speed": 100})

    def on_weight_event(self, topic: str, payload: dict):
        """Called when car/weight_event is received (weight sensor confirmed)."""
        event = payload.get("event", "")
        if event == "loaded":
            logger.info("PlanExecutor: weight loaded → sending next direction")
            self._send_next_direction()

    def on_node_update(self, topic: str, payload: dict):
        """Called when car/node_id is received (AprilTag confirmed arrival)."""
        raw = payload.get("tag_id", payload.get("node", ""))
        node = self._resolve_node(raw)
        if not node:
            return

        with self._lock:
            robot_id = self.robot_id
            self.prev_node = self.current_node
            self.current_node = node
            full_path = list(self.full_path)
            active = self._active
            stops = list(self.stops)
            stop_pointer = self.stop_pointer

        # Sync position to GlobalPlannerState so replan uses correct start node
        if robot_id:
            from .planner_state import get_global_state
            get_global_state().update_robot_location(robot_id, node)

        if not active or not full_path:
            return

        logger.info(f"PlanExecutor: car at node '{node}'")

        # Advance current_step: scan forward for next match (handles repeated nodes)
        with self._lock:
            for i in range(self.current_step, len(full_path)):
                if full_path[i] == node:
                    self.current_step = i
                    break

        # Check if this is the next expected action stop
        if stop_pointer < len(stops) and node == stops[stop_pointer]:
            with self._lock:
                action_meta = (
                    self.stop_actions[stop_pointer]
                    if stop_pointer < len(self.stop_actions)
                    else {"type": "NONE", "order_k": None}
                )
                self.stop_pointer += 1
            self._handle_stop_action(node, action_meta)
        else:
            # Transit node — just keep moving
            self._send_next_direction()

    # ------------------------------------------------------------------ #
    # Stop action handlers                                                 #
    # ------------------------------------------------------------------ #

    def _handle_stop_action(self, node: str, action_meta: dict):
        action_type = action_meta.get("type", "NONE")
        order_k = action_meta.get("order_k")

        with self._lock:
            robot_id = self.robot_id

        if action_type == "PICKUP" and order_k is not None and robot_id:
            logger.info(f"PlanExecutor: PICKUP order {order_k} at {node}")
            self._auto_mark_picked(robot_id, order_k)
            self._send_next_direction()

        elif action_type == "DELIVER" and order_k is not None and robot_id:
            logger.info(f"PlanExecutor: DELIVER order {order_k} at {node}")
            self._auto_mark_delivered(robot_id, order_k)
            # _auto_mark_delivered decides: replan or stop

        else:
            self._send_next_direction()

    def _auto_mark_picked(self, robot_id: str, order_k: int):
        from .planner_state import get_global_state
        from .ws import update_order_in_db
        from .mqtt_bridge import _schedule_ws_broadcast

        state = get_global_state()
        robot = state.get_robot(robot_id)
        if not robot:
            return
        order = robot.all_orders.get(order_k)
        if state.mark_order_picked(robot_id, order_k):
            if order and order.order_id:
                update_order_in_db(order.order_id, "PICKED")
                _schedule_ws_broadcast({
                    "type": "order_status",
                    "order_id": order.order_id,
                    "status": "PICKED",
                    "robot_id": robot_id,
                })
            logger.info(f"PlanExecutor: auto marked order {order_k} PICKED for {robot_id}")

    def _auto_mark_delivered(self, robot_id: str, order_k: int):
        from .planner_state import get_global_state
        from .ws import update_order_in_db
        from .mqtt_bridge import _schedule_ws_broadcast

        state = get_global_state()
        robot = state.get_robot(robot_id)
        if not robot:
            return
        order = robot.all_orders.get(order_k)

        if not state.mark_order_delivered(robot_id, order_k):
            return

        if order and order.order_id:
            update_order_in_db(order.order_id, "DELIVERED")
            _schedule_ws_broadcast({
                "type": "order_status",
                "order_id": order.order_id,
                "status": "DELIVERED",
                "robot_id": robot_id,
            })
        logger.info(f"PlanExecutor: auto marked order {order_k} DELIVERED for {robot_id}")

        # Auto-clear delivered orders, then replan remaining
        state.clear_delivered_orders(robot_id)
        updated = state.get_robot(robot_id)
        if updated and updated.get_pending_count() > 0:
            self._trigger_replan(robot_id)
        else:
            logger.info(f"PlanExecutor: no more orders for {robot_id}, stopping")
            with self._lock:
                self._active = False
            self._publish("car/cmd", {"cmd": "stop", "speed": 0})

    def _trigger_replan(self, robot_id: str):
        """Run replan and publish new plan via MQTT (called from MQTT thread)."""
        from .dispatcher import _run_replan
        from .mqtt_bridge import get_mqtt_bridge

        ok, actions, stops, cost = _run_replan(robot_id)
        if ok:
            try:
                bridge = get_mqtt_bridge()
                bridge.publish_plan(robot_id, actions, stops)
                logger.info(f"PlanExecutor: replan published for {robot_id}, cost={cost}")
            except Exception as e:
                logger.warning(f"PlanExecutor: replan publish failed: {e}")
        else:
            logger.info(f"PlanExecutor: replan found no orders for {robot_id}")
            with self._lock:
                self._active = False
            self._publish("car/cmd", {"cmd": "stop", "speed": 0})

    # ------------------------------------------------------------------ #
    # Navigation helpers                                                   #
    # ------------------------------------------------------------------ #

    def _send_next_direction(self):
        with self._lock:
            step = self.current_step
            full_path = list(self.full_path)
            prev = self.prev_node
            current = self.current_node

        if not full_path or step >= len(full_path) - 1:
            logger.info("PlanExecutor: reached end of path, stopping")
            self._publish("car/cmd", {"cmd": "stop", "speed": 0})
            with self._lock:
                self._active = False
            return

        next_node = full_path[step + 1]
        cmd = self._determine_direction(prev, current, next_node)
        logger.info(f"PlanExecutor: {prev}→{current}→{next_node} = {cmd}")
        self._publish("car/cmd", {"cmd": cmd, "speed": 100})

    def _resolve_node(self, raw) -> Optional[str]:
        """Convert AprilTag ID (int or numeric str) → node name; pass through if already a name."""
        if isinstance(raw, int):
            return _get_tag_to_node().get(raw)
        s = str(raw).strip()
        if not s:
            return None
        try:
            return _get_tag_to_node().get(int(s), s)
        except ValueError:
            return s  # already "A", "B", etc.

    def _compute_full_path(self, start_node: Optional[str], stops: List[str]) -> List[str]:
        from .graph import dijkstra
        from .state import GRAPH_STORE

        graph = next(iter(GRAPH_STORE.values()), None)
        if not graph or not stops:
            return list(stops)

        # Build full sequence: start → stop1 → stop2 → ...
        sequence: List[str] = []
        if start_node and (not stops or stops[0] != start_node):
            sequence = [start_node] + list(stops)
        else:
            sequence = list(stops)

        if len(sequence) < 2:
            return sequence

        full_path: List[str] = []
        for i in range(len(sequence) - 1):
            try:
                path, _ = dijkstra(graph, sequence[i], sequence[i + 1])
                full_path.extend(path[1:] if full_path else path)
            except Exception as e:
                logger.error(f"PlanExecutor: dijkstra {sequence[i]}→{sequence[i+1]} failed: {e}")
                return list(stops)

        return full_path

    def _determine_direction(self, prev: Optional[str], current: Optional[str], next_node: str) -> str:
        """Cross product of (prev→current) × (current→next) to determine left/right/forward."""
        if not prev or not current:
            return "forward"

        from .state import MAP_STORE
        map_data = next(iter(MAP_STORE.values()), None)
        if not map_data:
            return "forward"

        coords = {n.id: (n.x, n.y) for n in map_data.nodes}
        if prev not in coords or current not in coords or next_node not in coords:
            return "forward"

        px, py = coords[prev]
        cx, cy = coords[current]
        nx, ny = coords[next_node]

        hx, hy = cx - px, cy - py   # heading vector
        dx, dy = nx - cx, ny - cy   # desired direction

        # Map uses screen coords (y increases downward), so cross product sign is flipped
        # vs standard math coords: positive cross = clockwise = right turn
        cross = hx * dy - hy * dx
        if cross > 0:
            return "right"
        elif cross < 0:
            return "left"
        else:
            return "forward" if (hx * dx + hy * dy) >= 0 else "backward"

    def _publish(self, topic: str, payload: dict):
        from .mqtt_bridge import get_mqtt_bridge
        bridge = get_mqtt_bridge()
        bridge.client.publish(topic, payload)


_executor: Optional[PlanExecutor] = None


def get_plan_executor() -> PlanExecutor:
    global _executor
    if _executor is None:
        _executor = PlanExecutor()
    return _executor

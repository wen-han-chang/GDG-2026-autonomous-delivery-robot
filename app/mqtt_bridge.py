"""
MQTT 橋接層

職責：
1. 連接 MQTT broker
2. 訂閱小車位置與狀態更新 （robot/{robot_id}/telemetry）
3. 發佈規劃指令與重新規劃請求 （robot/{robot_id}/plan）

訊息格式：
  - 小車發佈位置: {"robot_id": "R001", "node": "A", "timestamp": "2026-03-04T..."}
  - 後端發佈規劃: {"robot_id": "R001", "actions": [...], "stops": [...]}

設定環境變數：
  MQTT_BROKER_URL=localhost   (broker hostname)
  MQTT_BROKER_PORT=1883
  MQTT_USE_MOCK=true          (開發測試用 mock；false 啟用真實 paho-mqtt)
"""

import asyncio
import json
import logging
import threading
from typing import Callable, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Mock 客戶端（開發測試用）
# ─────────────────────────────────────────────

class MockMQTTClient:
    """
    簡易 Mock MQTT 客戶端（用於開發測試）

    生產環境應改用 paho-mqtt（設定 MQTT_USE_MOCK=false）
    """

    def __init__(self, broker_url: str = "mqtt://localhost:1883"):
        self.broker_url = broker_url
        self.is_connected = False
        self.subscriptions: Dict[str, Callable] = {}
        logger.info(f"MockMQTTClient initialized (url={broker_url})")

    def connect(self) -> bool:
        logger.info(f"[Mock] Connecting to {self.broker_url}")
        self.is_connected = True
        return True

    def disconnect(self):
        self.is_connected = False
        logger.info("[Mock] Disconnected")

    def subscribe(self, topic: str, callback: Callable) -> bool:
        self.subscriptions[topic] = callback
        logger.info(f"[Mock] Subscribed to {topic}")
        return True

    def publish(self, topic: str, payload: dict) -> bool:
        if not self.is_connected:
            logger.warning("[Mock] Not connected, cannot publish")
            return False
        logger.debug(f"[Mock] Published to {topic}: {json.dumps(payload)}")
        return True

    def simulate_receive(self, topic: str, payload: dict):
        """（測試用）模擬接收訊息"""
        if topic in self.subscriptions:
            self.subscriptions[topic](topic, payload)


# ─────────────────────────────────────────────
# 真實 paho-mqtt 客戶端
# ─────────────────────────────────────────────

class RealPahoClient:
    """
    paho-mqtt 封裝（生產環境用）

    使用 loop_start() 在背景執行緒中處理 MQTT 網路事件，
    不阻塞 FastAPI 的 asyncio 事件迴圈。
    """

    def __init__(self, broker_host: str, broker_port: int = 1883):
        import paho.mqtt.client as mqtt  # lazy import，開發測試不強制安裝

        self.broker_host = broker_host
        self.broker_port = broker_port
        self.is_connected = False
        self._subscriptions: Dict[str, Callable] = {}
        self._lock = threading.Lock()

        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

        # 保存主事件迴圈供跨執行緒的 asyncio 呼叫
        try:
            self._loop: Optional[asyncio.AbstractEventLoop] = asyncio.get_event_loop()
        except RuntimeError:
            self._loop = None

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            self.is_connected = True
            logger.info(f"MQTT connected to {self.broker_host}:{self.broker_port}")
            # 重連後重新訂閱所有主題
            with self._lock:
                for topic in self._subscriptions:
                    client.subscribe(topic)
        else:
            logger.error(f"MQTT connect failed, reason_code={reason_code}")

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        self.is_connected = False
        logger.warning(f"MQTT disconnected (reason_code={reason_code})")

    def _on_message(self, client, userdata, message):
        import paho.mqtt.client as mqtt

        topic = message.topic
        try:
            payload = json.loads(message.payload.decode())
        except Exception:
            logger.warning(f"Failed to decode MQTT payload on {topic}")
            return

        with self._lock:
            callbacks = list(self._subscriptions.items())

        for subscribed_topic, callback in callbacks:
            if mqtt.topic_matches_sub(subscribed_topic, topic):
                try:
                    callback(topic, payload)
                except Exception as e:
                    logger.exception(f"MQTT callback error on {topic}: {e}")

    def connect(self) -> bool:
        try:
            self._client.connect(self.broker_host, self.broker_port, keepalive=60)
            self._client.loop_start()  # 背景執行緒，不阻塞 asyncio
            logger.info(f"MQTT client loop started")
            return True
        except Exception as e:
            logger.error(f"MQTT connect exception: {e}")
            return False

    def disconnect(self):
        self._client.loop_stop()
        self._client.disconnect()
        self.is_connected = False

    def subscribe(self, topic: str, callback: Callable) -> bool:
        with self._lock:
            self._subscriptions[topic] = callback
        if self.is_connected:
            self._client.subscribe(topic)
        logger.info(f"MQTT subscribed to {topic}")
        return True

    def publish(self, topic: str, payload: dict) -> bool:
        if not self.is_connected:
            logger.warning(f"MQTT not connected, cannot publish to {topic}")
            return False
        try:
            self._client.publish(topic, json.dumps(payload))
            logger.debug(f"MQTT published to {topic}")
            return True
        except Exception as e:
            logger.error(f"MQTT publish error: {e}")
            return False


# ─────────────────────────────────────────────
# MQTT 橋接層
# ─────────────────────────────────────────────

class MQTTBridge:
    """
    MQTT 橋接層

    向小車、規劃服務系統提供發布/訂閱介面
    """

    def __init__(self, broker_url: str = "localhost", broker_port: int = 1883, use_mock: bool = True):
        self.broker_url = broker_url
        self.broker_port = broker_port
        self.use_mock = use_mock
        self.robot_telemetry_callbacks: Dict[str, Callable] = {}

        if use_mock:
            self.client = MockMQTTClient(f"mqtt://{broker_url}:{broker_port}")
        else:
            self.client = RealPahoClient(broker_url, broker_port)

    def start(self) -> bool:
        """啟動 MQTT 橋接"""
        import time
        for attempt in range(8):
            if self.client.connect():
                break
            logger.warning(f"MQTT connect failed (attempt {attempt + 1}/8), retrying in 3s...")
            time.sleep(3)
        else:
            logger.error("Failed to connect to MQTT broker after 8 attempts")
            return False

        def on_telemetry(topic: str, payload: dict):
            """小車 telemetry 回調：更新 GlobalPlannerState 並廣播 WebSocket"""
            robot_id = payload.get("robot_id")
            node = payload.get("node")

            if robot_id and node:
                from .planner_state import get_global_state
                get_global_state().update_robot_location(robot_id, node)
                logger.info(f"Telemetry: robot {robot_id} at node {node}")

                # 廣播給前端（跨執行緒安全）
                _schedule_ws_broadcast({
                    "type": "robot_location",
                    "robot_id": robot_id,
                    "node": node,
                })

            # 呼叫已註冊的個別回調
            if robot_id and robot_id in self.robot_telemetry_callbacks:
                self.robot_telemetry_callbacks[robot_id](payload)

        self.client.subscribe("robot/+/telemetry", on_telemetry)

        # Plan executor: robot/+/plan → car/cmd
        from .plan_executor import get_plan_executor
        executor = get_plan_executor()
        self.client.subscribe("robot/+/plan", executor.on_new_plan)
        self.client.subscribe("car/node_id", executor.on_node_update)
        self.client.subscribe("car/weight_event", executor.on_weight_event)

        self.client.subscribe("car/status", lambda t, p: None)

        logger.info("MQTT bridge started")
        return True

    def stop(self):
        """停止 MQTT 橋接"""
        self.client.disconnect()

    def register_telemetry_callback(self, robot_id: str, callback: Callable):
        """註冊小車 telemetry 回調"""
        self.robot_telemetry_callbacks[robot_id] = callback

    def is_connected(self) -> bool:
        """回傳 MQTT client 當前是否已連線。"""
        return bool(getattr(self.client, "is_connected", False))

    def publish_plan(self, robot_id: str, plan_actions: list, plan_stops: list) -> bool:
        """發佈規劃結果給小車（topic: robot/{robot_id}/plan）"""
        topic = f"robot/{robot_id}/plan"
        payload = {
            "robot_id": robot_id,
            "actions": plan_actions,
            "stops": plan_stops,
            "timestamp": datetime.now().isoformat(),
        }
        return self.client.publish(topic, payload)

    def publish_replan_request(self, robot_id: str) -> bool:
        """發佈重新規劃請求（topic: robot/{robot_id}/replan-req）"""
        topic = f"robot/{robot_id}/replan-req"
        payload = {
            "robot_id": robot_id,
            "request_time": datetime.now().isoformat(),
        }
        return self.client.publish(topic, payload)

    def simulate_robot_telemetry(self, robot_id: str, node: str):
        """（測試用）模擬小車發送位置更新"""
        if not self.use_mock:
            raise RuntimeError("simulate_robot_telemetry only works with mock client")
        payload = {
            "robot_id": robot_id,
            "node": node,
            "timestamp": datetime.now().isoformat(),
        }
        self.client.simulate_receive("robot/+/telemetry", payload)


# ─────────────────────────────────────────────
# 跨執行緒 WebSocket 廣播輔助函式
# ─────────────────────────────────────────────

_main_event_loop: Optional[asyncio.AbstractEventLoop] = None


def set_main_event_loop(loop: asyncio.AbstractEventLoop):
    """由 startup_event() 呼叫，儲存主 asyncio 事件迴圈供跨執行緒使用"""
    global _main_event_loop
    _main_event_loop = loop


def _schedule_ws_broadcast(msg: dict):
    """從任意執行緒安全地排程 WebSocket 廣播"""
    if _main_event_loop is None or not _main_event_loop.is_running():
        return
    from .ws import broadcast
    asyncio.run_coroutine_threadsafe(broadcast(msg), _main_event_loop)


# ─────────────────────────────────────────────
# 全局實例
# ─────────────────────────────────────────────

_mqtt_bridge: Optional[MQTTBridge] = None


def get_mqtt_bridge(
    broker_url: str = "localhost",
    broker_port: int = 1883,
    use_mock: bool = True,
) -> MQTTBridge:
    """取得全局 MQTT 橋接實例（首次呼叫時建立）"""
    global _mqtt_bridge
    if _mqtt_bridge is None:
        _mqtt_bridge = MQTTBridge(broker_url, broker_port, use_mock)
    return _mqtt_bridge

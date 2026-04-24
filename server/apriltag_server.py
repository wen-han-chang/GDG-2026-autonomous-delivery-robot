"""
GDG Delivery Robot - Backend Server

流程:
  1. ESP32-CAM 開機 → 發佈 car/cam_ip (自己的 HTTP Server IP)
  2. 主控 ESP32 到路口 → 發佈 car/status {state: "at_node"}
  3. 後端收到 → HTTP GET http://<cam_ip>/capture 拿 JPEG
  4. Python apriltag 辨識 → 知道在哪個節點
  5. 最短路徑演算法 → 發佈 car/cmd (left/right/forward/wait_weight)
  6. 重量確認後繼續前進

安裝依賴:
  pip install -r requirements.txt

使用:
  python apriltag_server.py
"""

import json
import logging
import urllib.request
import urllib.error

import cv2
import numpy as np
import pupil_apriltags as apriltag
import networkx as nx
import paho.mqtt.client as mqtt

# ─── Logging ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

# ─── Config ───────────────────────────────────────────────────
BROKER = "10.86.140.175"
PORT   = 1883

TOPIC_CAM_IP      = "car/cam_ip"       # ESP32-CAM 發佈的 IP
TOPIC_NODE_UPDATE = "car/node_update"  # 發佈辨識到的節點
TOPIC_STATUS      = "car/status"       # 主控發佈的狀態
TOPIC_CMD         = "car/cmd"          # 發佈給主控的指令
TOPIC_WEIGHT      = "car/weight_event" # 主控發佈的重量事件

DEST_NODE     = 5    # 目的地節點 (依實際情況修改)
DEFAULT_SPEED = 180
CAM_TIMEOUT   = 3.0  # HTTP 拍照逾時 (秒)

# ─── 地圖定義 ─────────────────────────────────────────────────
# node ID = 地板上的 AprilTag tag_id
# heading: 從 src 走到 dst 的車頭方向 (0=北/前, 90=東/右, 180=南/後, 270=西/左)
#
# 範例地圖 (依你的實際場地修改):
#   [0] ── [1] ── [2] ── [3]
#                  |
#                 [4] ── [5]
#
GRAPH = nx.DiGraph()
GRAPH.add_edges_from([
    (0, 1, {"heading": 90}),
    (1, 0, {"heading": 270}),
    (1, 2, {"heading": 90}),
    (2, 1, {"heading": 270}),
    (2, 3, {"heading": 90}),
    (3, 2, {"heading": 270}),
    (2, 4, {"heading": 180}),
    (4, 2, {"heading": 0}),
    (4, 5, {"heading": 90}),
    (5, 4, {"heading": 270}),
])

# ─── Runtime State ────────────────────────────────────────────
cam_ip      = None  # ESP32-CAM 的 IP，從 MQTT 取得
car_heading = 90    # 車頭當前朝向 (初始值，依實際出發方向修改)
current_node = -1

# ─── AprilTag Detector ────────────────────────────────────────
detector = apriltag.Detector(families="tag36h11")

# ─── 從 ESP32-CAM 抓圖 ────────────────────────────────────────
def fetch_frame() -> bytes | None:
    """HTTP GET http://<cam_ip>/capture，回傳 JPEG bytes 或 None。"""
    if not cam_ip:
        log.warning("[CAM] cam_ip not yet received, cannot fetch frame")
        return None
    url = f"http://{cam_ip}/capture"
    try:
        with urllib.request.urlopen(url, timeout=CAM_TIMEOUT) as resp:
            data = resp.read()
            log.info(f"[CAM] Fetched {len(data)} bytes from {url}")
            return data
    except urllib.error.URLError as e:
        log.error(f"[CAM] HTTP fetch failed: {e}")
        return None

# ─── AprilTag Detection ───────────────────────────────────────
def detect_apriltag(jpeg_bytes: bytes) -> int | None:
    """解碼 JPEG → AprilTag 辨識 → 回傳 tag_id 或 None。"""
    nparr = np.frombuffer(jpeg_bytes, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
    if frame is None:
        log.warning("[AprilTag] Failed to decode JPEG")
        return None

    results = detector.detect(frame)
    if not results:
        log.info("[AprilTag] No tag detected")
        return None

    # 取 decision_margin 最高的（最可信）
    best = max(results, key=lambda r: r.decision_margin)
    log.info(f"[AprilTag] tag_id={best.tag_id}  margin={best.decision_margin:.2f}")
    return best.tag_id

# ─── 路徑規劃 ─────────────────────────────────────────────────
def plan_route(current: int, destination: int) -> list[int]:
    try:
        path = nx.shortest_path(GRAPH, current, destination, weight=None)
        log.info(f"[Route] {current} → {destination}: {path}")
        return path
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        log.warning(f"[Route] No path {current} → {destination}")
        return []

def get_turn_cmd(cur_node: int, next_node: int, heading: int) -> str:
    """根據車頭朝向和目標方向算出 left/right/forward。"""
    edge = GRAPH.get_edge_data(cur_node, next_node)
    if not edge:
        return "forward"

    target = edge.get("heading", heading)
    diff   = (target - heading + 360) % 360

    if diff == 0:
        return "forward"
    elif diff == 90:
        return "right"
    elif diff == 270:
        return "left"
    else:
        return "right"  # 180° U-turn: 右轉兩次

# ─── MQTT Handlers ────────────────────────────────────────────
MAX_CAPTURE_ATTEMPTS = 5   # 最多拍幾張嘗試辨識

def handle_at_node(client: mqtt.Client, node: int) -> None:
    """到路口時：拍照辨識 AprilTag → 路徑規劃 → 發指令。"""
    global current_node, car_heading

    # 1. 最多拍 MAX_CAPTURE_ATTEMPTS 張，辨識到就停
    tag_id = None
    for attempt in range(1, MAX_CAPTURE_ATTEMPTS + 1):
        jpeg = fetch_frame()
        if jpeg is None:
            log.warning(f"[Route] Capture {attempt}/{MAX_CAPTURE_ATTEMPTS} failed (no frame)")
            continue
        tag_id = detect_apriltag(jpeg)
        if tag_id is not None:
            log.info(f"[AprilTag] Detected on attempt {attempt}/{MAX_CAPTURE_ATTEMPTS}")
            break
        log.warning(f"[Route] Capture {attempt}/{MAX_CAPTURE_ATTEMPTS}: no tag detected")

    if tag_id is None:
        log.error("[Route] All capture attempts failed, stopping car")
        client.publish(TOPIC_CMD, json.dumps({"cmd": "stop", "speed": 0}))
        return

    # 3. 更新節點，發佈給主控
    current_node = tag_id
    client.publish(TOPIC_NODE_UPDATE, json.dumps({"tag_id": tag_id}))
    log.info(f"[Node] Confirmed: node {tag_id}")

    # 4. 路徑規劃
    path = plan_route(tag_id, DEST_NODE)

    if not path:
        cmd = {"cmd": "stop", "speed": 0}
        log.warning("[Route] No path found")

    elif len(path) == 1:
        # 已在目的地
        cmd = {"cmd": "wait_weight", "speed": 0}
        log.info("[Route] Destination reached! Waiting for weight change.")

    else:
        next_node = path[1]
        direction = get_turn_cmd(tag_id, next_node, car_heading)

        # 更新車頭朝向
        edge = GRAPH.get_edge_data(tag_id, next_node)
        if edge:
            car_heading = edge.get("heading", car_heading)

        cmd = {"cmd": direction, "speed": DEFAULT_SPEED}
        log.info(f"[Route] Next node {next_node}, cmd={direction}, "
                 f"new heading={car_heading}")

    client.publish(TOPIC_CMD, json.dumps(cmd))


def handle_status(client: mqtt.Client, payload: str) -> None:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return

    state = data.get("state", "")
    node  = data.get("node", -1)
    log.info(f"[Status] state={state}  node={node}")

    if state == "at_node":
        handle_at_node(client, node)

    elif state == "weight_confirmed":
        cmd = {"cmd": "forward", "speed": DEFAULT_SPEED}
        client.publish(TOPIC_CMD, json.dumps(cmd))
        log.info("[Route] Weight confirmed, resuming...")


def handle_weight_event(payload: str) -> None:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return
    log.info(f"[Weight] event={data.get('event')}  "
             f"weight={data.get('weight_g', 0):.1f}g  "
             f"node={data.get('node', -1)}")


# ─── MQTT Setup ───────────────────────────────────────────────
def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code != 0:
        log.error(f"[MQTT] Connect failed rc={reason_code}")
        return
    log.info("[MQTT] Connected to broker")
    client.subscribe(TOPIC_CAM_IP)      # ESP32-CAM 的 IP
    client.subscribe(TOPIC_STATUS)
    client.subscribe(TOPIC_WEIGHT)


def on_message(client, userdata, msg):
    global cam_ip
    topic   = msg.topic
    payload = msg.payload

    if topic == TOPIC_CAM_IP:
        # ESP32-CAM 發佈了自己的 IP
        cam_ip = payload.decode().strip()
        log.info(f"[CAM] IP updated: {cam_ip}  "
                 f"→ http://{cam_ip}/capture")

    elif topic == TOPIC_STATUS:
        handle_status(client, payload.decode())

    elif topic == TOPIC_WEIGHT:
        handle_weight_event(payload.decode())


def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message

    log.info(f"[Server] Connecting to {BROKER}:{PORT}...")
    client.connect(BROKER, PORT, keepalive=60)

    log.info("[Server] Running. Ctrl+C to stop.")
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        log.info("[Server] Stopped.")
        client.disconnect()


if __name__ == "__main__":
    main()

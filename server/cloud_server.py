"""
GDG Delivery Robot - Cloud Server (AWS 部署版)

差異：
  本地版 (apriltag_server.py) 用 HTTP GET 拉 ESP32-CAM 的圖
  雲端版 (cloud_server.py)   由 ESP32-CAM 主動 POST JPEG 過來

流程:
  1. ESP32-CAM 開機 → 發佈 car/cam_ip (retained)
  2. 主控 ESP32 到路口 → 發佈 car/at_node
  3. 後端收到 → 連續發佈 car/capture_req (最多 MAX_CAPTURES 次)
  4. ESP32-CAM 拍照 → POST /upload-image
  5. 收集辨識結果，取 decision_margin 最高者
  6. 發佈 car/node_id + car/cmd

啟動:
  uvicorn cloud_server:app --host 0.0.0.0 --port 8000
"""

import json
import logging
import threading
import os
import time
from collections import defaultdict

import cv2
import numpy as np
import pupil_apriltags as apriltag
import networkx as nx
import paho.mqtt.client as mqtt
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.requests import ClientDisconnect

# ─── Logging ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

# ─── Config (從環境變數讀取，方便容器化) ──────────────────────
BROKER        = os.getenv("MQTT_HOST", "localhost")
PORT          = int(os.getenv("MQTT_PORT", "1883"))
DEST_NODE     = int(os.getenv("DEST_NODE", "5"))
DEFAULT_SPEED = int(os.getenv("DEFAULT_SPEED", "180"))
MAX_CAPTURES  = int(os.getenv("MAX_CAPTURES", "1"))   # 連拍張數 (燒錄 VGA 韌體後改回 3)

TOPIC_CAM_IP      = "car/cam_ip"
TOPIC_AT_NODE     = "car/at_node"
TOPIC_CAPTURE_REQ = "car/capture_req"
TOPIC_NODE_ID     = "car/node_id"
TOPIC_CMD         = "car/cmd"
TOPIC_WEIGHT      = "car/weight_event"

# ─── 地圖定義 ─────────────────────────────────────────────────
#   [0] ── [1] ── [2] ── [3]
#                  |
#                 [4] ── [5]
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
_state_lock = threading.Lock()
car_state = {
    "heading":        90,
    "current_node":   -1,
    "capture_count":  0,     # 已發出的 capture_req 次數
    "collected":      [],    # 收集的 jpeg bytes，拍完再一起辨識
}
mqtt_client: mqtt.Client | None = None

# ─── AprilTag Detector ────────────────────────────────────────
detector = apriltag.Detector(families="tag36h11")

# ─── FastAPI App ──────────────────────────────────────────────
app = FastAPI(title="GDG Robot Cloud Server")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/upload-image")
async def upload_image(request: Request):
    """
    ESP32-CAM 拍照後呼叫此端點 (raw JPEG bytes, Content-Type: image/jpeg)。
    先收集 MAX_CAPTURES 張，全部到齊後一次批次辨識，取最佳結果發布指令。
    """
    try:
        jpeg_bytes = await request.body()
    except ClientDisconnect:
        log.warning("[Upload] Client disconnected during upload, will retry via cam_ip reconnect")
        return JSONResponse({"status": "disconnected"}, status_code=499)
    if not jpeg_bytes:
        raise HTTPException(status_code=400, detail="Empty file")

    with _state_lock:
        car_state["collected"].append(jpeg_bytes)
        capture_count = car_state["capture_count"]
        collected_count = len(car_state["collected"])
        log.info(f"[Upload] #{collected_count}/{MAX_CAPTURES} {len(jpeg_bytes)} bytes — 收集中")

        # 還沒收滿 → 繼續請求下一張
        if capture_count < MAX_CAPTURES and mqtt_client and mqtt_client.is_connected():
            mqtt_client.publish(TOPIC_CAPTURE_REQ, "1")
            car_state["capture_count"] += 1
            return JSONResponse({"status": "collecting", "count": collected_count})

        # 收滿 → 取出所有圖片，重置狀態
        frames = car_state["collected"][:]
        heading = car_state["heading"]
        car_state["collected"] = []
        car_state["capture_count"] = 0

    # 批次辨識（在 lock 外執行，避免阻塞）
    log.info(f"[Batch] 開始辨識 {len(frames)} 張圖片...")
    best_tag_id, best_margin = None, -1.0
    for i, frame_bytes in enumerate(frames):
        tag_id, margin = detect_apriltag(frame_bytes)
        log.info(f"[Batch] 第 {i+1} 張: tag_id={tag_id}, margin={margin:.2f}")
        if tag_id is not None and margin > best_margin:
            best_tag_id, best_margin = tag_id, margin

    if best_tag_id is None:
        log.warning(f"[Batch] {len(frames)} 張全部辨識失敗")
        return JSONResponse({"tag_id": None, "cmd": None, "status": "no_tag"})

    log.info(f"[Batch] 最佳結果 tag_id={best_tag_id}, margin={best_margin:.2f}")
    car_state["current_node"] = best_tag_id

    cmd_payload = None
    if mqtt_client and mqtt_client.is_connected():
        mqtt_client.publish(TOPIC_NODE_ID, json.dumps({"tag_id": best_tag_id}))
        cmd_payload = build_command(best_tag_id, heading)
        mqtt_client.publish(TOPIC_CMD, json.dumps(cmd_payload))
        log.info(f"[MQTT] Published node_id={best_tag_id}, cmd={cmd_payload}")

    return JSONResponse({"tag_id": best_tag_id, "cmd": cmd_payload, "status": "done"})


# ─── Route Planning ───────────────────────────────────────────
def plan_route(current: int, destination: int) -> list[int]:
    try:
        return nx.shortest_path(GRAPH, current, destination)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return []


def get_turn_cmd(cur_node: int, next_node: int, heading: int) -> str:
    edge = GRAPH.get_edge_data(cur_node, next_node)
    if not edge:
        return "forward"
    target = edge.get("heading", heading)
    diff = (target - heading + 360) % 360
    if diff == 0:
        return "forward"
    elif diff == 90:
        return "right"
    elif diff == 270:
        return "left"
    elif diff == 180:
        return "left"  # 掉頭用左轉
    return "right"


def build_command(tag_id: int, heading: int) -> dict:
    path = plan_route(tag_id, DEST_NODE)
    if not path:
        return {"cmd": "stop", "speed": 0}
    if len(path) == 1:
        return {"cmd": "wait_weight", "speed": 0}

    next_node = path[1]
    direction = get_turn_cmd(tag_id, next_node, heading)

    edge = GRAPH.get_edge_data(tag_id, next_node)
    if edge:
        with _state_lock:
            car_state["heading"] = edge.get("heading", heading)

    log.info(f"[Route] {tag_id}→{next_node}: {direction}, heading={heading}→{car_state['heading']}, path={path}")
    return {"cmd": direction, "speed": DEFAULT_SPEED}


# ─── AprilTag Detection ───────────────────────────────────────
def detect_apriltag(jpeg_bytes: bytes) -> tuple[int | None, float]:
    """回傳 (tag_id, decision_margin)，辨識失敗回傳 (None, -1.0)"""
    nparr = np.frombuffer(jpeg_bytes, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
    if frame is None:
        return None, -1.0

    # Debug: 儲存圖片
    debug_path = f"/tmp/debug_{int(time.time())}.jpg"
    cv2.imwrite(debug_path, frame)

    results = detector.detect(frame)
    if not results:
        return None, -1.0

    best = max(results, key=lambda r: r.decision_margin)
    log.info(f"[Debug] Detected tag_id={best.tag_id}, margin={best.decision_margin:.2f}")
    return best.tag_id, best.decision_margin


# ─── MQTT ─────────────────────────────────────────────────────
def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code != 0:
        log.error(f"[MQTT] Connect failed rc={reason_code}")
        return
    log.info(f"[MQTT] Connected to {BROKER}:{PORT}")
    client.subscribe(TOPIC_AT_NODE)
    client.subscribe(TOPIC_WEIGHT)
    client.subscribe(TOPIC_CAM_IP)


def on_message(client, userdata, msg):
    topic = msg.topic
    payload = msg.payload.decode().strip()

    if topic == TOPIC_AT_NODE:
        log.info(f"[MQTT] at_node: {payload}")
        with _state_lock:
            # 重置批次狀態，開始新一輪連拍
            car_state["capture_count"] = 1
            car_state["collected"]     = []
        client.publish(TOPIC_CAPTURE_REQ, "1")
        log.info(f"[MQTT] Sent capture_req 1/{MAX_CAPTURES}")

    elif topic == TOPIC_WEIGHT:
        try:
            data = json.loads(payload)
            log.info(f"[Weight] {data}")
            if data.get("event") == "weight_confirmed":
                cmd = {"cmd": "forward", "speed": DEFAULT_SPEED}
                client.publish(TOPIC_CMD, json.dumps(cmd))
        except json.JSONDecodeError:
            pass

    elif topic == TOPIC_CAM_IP:
        log.info(f"[CAM] IP registered: {payload}")
        # CAM 重連時若批次還在進行中，延遲 1 秒再補發 capture_req
        # (讓 CAM 的 subscription 完全建立後再送)
        with _state_lock:
            count = car_state["capture_count"]
            collected = len(car_state["collected"])
        if 0 < count < MAX_CAPTURES and mqtt_client and mqtt_client.is_connected():
            log.info(f"[CAM] Reconnected mid-batch, resending in 1s (collected={collected}/{MAX_CAPTURES})")
            def delayed_resend():
                if mqtt_client and mqtt_client.is_connected():
                    mqtt_client.publish(TOPIC_CAPTURE_REQ, "1")
                    log.info("[CAM] Resent capture_req after delay")
            threading.Timer(1.0, delayed_resend).start()


def start_mqtt():
    global mqtt_client
    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message

    log.info(f"[MQTT] Connecting to {BROKER}:{PORT}...")
    mqtt_client.connect(BROKER, PORT, keepalive=60)
    mqtt_client.loop_forever()


# ─── Startup ──────────────────────────────────────────────────
@app.on_event("startup")
def startup_event():
    t = threading.Thread(target=start_mqtt, daemon=True)
    t.start()
    log.info("[Server] MQTT thread started")

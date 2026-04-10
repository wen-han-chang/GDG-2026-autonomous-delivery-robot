"""
GDG Delivery Robot - Cloud Server (AWS 部署版)

差異：
  本地版 (apriltag_server.py) 用 HTTP GET 拉 ESP32-CAM 的圖
  雲端版 (cloud_server.py)   由 ESP32-CAM 主動 POST JPEG 過來

流程:
  1. ESP32-CAM 開機 → 發佈 car/cam_ip (retained)
  2. 主控 ESP32 到路口 → 發佈 car/at_node
  3. 後端收到 → 發佈 car/capture_req 給 ESP32-CAM
  4. ESP32-CAM 拍照 → POST /upload-image
  5. Python apriltag 辨識 → 發佈 car/node_id + car/cmd

啟動:
  uvicorn cloud_server:app --host 0.0.0.0 --port 8000
"""

import json
import logging
import threading
import os

import cv2
import numpy as np
import pupil_apriltags as apriltag
import networkx as nx
import paho.mqtt.client as mqtt
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

# ─── Logging ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

# ─── Config (從環境變數讀取，方便容器化) ──────────────────────
BROKER      = os.getenv("MQTT_HOST", "localhost")
PORT        = int(os.getenv("MQTT_PORT", "1883"))
DEST_NODE   = int(os.getenv("DEST_NODE", "5"))
DEFAULT_SPEED = int(os.getenv("DEFAULT_SPEED", "180"))

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
    "heading":      90,
    "current_node": -1,
    "waiting_for_image": False,
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
async def upload_image(file: UploadFile = File(...)):
    """
    ESP32-CAM 拍照後呼叫此端點。
    回傳辨識結果，並透過 MQTT 發布 car/node_id 與 car/cmd。
    """
    jpeg_bytes = await file.read()
    if not jpeg_bytes:
        raise HTTPException(status_code=400, detail="Empty file")

    tag_id = detect_apriltag(jpeg_bytes)
    log.info(f"[Upload] Received {len(jpeg_bytes)} bytes, tag_id={tag_id}")

    if tag_id is None:
        return JSONResponse({"tag_id": None, "cmd": None})

    with _state_lock:
        car_state["current_node"] = tag_id
        car_state["waiting_for_image"] = False
        heading = car_state["heading"]

    if mqtt_client and mqtt_client.is_connected():
        mqtt_client.publish(TOPIC_NODE_ID, json.dumps({"tag_id": tag_id}))
        cmd_payload = build_command(tag_id, heading)
        mqtt_client.publish(TOPIC_CMD, json.dumps(cmd_payload))
        log.info(f"[MQTT] Published node_id={tag_id}, cmd={cmd_payload}")

    return JSONResponse({"tag_id": tag_id, "cmd": cmd_payload})


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

    log.info(f"[Route] {tag_id}→{next_node}: {direction}, path={path}")
    return {"cmd": direction, "speed": DEFAULT_SPEED}


# ─── AprilTag Detection ───────────────────────────────────────
def detect_apriltag(jpeg_bytes: bytes) -> int | None:
    nparr = np.frombuffer(jpeg_bytes, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
    if frame is None:
        return None
    results = detector.detect(frame)
    if not results:
        return None
    best = max(results, key=lambda r: r.decision_margin)
    return best.tag_id


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
            car_state["waiting_for_image"] = True
        # 觸發 ESP32-CAM 拍照
        client.publish(TOPIC_CAPTURE_REQ, "1")
        log.info("[MQTT] Sent capture_req")

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

"""
本地測試 Server

功能：
  1. HTTP POST /upload-image  ← 接收 ESP32-CAM 的 JPEG
  2. AprilTag 辨識
  3. MQTT 發佈 car/node_id 結果
  4. 提供 /trigger 手動觸發拍照（發 car/capture_req）

使用方式：
  python test_local_server.py

測試流程：
  1. 啟動此 server
  2. 開瀏覽器 http://localhost:8000/trigger 觸發拍照
  3. 或用 mosquitto_pub 手動發:
     mosquitto_pub -h 127.0.0.1 -t car/capture_req -m "{}"
"""

import os
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

import cv2
import numpy as np
import pupil_apriltags as apriltag
import paho.mqtt.client as mqtt

# ─── 設定 ────────────────────────────────────────────────────────
MQTT_BROKER   = "127.0.0.1"
MQTT_PORT     = 1883
LISTEN_PORT   = 8000
SAVE_DIR      = "captures"

TOPIC_CAPTURE_REQ = "car/capture_req"
TOPIC_NODE_ID     = "car/node_id"
TOPIC_CAM_IP      = "car/cam_ip"
# ────────────────────────────────────────────────────────────────

os.makedirs(SAVE_DIR, exist_ok=True)
detector = apriltag.Detector(families="tag36h11")

# ─── MQTT Client ─────────────────────────────────────────────────
mqtt_client = mqtt.Client(client_id="test-server")

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[MQTT] Connected to {MQTT_BROKER}:{MQTT_PORT}")
        client.subscribe(TOPIC_CAM_IP)
    else:
        print(f"[MQTT] Connect failed rc={rc}")

def on_message(client, userdata, msg):
    if msg.topic == TOPIC_CAM_IP:
        print(f"[MQTT] ESP32-CAM IP: {msg.payload.decode()}")

mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message


def trigger_capture():
    """發 MQTT 觸發 ESP32-CAM 拍照"""
    mqtt_client.publish(TOPIC_CAPTURE_REQ, "{}")
    print(f"[MQTT] Published: {TOPIC_CAPTURE_REQ}")


def detect_and_publish(jpeg_bytes: bytes) -> int | None:
    """AprilTag 辨識，回傳 tag_id（找不到回 None）"""
    arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        print("[DETECT] Failed to decode image")
        return None

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    results = [r for r in detector.detect(gray) if r.hamming <= 1]

    if not results:
        print("[DETECT] No tag found")
        return None

    # 取信心最高（hamming 最低）的
    best = min(results, key=lambda r: r.hamming)
    print(f"[DETECT] tag_id={best.tag_id}  hamming={best.hamming}  "
          f"center=({best.center[0]:.0f}, {best.center[1]:.0f})")

    payload = f'{{"tag_id": {best.tag_id}}}'
    mqtt_client.publish(TOPIC_NODE_ID, payload)
    print(f"[MQTT] Published {TOPIC_NODE_ID}: {payload}")
    return best.tag_id


# ─── HTTP Server ──────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # 關掉預設 log，改用自己的

    def do_POST(self):
        if self.path == "/upload-image":
            length = int(self.headers.get("Content-Length", 0))
            jpeg_bytes = self.rfile.read(length)

            # 存檔
            filename = os.path.join(SAVE_DIR, f"capture_{int(time.time())}.jpg")
            with open(filename, "wb") as f:
                f.write(jpeg_bytes)
            print(f"[HTTP] Received {len(jpeg_bytes)} bytes → {filename}")

            # 辨識
            tag_id = detect_and_publish(jpeg_bytes)

            # 回應
            body = f'{{"tag_id": {tag_id}}}'.encode() if tag_id is not None \
                   else b'{"tag_id": null}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        if self.path == "/trigger":
            trigger_capture()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Capture request sent!")
        elif self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            html = (
                "<h2>ESP32-CAM Test Server</h2>"
                f"<p>MQTT Broker: {MQTT_BROKER}:{MQTT_PORT}</p>"
                "<p><a href='/trigger'><button>觸發拍照</button></a></p>"
                f"<p>照片存放: {os.path.abspath(SAVE_DIR)}</p>"
            )
            self.wfile.write(html.encode())
        else:
            self.send_response(404)
            self.end_headers()


def main():
    # 啟動 MQTT
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT)
    mqtt_client.loop_start()

    # 啟動 HTTP server
    httpd = HTTPServer(("0.0.0.0", LISTEN_PORT), Handler)
    print(f"[Server] Listening on port {LISTEN_PORT}")
    print(f"[Server] 開瀏覽器: http://localhost:{LISTEN_PORT}/")
    print(f"[Server] 觸發拍照: http://localhost:{LISTEN_PORT}/trigger")
    print(f"[Server] 或用指令: mosquitto_pub -h 127.0.0.1 -t car/capture_req -m \"{{}}\"")
    httpd.serve_forever()


if __name__ == "__main__":
    main()

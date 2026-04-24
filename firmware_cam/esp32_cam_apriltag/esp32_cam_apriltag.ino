/*
 * ESP32-CAM - MQTT 觸發拍照 + HTTP POST 回傳
 *
 * 流程:
 *   後端收到 car/at_node →
 *   發佈 car/capture_req →
 *   ESP32-CAM 拍照 →
 *   HTTP POST JPEG 到後端 /upload-image →
 *   後端 apriltag 辨識 → 發佈 car/cmd
 *
 * Board 設定:
 *   - Board: "AI Thinker ESP32-CAM"
 *   - Partition Scheme: "Huge APP (3MB No OTA)"
 *
 * 燒錄方法:
 *   GPIO0 → GND → 上傳 → 拔掉 GPIO0 → 重新上電
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <WebServer.h>
#include <PubSubClient.h>
#include "esp_camera.h"
#include "config_cam.h"

// ─── AI-Thinker ESP32-CAM 鏡頭腳位 (固定，勿更改) ─────────────
#define CAM_PIN_PWDN  32
#define CAM_PIN_RESET -1
#define CAM_PIN_XCLK   0
#define CAM_PIN_SIOD  26
#define CAM_PIN_SIOC  27
#define CAM_PIN_D7    35
#define CAM_PIN_D6    34
#define CAM_PIN_D5    39
#define CAM_PIN_D4    36
#define CAM_PIN_D3    21
#define CAM_PIN_D2    19
#define CAM_PIN_D1    18
#define CAM_PIN_D0     5
#define CAM_PIN_VSYNC 25
#define CAM_PIN_HREF  23
#define CAM_PIN_PCLK  22
#define CAM_PIN_FLASH  4

#define TOPIC_CAM_IP      "car/cam_ip"       // 開機時發佈自己的 IP
#define TOPIC_CAPTURE_REQ "car/capture_req"  // 訂閱：後端要求拍照

// ─── Globals ──────────────────────────────────────────────────
WebServer    server(80);
WiFiClient   wifiClient;
PubSubClient mqtt(wifiClient);

volatile bool captureRequested = false;  // MQTT callback 設 flag，loop 處理

// ─── Camera Init ──────────────────────────────────────────────
bool initCamera() {
  camera_config_t cfg = {};
  cfg.ledc_channel  = LEDC_CHANNEL_0;
  cfg.ledc_timer    = LEDC_TIMER_0;
  cfg.pin_d0        = CAM_PIN_D0;
  cfg.pin_d1        = CAM_PIN_D1;
  cfg.pin_d2        = CAM_PIN_D2;
  cfg.pin_d3        = CAM_PIN_D3;
  cfg.pin_d4        = CAM_PIN_D4;
  cfg.pin_d5        = CAM_PIN_D5;
  cfg.pin_d6        = CAM_PIN_D6;
  cfg.pin_d7        = CAM_PIN_D7;
  cfg.pin_xclk      = CAM_PIN_XCLK;
  cfg.pin_pclk      = CAM_PIN_PCLK;
  cfg.pin_vsync     = CAM_PIN_VSYNC;
  cfg.pin_href      = CAM_PIN_HREF;
  cfg.pin_sccb_sda  = CAM_PIN_SIOD;
  cfg.pin_sccb_scl  = CAM_PIN_SIOC;
  cfg.pin_pwdn      = CAM_PIN_PWDN;
  cfg.pin_reset     = CAM_PIN_RESET;
  cfg.xclk_freq_hz  = 20000000;
  cfg.pixel_format  = PIXFORMAT_JPEG;
  cfg.frame_size    = FRAMESIZE_VGA;
  cfg.grab_mode     = CAMERA_GRAB_WHEN_EMPTY;
  cfg.fb_location   = CAMERA_FB_IN_DRAM;  // 避免 GPIO4 (flash) 因 PSRAM 共用腳位一直亮
  cfg.jpeg_quality  = 12;
  cfg.fb_count      = 1;

  esp_err_t err = esp_camera_init(&cfg);
  if (err != ESP_OK) {
    Serial.printf("[CAM] Init failed: 0x%x\n", err);
    return false;
  }
  Serial.println("[CAM] Init OK");
  return true;
}

// ─── 拍照並 POST 到後端 ────────────────────────────────────────
void captureAndPost() {
  // 等車體穩定再拍
  delay(300);

  // 補光 LED
  digitalWrite(CAM_PIN_FLASH, HIGH);
  delay(80);

  // 丟棄 stale frame
  camera_fb_t* discard = esp_camera_fb_get();
  if (discard) esp_camera_fb_return(discard);
  delay(100);

  // 最多重試 3 次
  camera_fb_t* fb = nullptr;
  for (int i = 0; i < 3 && !fb; i++) {
    fb = esp_camera_fb_get();
    if (!fb) delay(200);
  }

  digitalWrite(CAM_PIN_FLASH, LOW);

  if (!fb) {
    Serial.println("[CAM] Capture failed after 3 retries");
    return;
  }

  Serial.printf("[CAM] Captured %u bytes, posting to %s\n", fb->len, BACKEND_UPLOAD_URL);

  HTTPClient http;
  http.begin(BACKEND_UPLOAD_URL);
  http.addHeader("Content-Type", "image/jpeg");
  http.setTimeout(10000);

  int code = http.POST(fb->buf, fb->len);
  if (code > 0) {
    Serial.printf("[POST] Response %d: %s\n", code, http.getString().c_str());
  } else {
    Serial.printf("[POST] Failed: %s\n", http.errorToString(code).c_str());
  }

  http.end();
  esp_camera_fb_return(fb);
}

// ─── HTTP Handler: GET /capture (本地 debug 用) ───────────────
void handleCapture() {
  digitalWrite(CAM_PIN_FLASH, HIGH);
  delay(80);

  camera_fb_t* discard = esp_camera_fb_get();
  if (discard) esp_camera_fb_return(discard);
  delay(100);

  camera_fb_t* fb = nullptr;
  for (int i = 0; i < 3 && !fb; i++) {
    fb = esp_camera_fb_get();
    if (!fb) delay(200);
  }

  digitalWrite(CAM_PIN_FLASH, LOW);

  if (!fb) {
    server.send(500, "text/plain", "Camera capture failed");
    return;
  }

  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send_P(200, "image/jpeg", (const char*)fb->buf, fb->len);
  Serial.printf("[HTTP] Served %u bytes JPEG\n", fb->len);
  esp_camera_fb_return(fb);
}

void handleRoot() {
  String ip = WiFi.localIP().toString();
  String html = "<h2>ESP32-CAM Online</h2>"
                "<p>IP: " + ip + "</p>"
                "<p>Backend: " + String(BACKEND_UPLOAD_URL) + "</p>"
                "<p><a href='/capture'>Take Photo (debug)</a></p>"
                "<p><img src='/capture' style='max-width:100%'></p>";
  server.send(200, "text/html", html);
}

// ─── MQTT Callback ────────────────────────────────────────────
void mqttCallback(char* topic, byte* payload, unsigned int length) {
  Serial.printf("[MQTT] Received: %s\n", topic);
  if (strcmp(topic, TOPIC_CAPTURE_REQ) == 0) {
    captureRequested = true;  // 在 loop() 處理，避免在 callback 做耗時操作
  }
}

// ─── MQTT 非阻塞重連 ──────────────────────────────────────────
void mqttReconnect() {
  if (mqtt.connected()) return;

  Serial.print("[MQTT] Connecting...");
  if (mqtt.connect(MQTT_CLIENT_ID)) {
    Serial.println("OK");
    mqtt.subscribe(TOPIC_CAPTURE_REQ);
    Serial.printf("[MQTT] Subscribed: %s\n", TOPIC_CAPTURE_REQ);

    // 發佈自己的 IP（retained）
    String ip = WiFi.localIP().toString();
    mqtt.publish(TOPIC_CAM_IP, ip.c_str(), true);
    Serial.printf("[MQTT] IP published: %s\n", ip.c_str());
  } else {
    Serial.printf("failed rc=%d\n", mqtt.state());
  }
}

// ─── Setup ────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  Serial.println("[Boot] ESP32-CAM Starting...");

  pinMode(CAM_PIN_FLASH, OUTPUT);
  digitalWrite(CAM_PIN_FLASH, LOW);

  if (!initCamera()) {
    Serial.println("[Boot] Camera FAILED, halting");
    while (1) delay(1000);
  }

  WiFi.setSleep(false);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("[WiFi] Connecting");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.printf("\n[WiFi] IP: %s\n", WiFi.localIP().toString().c_str());

  // HTTP Server (debug)
  server.on("/", HTTP_GET, handleRoot);
  server.on("/capture", HTTP_GET, handleCapture);
  server.begin();
  Serial.println("[HTTP] Server started on port 80");

  // MQTT
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(mqttCallback);
  mqtt.setBufferSize(256);
  mqttReconnect();
}

// ─── Loop ─────────────────────────────────────────────────────
void loop() {
  server.handleClient();

  // MQTT 非阻塞重連（每 5 秒嘗試一次）
  if (!mqtt.connected()) {
    static unsigned long lastRetry = 0;
    if (millis() - lastRetry > 5000) {
      lastRetry = millis();
      mqttReconnect();
    }
  }
  mqtt.loop();

  // 處理拍照請求（從 MQTT callback 設的 flag）
  if (captureRequested) {
    captureRequested = false;
    captureAndPost();
  }
}

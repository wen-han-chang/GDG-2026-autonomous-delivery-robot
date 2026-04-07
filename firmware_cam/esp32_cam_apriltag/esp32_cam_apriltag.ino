/*
 * ESP32-CAM - 按需拍照 HTTP Server
 *
 * 流程:
 *   後端 Server 收到 car/at_node →
 *   HTTP GET http://<ESP32_CAM_IP>/capture →
 *   拿到 JPEG → Python apriltag 辨識 → 發佈 car/cmd
 *
 * 不再持續傳圖，只有後端主動來抓才拍，省頻寬省電。
 *
 * 依賴函式庫:
 *   - PubSubClient  (傳自己的 IP 給後端用)
 *   - esp32 board package (含 esp_camera, WebServer)
 *
 * Board 設定:
 *   - Board: "AI Thinker ESP32-CAM"
 *   - Partition Scheme: "Huge APP (3MB No OTA)"
 *
 * 燒錄方法:
 *   GPIO0 → GND → 上傳 → 拔掉 GPIO0 → 重新上電
 */

#include <WiFi.h>
#include "esp_log.h"
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
#define CAM_PIN_FLASH  4  // 補光 LED

#define TOPIC_CAM_IP "car/cam_ip"  // 開機時發佈自己的 IP 給後端

// ─── Globals ──────────────────────────────────────────────────
WebServer    server(80);
WiFiClient   wifiClient;
PubSubClient mqtt(wifiClient);

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
  cfg.frame_size    = FRAMESIZE_UXGA;
  cfg.grab_mode     = CAMERA_GRAB_WHEN_EMPTY;
  cfg.fb_location   = CAMERA_FB_IN_PSRAM;
  cfg.jpeg_quality  = 12;
  cfg.fb_count      = 1;
  if (psramFound()) {
    cfg.jpeg_quality = 10;
    cfg.fb_count     = 2;
    cfg.grab_mode    = CAMERA_GRAB_LATEST;
  } else {
    cfg.frame_size   = FRAMESIZE_SVGA;
    cfg.fb_location  = CAMERA_FB_IN_DRAM;
  }

  esp_err_t err = esp_camera_init(&cfg);
  if (err != ESP_OK) {
    Serial.printf("[CAM] Init failed: 0x%x\n", err);
    return false;
  }

  Serial.printf("[CAM] Free heap: %u bytes, PSRAM: %u bytes\n",
                ESP.getFreeHeap(), ESP.getFreePsram());
  Serial.println("[CAM] Init OK");
  return true;
}

// ─── HTTP Handler: GET /capture ───────────────────────────────
// 後端呼叫這個 endpoint 拿一張 JPEG 圖片
void handleCapture() {
  // 補光 LED 短暫點亮
  digitalWrite(CAM_PIN_FLASH, HIGH);
  delay(80);  // 等曝光穩定

  // 丟棄一張 stale frame
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
    server.send(500, "text/plain", "Camera capture failed");
    Serial.println("[CAM] Capture failed after 3 retries");
    return;
  }

  // 直接回傳 JPEG binary，後端收到後直接用 cv2.imdecode 處理
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send_P(200, "image/jpeg",
                (const char*)fb->buf, fb->len);

  Serial.printf("[CAM] Served %u bytes JPEG\n", fb->len);
  esp_camera_fb_return(fb);
}

// HTTP Handler: GET / (狀態頁，方便 debug)
void handleRoot() {
  String ip = WiFi.localIP().toString();
  String html = "<h2>ESP32-CAM Online</h2>"
                "<p>IP: " + ip + "</p>"
                "<p><a href='/capture'>Take Photo</a></p>"
                "<p><img src='/capture' style='max-width:100%'></p>";
  server.send(200, "text/html", html);
}

// ─── MQTT ─────────────────────────────────────────────────────
void mqttConnect() {
  while (!mqtt.connected()) {
    Serial.print("[MQTT] Connecting...");
    if (mqtt.connect(MQTT_CLIENT_ID)) {
      Serial.println("OK");
      // 開機時把自己的 IP 發佈出去，讓後端知道去哪裡抓圖
      String ip = WiFi.localIP().toString();
      mqtt.publish(TOPIC_CAM_IP, ip.c_str(), true); // retain=true
      Serial.printf("[CAM] IP published: %s\n", ip.c_str());
    } else {
      Serial.printf("failed rc=%d, retry 3s\n", mqtt.state());
      delay(3000);
    }
  }
}

// ─── Setup ────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  Serial.setDebugOutput(true);
  esp_log_level_set("*", ESP_LOG_VERBOSE);
  Serial.println("[Boot] ESP32-CAM Starting...");

  // Flash LED
  pinMode(CAM_PIN_FLASH, OUTPUT);
  digitalWrite(CAM_PIN_FLASH, LOW);

  // Camera
  if (!initCamera()) {
    Serial.println("[Boot] Camera FAILED, halting");
    while (1) delay(1000);
  }

  // WiFi 前先測試 camera
  {
    unsigned long t0 = millis();
    camera_fb_t* fb = esp_camera_fb_get();
    unsigned long elapsed = millis() - t0;
    if (fb) {
      Serial.printf("[PRE-WIFI TEST] Got frame: %u bytes (took %lums)\n", fb->len, elapsed);
      esp_camera_fb_return(fb);
    } else {
      Serial.printf("[PRE-WIFI TEST] No frame (took %lums)\n", elapsed);
    }
  }

  // WiFi
  WiFi.setSleep(false);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("[WiFi] Connecting");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.printf("\n[WiFi] IP: %s\n", WiFi.localIP().toString().c_str());
  Serial.printf("[HTTP] Capture URL: http://%s/capture\n",
                WiFi.localIP().toString().c_str());

  // HTTP Server
  server.on("/", HTTP_GET, handleRoot);
  server.on("/capture", HTTP_GET, handleCapture);
  server.begin();
  Serial.println("[HTTP] Server started on port 80");

  xTaskCreate(cameraTestTask, "cam_test", 4096, NULL, 5, NULL);

  // MQTT (只用來發佈 IP)
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  // mqttConnect();  // 測試時暫時關閉
}

// ─── Camera test task ─────────────────────────────────────────
void cameraTestTask(void* param) {
  vTaskDelay(2000 / portTICK_PERIOD_MS);  // 等 2 秒再開始
  while (true) {
    unsigned long t0 = millis();
    camera_fb_t* fb = esp_camera_fb_get();
    unsigned long elapsed = millis() - t0;
    if (fb) {
      Serial.printf("[TASK] Got frame: %u bytes (took %lums)\n", fb->len, elapsed);
      esp_camera_fb_return(fb);
    } else {
      Serial.printf("[TASK] No frame (took %lums)\n", elapsed);
    }
    vTaskDelay(5000 / portTICK_PERIOD_MS);
  }
}

// ─── Loop ─────────────────────────────────────────────────────
void loop() {
  server.handleClient();
  // if (!mqtt.connected()) mqttConnect();  // 測試時暫時關閉
  // mqtt.loop();
}

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include "config.h"   // 你自己建立：WIFI_SSID/WIFI_PASS/MQTT_HOST/MQTT_PORT/TOPIC_CMD

// ===================== Motor pins (你原本接法) =====================
const int A1A = 25;
const int A1B = 26;
const int B1A = 32;
const int B1B = 33;

// ===================== KSB042 line tracking pins =====================
// 投影片：ROT=GPIO18（右路循跡）、LOT=GPIO17（左路循跡）
const int PIN_LOT = 17; // Left Optical Tracking
const int PIN_ROT = 18; // Right Optical Tracking

// 很多循線模組：黑線=LOW；若你的模組黑線=HIGH 改 true
const bool BLACK_IS_HIGH = false;

// ===================== LEDC (PWM) settings =====================
const int PWM_FREQ = 5000;
const int PWM_RES  = 8;     // 0~255
int SPEED = 160;            // 速度可調 (0~255)

// 每個 pin 一個 channel
const int CH_A1A = 0;
const int CH_A1B = 1;
const int CH_B1A = 2;
const int CH_B1B = 3;

// ===================== MQTT =====================
WiFiClient espClient;
PubSubClient client(espClient);

// ===================== Safety timeout =====================
// 超過這段時間沒收到新指令就自動停（避免後端斷線車一直跑）
unsigned long last_cmd_ms = 0;
const unsigned long CMD_TIMEOUT_MS = 500;

// ===================== Turn-to-first-black-line =====================
const unsigned long TURN_TIMEOUT_MS = 2500; // 轉彎找不到線就停，避免無限轉
const int LINE_CONFIRM_COUNT = 3;           // 防抖：連續命中幾次才算真的到「第一條黑線」

enum Mode {
  MODE_MANUAL = 0,            // forward/back/stop 直接控制
  MODE_TURN_LEFT_TO_LINE,     // 左轉直到「兩顆都黑」(遇到第一條黑線/交叉線)
  MODE_TURN_RIGHT_TO_LINE     // 右轉直到「兩顆都黑」
};

volatile Mode mode = MODE_MANUAL;
unsigned long turn_start_ms = 0;
int line_hit_count = 0;

// ===================== Helpers =====================
void pwmWrite(int channel, int value) {
  value = constrain(value, 0, 255);
  ledcWrite(channel, value);
}

void motorStop() {
  pwmWrite(CH_A1A, 0);
  pwmWrite(CH_A1B, 0);
  pwmWrite(CH_B1A, 0);
  pwmWrite(CH_B1B, 0);
}

void motorForward() {
  pwmWrite(CH_A1A, SPEED);
  pwmWrite(CH_A1B, 0);
  pwmWrite(CH_B1A, SPEED);
  pwmWrite(CH_B1B, 0);
}

void motorBack() {
  pwmWrite(CH_A1A, 0);
  pwmWrite(CH_A1B, SPEED);
  pwmWrite(CH_B1A, 0);
  pwmWrite(CH_B1B, SPEED);
}

void motorLeft() {
  // 左轉：左輪後退、右輪前進（依你馬達方向可能要互換）
  pwmWrite(CH_A1A, 0);
  pwmWrite(CH_A1B, SPEED);
  pwmWrite(CH_B1A, SPEED);
  pwmWrite(CH_B1B, 0);
}

void motorRight() {
  // 右轉：左輪前進、右輪後退（依你馬達方向可能要互換）
  pwmWrite(CH_A1A, SPEED);
  pwmWrite(CH_A1B, 0);
  pwmWrite(CH_B1A, 0);
  pwmWrite(CH_B1B, SPEED);
}

bool isBlackPin(int pin) {
  int v = digitalRead(pin);
  return BLACK_IS_HIGH ? (v == HIGH) : (v == LOW);
}

// 2 路循線：兩顆都黑，通常代表「交叉線/岔路線/停止線」（你要的第一條黑線）
bool bothOnBlackStable() {
  bool L = isBlackPin(PIN_LOT);
  bool R = isBlackPin(PIN_ROT);

  if (L && R) line_hit_count++;
  else line_hit_count = 0;

  return line_hit_count >= LINE_CONFIRM_COUNT;
}

void applyCommand(const String& cmd) {
  Serial.print("[CMD] ");
  Serial.println(cmd);

  if (cmd == "forward") {
    mode = MODE_MANUAL;
    motorForward();
  }
  else if (cmd == "back") {
    mode = MODE_MANUAL;
    motorBack();
  }
  else if (cmd == "left") {
    // 左轉到第一條黑線（兩顆都黑）
    mode = MODE_TURN_LEFT_TO_LINE;
    turn_start_ms = millis();
    line_hit_count = 0;
    motorLeft();
  }
  else if (cmd == "right") {
    // 右轉到第一條黑線（兩顆都黑）
    mode = MODE_TURN_RIGHT_TO_LINE;
    turn_start_ms = millis();
    line_hit_count = 0;
    motorRight();
  }
  else { // stop / unknown
    mode = MODE_MANUAL;
    motorStop();
  }

  last_cmd_ms = millis(); // 更新最後一次收到命令時間
}

void callback(char* topic, byte* payload, unsigned int length) {
  Serial.print("[MQTT] ");
  Serial.print(topic);
  Serial.print(" => ");

  String msg;
  msg.reserve(length + 1);
  for (unsigned int i = 0; i < length; i++) msg += (char)payload[i];
  Serial.println(msg);

  // 嘗試解析 JSON
  StaticJsonDocument<128> doc;
  DeserializationError err = deserializeJson(doc, msg);

  if (err) {
    // 不是 JSON：就當作 raw cmd（例如 "left"）
    Serial.println("[JSON] parse failed, fallback raw string");
    applyCommand(msg);
    return;
  }

  if (doc.containsKey("speed")) {
    SPEED = doc["speed"].as<int>();
    SPEED = constrain(SPEED, 0, 255);
    Serial.print("[SPEED] ");
    Serial.println(SPEED);
  }

  if (doc.containsKey("cmd")) {
    String cmd = doc["cmd"].as<String>();
    applyCommand(cmd);
  }
}

void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);

  Serial.print("[WIFI] connecting");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();

  Serial.print("[WIFI] IP: ");
  Serial.println(WiFi.localIP());
}

void connectMQTT() {
  client.setServer(MQTT_HOST, MQTT_PORT);
  client.setCallback(callback);

  while (!client.connected()) {
    String cid = "esp32-car-" + String((uint32_t)ESP.getEfuseMac(), HEX);
    Serial.print("[MQTT] connecting...");
    if (client.connect(cid.c_str())) {
      Serial.println("OK");
      client.subscribe(TOPIC_CMD);
      Serial.print("[MQTT] subscribed ");
      Serial.println(TOPIC_CMD);
    } else {
      Serial.print("FAIL rc=");
      Serial.println(client.state());
      delay(1000);
    }
  }
}

void setupPWM() {
  ledcSetup(CH_A1A, PWM_FREQ, PWM_RES);
  ledcAttachPin(A1A, CH_A1A);

  ledcSetup(CH_A1B, PWM_FREQ, PWM_RES);
  ledcAttachPin(A1B, CH_A1B);

  ledcSetup(CH_B1A, PWM_FREQ, PWM_RES);
  ledcAttachPin(B1A, CH_B1A);

  ledcSetup(CH_B1B, PWM_FREQ, PWM_RES);
  ledcAttachPin(B1B, CH_B1B);

  motorStop();
}

void setup() {
  Serial.begin(115200);
  delay(500);

  // Line sensors (2路)
  pinMode(PIN_LOT, INPUT);
  pinMode(PIN_ROT, INPUT);

  setupPWM();
  connectWiFi();
  connectMQTT();

  last_cmd_ms = millis();
}

void loop() {
  if (!client.connected()) connectMQTT();
  client.loop();

  // ===== Turn-to-first-black-line logic (2路循線) =====
  if (mode == MODE_TURN_LEFT_TO_LINE || mode == MODE_TURN_RIGHT_TO_LINE) {
    // 1) 超時保護：找不到線就停
    if (millis() - turn_start_ms > TURN_TIMEOUT_MS) {
      Serial.println("[TURN] timeout, stop");
      mode = MODE_MANUAL;
      motorStop();
    } else {
      // 2) 看到第一條黑線（兩顆都黑，且連續命中）
      if (bothOnBlackStable()) {
        Serial.println("[TURN] first line found (both black), stop");
        mode = MODE_MANUAL;
        motorStop();

        // 你也可以改成：找到線後自動前進一點點再停，讓車壓在線上更穩
        // motorForward(); delay(120); motorStop();
      } else {
        // 還沒找到線就繼續轉
        if (mode == MODE_TURN_LEFT_TO_LINE) motorLeft();
        else motorRight();
      }
    }
  }

  // ===== Safety: timeout auto stop =====
  if (millis() - last_cmd_ms > CMD_TIMEOUT_MS) {
    motorStop();
  }
}

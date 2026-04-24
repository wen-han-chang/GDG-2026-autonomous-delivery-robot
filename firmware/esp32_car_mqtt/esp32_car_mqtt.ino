/*
 * ESP32 Autonomous Delivery Robot - Main Controller
 * 馬達驅動: TB6612FNG (取代 L298N)
 * 功能: 循線行駛 / 路口停車 / HX711 重量感測 / MQTT 通訊
 *
 * 依賴函式庫 (Arduino Library Manager):
 *   - PubSubClient  by Nick O'Leary
 *   - ArduinoJson   by Benoit Blanchon
 *   - HX711         by Bogdan Necula
 */

#include <Preferences.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <HX711.h>
#include "config.h"

// ─── State Machine ────────────────────────────────────────────
enum RobotState {
  STATE_IDLE,
  STATE_MOVING,
  STATE_TURN_LEFT,
  STATE_TURN_RIGHT,
  STATE_WAIT_CMD,      // 停在路口等後端路徑指令
  STATE_WAIT_WEIGHT,   // 等重量變化 (取貨 or 送達確認)
};

// ─── Globals ──────────────────────────────────────────────────
WiFiClient   wifiClient;
PubSubClient mqtt(wifiClient);
HX711        scale;

RobotState    state        = STATE_IDLE;
int           currentNode  = -1;
int           currentSpeed = DEFAULT_SPEED;

unsigned long lastCmdTime    = 0;
unsigned long turnStartTime  = 0;
unsigned long weightPollTime = 0;
unsigned long startupTime    = 0;  // 開機完成時間，用來忽略 retained 訊息
unsigned long moveStartTime  = 0;  // 收到 forward 的時間，用來忽略路口緩衝
#define STARTUP_IGNORE_MS 1000     // 開機後 1 秒內的指令全部忽略
#define LEAVE_NODE_MS     1000     // 離開路口緩衝期 (ms)，期間不偵測路口

int lineHitCount = 0;

// Weight tracking
float baselineWeight   = 0.0f;
int   weightEventCount = 0;

// Motor trim
Preferences prefs;
float trimL = MOTOR_TRIM_L;
float trimR = MOTOR_TRIM_R;

void loadTrim() {
  prefs.begin("car_trim", true);
  trimL = prefs.getFloat("trimL", MOTOR_TRIM_L);
  trimR = prefs.getFloat("trimR", MOTOR_TRIM_R);
  prefs.end();
  Serial.printf("[Trim] Loaded: L=%.3f R=%.3f\n", trimL, trimR);
}

void saveTrim() {
  prefs.begin("car_trim", false);
  prefs.putFloat("trimL", trimL);
  prefs.putFloat("trimR", trimR);
  prefs.end();
  Serial.printf("[Trim] Saved: L=%.3f R=%.3f\n", trimL, trimR);
}

static inline int applyTrim(int spd, float trim) {
  return constrain((int)(spd * trim), 0, 255);
}

// ─── L9110S Digital Setup ─────────────────────────────────────
void setupMotorPWM() {
  pinMode(PIN_A_IA, OUTPUT); pinMode(PIN_A_IB, OUTPUT);
  pinMode(PIN_B_IA, OUTPUT); pinMode(PIN_B_IB, OUTPUT);
}

// ─── Motor Primitives (L9110S digital) ───────────────────────
// 前進：IA=H, IB=L
// 後退：IA=L, IB=H
// 停止：IA=L, IB=L

void motorForward(int spd) {
  digitalWrite(PIN_A_IA, HIGH); digitalWrite(PIN_A_IB, LOW);
  digitalWrite(PIN_B_IA, HIGH); digitalWrite(PIN_B_IB, LOW);
}

void motorBack(int spd) {
  digitalWrite(PIN_A_IA, LOW); digitalWrite(PIN_A_IB, HIGH);
  digitalWrite(PIN_B_IA, LOW); digitalWrite(PIN_B_IB, HIGH);
}

// 原地左轉: 左輪後退，右輪前進
void motorLeft(int spd) {
  digitalWrite(PIN_A_IA, LOW);  digitalWrite(PIN_A_IB, HIGH);
  digitalWrite(PIN_B_IA, HIGH); digitalWrite(PIN_B_IB, LOW);
}

// 原地右轉: 左輪前進，右輪後退
void motorRight(int spd) {
  digitalWrite(PIN_A_IA, HIGH); digitalWrite(PIN_A_IB, LOW);
  digitalWrite(PIN_B_IA, LOW);  digitalWrite(PIN_B_IB, HIGH);
}

void motorStop() {
  digitalWrite(PIN_A_IA, LOW); digitalWrite(PIN_A_IB, LOW);
  digitalWrite(PIN_B_IA, LOW); digitalWrite(PIN_B_IB, LOW);
}

// ─── Steering (循線微修正) ────────────────────────────────────
// 偏右 → 左修正: 右輪全速，左輪停
void motorSteerLeft(int spd) {
  digitalWrite(PIN_A_IA, LOW);  digitalWrite(PIN_A_IB, LOW);
  digitalWrite(PIN_B_IA, HIGH); digitalWrite(PIN_B_IB, LOW);
}

// 偏左 → 右修正: 左輪全速，右輪停
void motorSteerRight(int spd) {
  digitalWrite(PIN_A_IA, HIGH); digitalWrite(PIN_A_IB, LOW);
  digitalWrite(PIN_B_IA, LOW);  digitalWrite(PIN_B_IB, LOW);
}

// ─── MQTT Publish Helpers ─────────────────────────────────────
void publishStatus(const char* stateStr) {
  StaticJsonDocument<128> doc;
  doc["state"] = stateStr;
  doc["node"]  = currentNode;
  char buf[128];
  serializeJson(doc, buf);
  mqtt.publish(TOPIC_STATUS, buf);
  Serial.printf("[Status] %s @ node %d\n", stateStr, currentNode);
}

void publishWeightEvent(const char* event, float weightG) {
  StaticJsonDocument<128> doc;
  doc["event"]    = event;
  doc["weight_g"] = weightG;
  doc["node"]     = currentNode;
  char buf[128];
  serializeJson(doc, buf);
  mqtt.publish(TOPIC_WEIGHT_EVENT, buf);
  Serial.printf("[Weight] event=%s weight=%.1fg node=%d\n",
                event, weightG, currentNode);
}

// ─── MQTT Callback ────────────────────────────────────────────
void onMqttMessage(char* topic, byte* payload, unsigned int len) {
  char msg[256] = {};
  memcpy(msg, payload, min((unsigned int)255, len));
  Serial.printf("[MQTT] %s: %s\n", topic, msg);

  // ── car/node_update: Server 辨識 AprilTag 後更新節點 ──
  if (strcmp(topic, TOPIC_NODE_UPDATE) == 0) {
    StaticJsonDocument<64> doc;
    if (!deserializeJson(doc, msg)) {
      currentNode = doc["tag_id"] | currentNode;
      Serial.printf("[Node] Now at node %d\n", currentNode);
    }
    return;
  }

  // ── car/cmd: 路徑指令 ──
  if (strcmp(topic, TOPIC_CMD) != 0) return;

  // 開機後 1 秒內忽略（避免 broker retained 訊息誤觸）
  if (startupTime > 0 && millis() - startupTime < STARTUP_IGNORE_MS) {
    Serial.println("[MQTT] Ignored (startup grace period)");
    return;
  }

  lastCmdTime = millis();

  StaticJsonDocument<128> doc;
  DeserializationError err = deserializeJson(doc, msg);

  const char* cmd = nullptr;
  int spd = currentSpeed;

  if (!err && doc.containsKey("cmd")) {
    cmd = doc["cmd"];
    spd = doc["speed"] | currentSpeed;
  } else {
    cmd = msg;
  }

  currentSpeed = spd;

  if (strcmp(cmd, "forward") == 0) {
    motorForward(spd);
    lineHitCount = 0;
    moveStartTime = millis();  // 記錄開始移動時間
    state = STATE_MOVING;
    publishStatus("moving");

  } else if (strcmp(cmd, "left") == 0) {
    // 先前進一小段離開路口中心，再用 TURN_SPEED 原地左轉
    motorForward(currentSpeed);
    delay(300);
    motorLeft(TURN_SPEED);
    turnStartTime = millis();
    moveStartTime = millis();
    lineHitCount  = 0;
    state = STATE_TURN_LEFT;
    publishStatus("turning_left");

  } else if (strcmp(cmd, "right") == 0) {
    motorForward(currentSpeed);
    delay(300);
    motorRight(TURN_SPEED);
    turnStartTime = millis();
    moveStartTime = millis();
    lineHitCount  = 0;
    state = STATE_TURN_RIGHT;
    publishStatus("turning_right");

  } else if (strcmp(cmd, "wait_weight") == 0) {
    motorStop();
    baselineWeight   = scale.get_units(5);
    weightEventCount = 0;
    state = STATE_WAIT_WEIGHT;
    publishStatus("waiting_weight");
    Serial.printf("[Weight] Baseline: %.1fg\n", baselineWeight);

  } else if (strcmp(cmd, "trim") == 0) {
    if (!err) {
      trimL = constrain((float)(doc["left"]  | trimL), 0.5f, 1.0f);
      trimR = constrain((float)(doc["right"] | trimR), 0.5f, 1.0f);
      saveTrim();
      char buf[64];
      snprintf(buf, sizeof(buf), "{\"trimL\":%.3f,\"trimR\":%.3f}", trimL, trimR);
      mqtt.publish(TOPIC_STATUS, buf);
    }

  } else if (strcmp(cmd, "stop") == 0) {
    motorStop();
    state = STATE_IDLE;
    publishStatus("idle");

  } else if (strcmp(cmd, "backward") == 0) {
    motorBack(spd);
    state = STATE_MOVING;
    publishStatus("moving");
  }
}

// ─── MQTT Connect ─────────────────────────────────────────────
void mqttConnect() {
  while (!mqtt.connected()) {
    Serial.print("[MQTT] Connecting...");
    if (mqtt.connect(MQTT_CLIENT_ID)) {
      Serial.println("OK");
      mqtt.publish(TOPIC_CMD, "", true);  // 清除 broker 上的 retained 指令
      mqtt.subscribe(TOPIC_CMD);
      mqtt.subscribe(TOPIC_NODE_UPDATE);  // car/node_id
      motorStop();
      state = STATE_IDLE;
      publishStatus("idle");
    } else {
      Serial.printf("failed rc=%d, retry 3s\n", mqtt.state());
      delay(3000);
    }
  }
}

// ─── Setup ────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  Serial.println("[Boot] ESP32 Car Starting...");

  // Motor trim
  loadTrim();

  // Motor (L9110S)
  setupMotorPWM();
  motorStop();

  // Line sensors
  pinMode(PIN_LINE_L, INPUT);
  pinMode(PIN_LINE_R, INPUT);

  // HX711 (若未接上則跳過，不卡住)
  scale.begin(PIN_HX_DT, PIN_HX_SCK);
  scale.set_scale(HX711_SCALE_FACTOR);
  if (scale.wait_ready_timeout(2000)) {
    scale.tare();
    Serial.println("[HX711] Ready, tare done");
  } else {
    Serial.println("[HX711] Not found, skipping");
  }

  // WiFi
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("[WiFi] Connecting");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.printf("\n[WiFi] IP: %s\n", WiFi.localIP().toString().c_str());

  // MQTT
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(onMqttMessage);
  mqttConnect();

  startupTime = millis();
  Serial.println("[Boot] Ready");
}

// ─── Loop ─────────────────────────────────────────────────────
void loop() {
  if (!mqtt.connected()) mqttConnect();
  mqtt.loop();

  unsigned long now = millis();

  switch (state) {

    case STATE_MOVING: {
      bool lOn = (digitalRead(PIN_LINE_L) == LINE_ACTIVE);
      bool rOn = (digitalRead(PIN_LINE_R) == LINE_ACTIVE);

      // 離開路口緩衝期，不偵測路口
      if (now - moveStartTime < LEAVE_NODE_MS) {
        motorForward(currentSpeed);
        break;
      }

      if (lOn && rOn) {
        // 兩個都偵測到黑線 = 路口
        if (++lineHitCount == 1) {
          // 第一次偵測到就立刻減速，給後續確認次數足夠時間
          motorForward(INTERSECTION_SPEED);
        } else if (lineHitCount >= LINE_DEBOUNCE) {
          motorStop();
          delay(50);
          state = STATE_WAIT_CMD;
          // 通知後端觸發拍照辨識
          StaticJsonDocument<64> atDoc;
          atDoc["state"] = "at_node";
          char atBuf[64];
          serializeJson(atDoc, atBuf);
          mqtt.publish(TOPIC_AT_NODE, atBuf);
          publishStatus("at_node");
          Serial.printf("[Nav] Intersection! node=%d\n", currentNode);
        }
      } else if (!lOn && rOn) {
        // 右感測器在線，左出線 → 車偏左 → 右修正
        lineHitCount = 0;
        motorSteerRight(currentSpeed);
      } else if (lOn && !rOn) {
        // 左感測器在線，右出線 → 車偏右 → 左修正
        lineHitCount = 0;
        motorSteerLeft(currentSpeed);
      } else {
        // 兩個都離線（暫時跨越白色間隙），直走
        lineHitCount = 0;
        motorForward(currentSpeed);
      }
      break;
    }

    case STATE_TURN_LEFT: {
      if (now - turnStartTime >= TURN_LEFT_MS) {
        motorForward(currentSpeed);
        lineHitCount = 0;
        moveStartTime = millis();
        state = STATE_MOVING;
        publishStatus("moving");
        Serial.println("[Nav] Left turn done");
      }
      break;
    }

    case STATE_TURN_RIGHT: {
      if (now - turnStartTime >= TURN_RIGHT_MS) {
        motorForward(currentSpeed);
        lineHitCount = 0;
        moveStartTime = millis();
        state = STATE_MOVING;
        publishStatus("moving");
        Serial.println("[Nav] Right turn done");
      }
      break;
    }

    case STATE_WAIT_WEIGHT:
      if (now - weightPollTime > WEIGHT_POLL_MS) {
        weightPollTime = now;

        if (!scale.is_ready()) break;
        float w    = scale.get_units(3);
        float diff = w - baselineWeight;

        Serial.printf("[Weight] current=%.1fg baseline=%.1fg diff=%.1fg\n",
                      w, baselineWeight, diff);

        if (fabs(diff) > WEIGHT_THRESHOLD_G) {
          weightEventCount++;
          if (weightEventCount >= WEIGHT_STABLE_COUNT) {
            const char* evt = (diff > 0) ? "loaded" : "unloaded";
            publishWeightEvent(evt, w);
            state = STATE_WAIT_CMD;
            publishStatus("weight_confirmed");
            weightEventCount = 0;
          }
        } else {
          weightEventCount = 0;
        }
      }
      break;

    case STATE_WAIT_CMD:
    case STATE_IDLE:
    default:
      break;
  }
}

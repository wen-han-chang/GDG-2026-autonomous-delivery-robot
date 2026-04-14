#pragma once

// ===== WiFi =====
const char* WIFI_SSID = "vivo V70";
const char* WIFI_PASS = "willy621";

// ===== MQTT =====
const char* MQTT_HOST      = "3.27.165.128";  // AWS EC2 公網 IP
const int   MQTT_PORT      = 1883;
const char* MQTT_CLIENT_ID = "esp32-car";

// ===== Topics =====
const char* TOPIC_CMD          = "car/cmd";
const char* TOPIC_STATUS       = "car/status";
const char* TOPIC_WEIGHT_EVENT = "car/weight_event";
const char* TOPIC_NODE_UPDATE  = "car/node_id";    // 與後端一致
const char* TOPIC_AT_NODE      = "car/at_node";    // 路口通知

// ===== L9110S Motor Driver Pins =====
// Motor A = 左馬達 (Left)
#define PIN_A_IA 13   // 左馬達 A-IA (前進)
#define PIN_A_IB 27   // 左馬達 A-IB (後退)
// Motor B = 右馬達 (Right) ← 改用 GPIO25/26 (純 digitalWrite，DAC 無影響)
#define PIN_B_IA 26   // 右馬達 B-IA (前進)
#define PIN_B_IB 25   // 右馬達 B-IB (後退)

// ===== Line Sensors =====
#define PIN_LINE_L 17
#define PIN_LINE_R 18

// ===== HX711 =====
#define PIN_HX_DT  4
#define PIN_HX_SCK 5

// ===== Line Following =====
// KSB042: 偵測到黑線時 OUT = HIGH。若你的感測器相反，改成 LOW
#define LINE_ACTIVE  HIGH
// 修正偏移時，內側輪速度倍率 (0.0=完全停住, 1.0=不修正, 建議 0.35~0.5)
#define STEER_FACTOR 0.40f

// ===== Motor Trim (左右馬達速度校正) =====
// 診斷方法: 把車放地上跑直線，往左偏 → 右馬達快 → 降低 MOTOR_TRIM_R
//                               往右偏 → 左馬達快 → 降低 MOTOR_TRIM_L
// 調整方式: 透過 MQTT 發送 {"cmd":"trim","left":0.95,"right":1.0}
#define MOTOR_TRIM_L 1.0f
#define MOTOR_TRIM_R 1.0f

// ===== Weight Config =====
#define HX711_SCALE_FACTOR  420.0f   // 用已知重物校正後填入
#define WEIGHT_THRESHOLD_G  100.0f   // 重量變化閾值 (克)
#define WEIGHT_STABLE_COUNT 5        // 連續幾次確認才觸發事件

// ===== Timing =====
#define DEFAULT_SPEED        100     // PWM duty 0~255
#define INTERSECTION_SPEED    70     // 偵測到路口後立刻降速
#define TURN_SPEED            70     // 轉彎專用速度（比前進慢，避免衝過新線）
#define CMD_TIMEOUT_MS       500     // 無指令自動停車
#define TURN_TIMEOUT_MS     3000     // 最長轉向時間
#define WEIGHT_POLL_MS       200     // 重量取樣間隔
#define LINE_DEBOUNCE          5     // 路口偵測連續確認次數
#define TURN_LEFT_MS         415     // 左轉 90° 所需毫秒
#define TURN_RIGHT_MS        415     // 右轉 90° 所需毫秒

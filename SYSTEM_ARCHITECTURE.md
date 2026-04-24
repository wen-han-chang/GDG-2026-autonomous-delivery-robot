# GDG 2026 自主送餐機器人 — 完整系統架構

## 系統架構總覽

```mermaid
graph TB
    subgraph USER["👤 使用者端"]
        FE["Frontend<br/>React + Vite<br/>・下單介面<br/>・即時配送地圖<br/>・基本設定"]
    end

    subgraph CLOUD_MAIN["☁️ AWS EC2 Docker — 主後端"]
        BE["FastAPI Backend<br/>app/main.py"]
        DB[("PostgreSQL<br/>訂單 / 商店 / 商品 / 使用者")]
        ALGO["路徑規劃<br/>Dijkstra / A*<br/>app/graph.py"]
        WS["WebSocket<br/>app/ws.py"]
    end

    subgraph EC2["☁️ AWS EC2 — 機器人服務"]
        MQ["Mosquitto<br/>MQTT Broker<br/>:1883"]
        API["FastAPI + AprilTag<br/>server/cloud_server.py<br/>:8000"]
        NAV["導航演算法<br/>NetworkX 最短路徑"]
    end

    subgraph ROBOT["🤖 機器人硬體"]
        CAM["ESP32-CAM<br/>AI Thinker"]
        MCU["主控 ESP32<br/>馬達控制"]
        MOTOR["L9110S<br/>左右馬達"]
        LINE["循跡感測器<br/>左 / 右"]
        WEIGHT["HX711<br/>重量感測器"]
    end

    %% 使用者 ↔ 前端 ↔ 後端
    FE -->|"HTTP REST"| BE
    WS -.->|"WebSocket 推送 (規劃中)"| FE
    BE -->|"讀寫"| DB
    BE --> ALGO

    %% 後端 → EC2 (目前 Mock，未來接通)
    BE -.->|"MQTT bridge (規劃中)"| MQ
    MQ -.->|"小車位置 (規劃中)"| WS

    %% EC2 內部
    API -->|"subscribe/publish"| MQ
    API --> NAV

    %% ESP32-CAM ↔ EC2
    CAM -->|"MQTT :1883<br/>car/cam_ip"| MQ
    CAM -->|"HTTP POST JPEG<br/>:8000/upload-image"| API
    MQ -->|"car/capture_req"| CAM

    %% 主控 ESP32 ↔ EC2
    MCU -->|"MQTT<br/>car/at_node"| MQ
    MCU -->|"MQTT<br/>car/weight_event"| MQ
    MQ -->|"car/cmd<br/>left/right/forward/wait_weight"| MCU
    MQ -->|"car/node_id"| MCU

    %% 主控 ESP32 ↔ 硬體
    MCU --> MOTOR
    LINE -->|"循跡訊號"| MCU
    WEIGHT -->|"重量訊號"| MCU
```

---

## 完整運作流程

### Phase 1：使用者下單

```mermaid
sequenceDiagram
    actor User
    participant FE as Frontend
    participant BE as 主後端 (App Runner)
    participant DB as PostgreSQL RDS

    User->>FE: 選擇商店 / 商品 / 下單
    FE->>BE: POST /orders
    BE->>BE: Dijkstra / A* 計算最短路徑
    BE->>DB: 儲存訂單 (order_id, route, eta)
    BE-->>FE: 回傳 order_id + 預估時間
    FE-->>User: 顯示訂單確認 + 地圖
```

---

### Phase 2：機器人循跡前進（路口之間）

```mermaid
sequenceDiagram
    participant MCU as 主控 ESP32
    participant LINE as 循跡感測器
    participant MOTOR as 馬達

    Note over MCU: 收到 car/cmd forward 後開始前進
    loop 循跡行進中
        LINE-->>MCU: 左/右感測器訊號
        MCU->>MCU: 判斷偏移，修正方向
        MCU->>MOTOR: 輸出 PWM 調整速度
    end
    Note over MCU: 偵測到路口（兩個感測器同時觸發）
    MCU->>MCU: 降速，發布 car/at_node
```

---

### Phase 3：路口辨識 → 取得下一步指令

```mermaid
sequenceDiagram
    participant MCU as 主控 ESP32
    participant MQ as Mosquitto (EC2)
    participant API as FastAPI+AprilTag (EC2)
    participant CAM as ESP32-CAM

    MCU->>MQ: car/at_node {"state":"at_node"}
    MQ->>API: 轉發訊息
    API->>MQ: car/capture_req "1"
    MQ->>CAM: 觸發拍照

    CAM->>CAM: 拍照 (JPEG)
    CAM->>API: HTTP POST /upload-image (JPEG bytes)
    API->>API: AprilTag 辨識 → tag_id = N
    API->>API: NetworkX 最短路徑規劃

    alt 尚未到達目的地
        API->>MQ: car/node_id {"tag_id": N}
        API->>MQ: car/cmd {"cmd":"left/right/forward","speed":180}
        MQ->>MCU: 執行轉向指令 → 回到 Phase 2
    else 抵達目的地節點
        API->>MQ: car/cmd {"cmd":"wait_weight","speed":0}
        MQ->>MCU: 停車等待
    end
```

---

### Phase 4：停靠點取餐 → 繼續路線

```mermaid
sequenceDiagram
    participant MCU as 主控 ESP32
    participant WEIGHT as HX711 重量感測器
    participant MQ as Mosquitto (EC2)
    participant API as FastAPI+AprilTag (EC2)

    Note over MCU: 停車中，持續取樣重量
    loop 重量偵測
        WEIGHT-->>MCU: 重量數值
        MCU->>MCU: 判斷重量變化 > 閾值 (100g)
    end
    MCU->>MQ: car/weight_event {"event":"weight_confirmed","weight_g":X}
    MQ->>API: 轉發重量事件
    Note over API: 繼續執行路線（下一停靠點或回程）
    API->>MQ: car/cmd {"cmd":"forward","speed":180}
    MQ->>MCU: 繼續前進 → 回到 Phase 2
```

---

## MQTT Topic 對照表

| Topic | 發布者 | 訂閱者 | 說明 |
|---|---|---|---|
| `car/cam_ip` | ESP32-CAM | FastAPI | 相機開機 IP (retained) |
| `car/at_node` | 主控 ESP32 | FastAPI | 偵測到路口通知 |
| `car/capture_req` | FastAPI | ESP32-CAM | 觸發拍照 |
| `car/node_id` | FastAPI | 主控 ESP32 | AprilTag 辨識結果 |
| `car/cmd` | FastAPI | 主控 ESP32 | 行進指令 (left/right/forward/wait_weight) |
| `car/weight_event` | 主控 ESP32 | FastAPI | 重量變化確認 |

---

## 各服務部署位置

> 所有後端服務皆以 Docker 容器方式部署於同一台 AWS EC2 (`t3.small`, 2 vCPU / 2GB RAM, ap-southeast-2, IP: `3.27.165.128`)，以 `docker-compose` 統一管理。

| 服務 | 技術 | 部署位置 | Port |
|---|---|---|---|
| Frontend | React + Vite (Nginx) | Docker — AWS EC2 (3.27.165.128) | 80 |
| 主後端 | FastAPI + SQLAlchemy | Docker — AWS EC2 (3.27.165.128) | 8001 |
| 資料庫 | PostgreSQL | Docker — AWS EC2 (3.27.165.128) | 5432 |
| MQTT Broker | Eclipse Mosquitto | Docker — AWS EC2 (3.27.165.128) | 1883 |
| 機器人服務 | FastAPI + AprilTag | Docker — AWS EC2 (3.27.165.128) | 8000 |
| ESP32-CAM | Arduino C++ | 機器人本體 | WiFi |
| 主控 ESP32 | Arduino C++ | 機器人本體 | WiFi |

### 預估資源使用 (t3.small)

| 服務 | 估計 RAM |
|---|---|
| Nginx (Frontend) | ~50 MB |
| FastAPI 主後端 | ~200 MB |
| PostgreSQL | ~200 MB |
| Mosquitto | ~20 MB |
| 機器人服務 (AprilTag + OpenCV) | ~400 MB |
| OS + Docker overhead | ~300 MB |
| **合計** | **~1.2 GB / 2 GB** |

---

## ⚠️ 已知 Bug 需修正

| 問題 | 說明 |
|---|---|
| Topic 不一致 | `cloud_server.py` 發布 `car/node_id`，主控韌體訂閱 `car/node_update`，需統一 |

---

## 目前狀態

| 模組 | 狀態 |
|---|---|
| ESP32-CAM ↔ EC2 MQTT | ✅ 完成 |
| ESP32-CAM 拍照上傳 | ✅ 完成 |
| EC2 AprilTag 辨識 | ✅ 完成（需調整實體環境）|
| EC2 路徑規劃 | ✅ 完成 |
| 主後端 API + RDS | ✅ 完成 |
| 主後端 ↔ EC2 MQTT 整合 | ⚠️ 規劃中（目前 Mock）|
| WebSocket 推送小車位置 | ⚠️ 規劃中 |
| 主控 ESP32 燒錄雲端 config | ⏳ 待完成 |
| 實體測試 | ⏳ 待完成 |

# ESP32 Autonomous Delivery Robot (DEV Branch)

> ⚠️ This is the **development / integration branch** (`dev`).
> - `dev` may contain unfinished features or unstable changes.
> - For stable demo/release version, switch to `main`.

---

## Branch Policy

### Main Branches
- ✅ `main`: Stable / demo-ready / release branch (NO direct push)
- ✅ `dev`: Integration branch for team development

### Workflow
1. Developers create a feature branch **from `dev`**
2. Push commits to feature branch
3. Open Pull Request (PR) → merge into `dev`
4. Only when `dev` is stable → PR from `dev` to `main`

### Branch Naming Convention
Use short, module-based prefixes:

#### Frontend
- `fe/<feature>`
  - Example: `fe/map-ui`

#### Backend
- `be/<feature>`
  - Example: `be/order-api`

#### Firmware (ESP32)
- `fw/<feature>`
  - Example: `fw/mqtt-control`

#### Bug Fix
- `fix/<bug>`
  - Example: `fix/backend-timeout`

---

## Project Structure

```
.
├── app/                # Backend (Python)
├── frontend/           # Frontend (Vite / Web UI)
├── data/               # Map / test data
├── robot_simulator.py  # Simulation entry (if used)
└── README.md
```

---

## 新環境完整重建（重新下載專案）

這份流程給「第一次下載專案」的人，照做可以直接完成：
- 全部 Docker 服務重建
- 後端/前端可用
- 小車狀態可重置到可實作狀態
- 可重現 MQTT 訂閱失敗情境

### 0. 前置需求

- Docker Desktop（含 Docker Compose）
- Git
- Windows 使用者建議 PowerShell 7+（Windows PowerShell 5.1 也可）

### 1. 下載並進入專案

```bash
git clone <your-repo-url>
cd GDG-2026-autonomous-delivery-robot
```

### 2. 建立 `.env`

```bash
# Linux/macOS
cp .env.example .env

# Windows PowerShell
Copy-Item .env.example .env
```

至少確認以下欄位：

```dotenv
JWT_SECRET_KEY=change_me_to_a_random_secret
FRONTEND_VITE_API_URL=http://localhost:8001
ALLOWED_ORIGINS=http://localhost,http://127.0.0.1,http://localhost:80
```

### 3. 全量重建全部 Docker（乾淨重建）

```bash
docker compose down -v --remove-orphans
docker compose build --no-cache
docker compose up -d
docker compose ps
```

預期會啟動 4 個服務：`db`、`mosquitto`、`backend`、`frontend`。

### 4. 基本健康檢查

```bash
# 查看後端最近日誌
docker compose logs --tail 80 backend

# API 文件
curl http://localhost:8001/docs

# 規劃狀態（若尚未 init 可能回 not found，屬正常）
curl "http://localhost:8001/planner/status?robot_id=R001"
```

瀏覽器開啟：
- 前端 UI：http://localhost
- 後端 Swagger：http://localhost:8001/docs

### 5. 重置小車到可實作狀態

```powershell
.\tools\reset-robot-state.ps1 -RobotId R001 -StartNode A
```

這個腳本會：
- 清空 `orders`（可用 `-SkipOrderClear` 保留）
- 將 `robot_states` 重置到指定節點
- 重啟 backend 並印出 `planner/status`

### 6. MQTT 訂閱失敗模擬（實機 MQTT 模式）

若要模擬「小車訂閱失敗／broker 中斷」，請先把 backend 切到真實 MQTT：

在 `.env` 新增（或修改）

```dotenv
MQTT_USE_MOCK=false
MQTT_BROKER_URL=mosquitto
MQTT_BROKER_PORT=1883
```

套用設定：

```bash
docker compose up -d --build backend mosquitto
docker compose logs --tail 50 backend
```

你應看到類似：`MQTT bridge started (mock=False, host=mosquitto:1883)`。

開始模擬故障：

```bash
docker compose stop mosquitto
docker compose logs -f backend
```

此時建立新訂單/重規劃請求即可觀察 broker 不可用情境。

恢復：

```bash
docker compose start mosquitto
docker compose restart backend
docker compose logs --tail 80 backend
```

---

## Quick Start (Docker Compose)

本專案建議使用 Docker Compose 進行開發環境的快速啟動與管理。

1.  **確保 Docker 正在運行**
    *   請確認您的機器上已安裝 Docker Desktop 並正在運行。

2.  **啟動所有服務**
    *   在專案的根目錄 (與 `docker-compose.yml` 同級的目錄) 執行：
        ```bash
        docker compose up -d
        ```
    *   這會啟動資料庫 (`robot-db`)、MQTT Broker (`robot-mqtt`)、後端 (`robot-backend`) 和前端 (`robot-frontend`) 服務。

3.  **確認服務狀態**
    *   您可以執行以下指令查看所有服務是否正常運行：
        ```bash
        docker compose ps
        ```
    *   確認所有服務的 `STATUS` 都是 `Up`。

4.  **訪問應用程式**
    *   **前端 (Web UI)**: 打開您的瀏覽器，訪問 [http://localhost](http://localhost)。
    *   **後端 API 文件**: 訪問 [http://localhost:8001/docs](http://localhost:8001/docs) (Swagger UI)。

### EC2 部署注意事項（重要）

若要讓所有人可透過 EC2 公網存取，請先設定 `.env`：

```bash
FRONTEND_VITE_API_URL=http://<你的EC2公網IP或網域>:8001
ALLOWED_ORIGINS=http://<你的EC2公網IP或網域>
```

`FRONTEND_VITE_API_URL` 是前端 build-time 變數，修改後必須重建前端映像：

```bash
docker compose build frontend
docker compose up -d frontend backend
```

若未重建前端，使用者可能看到「可瀏覽店家但下單失敗」，因為前端仍呼叫舊的 API 位址。

---

## 本地開發啟動（不使用完整 Docker）

只啟動基礎設施（DB + MQTT），後端直接用 uvicorn 在本機跑，方便快速 hot-reload 開發：

```bash
# 1. 啟動 PostgreSQL 和 MQTT Broker
docker compose up -d db mosquitto

# 2. 安裝依賴（僅首次或更新後需要）
pip install -r requirements.txt

# 3. 啟動後端（連接本機 Docker 的 MQTT）
MQTT_USE_MOCK=false MQTT_BROKER_URL=localhost MQTT_BROKER_PORT=1883 \
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

啟動成功後 terminal 應出現：
```
✅ Database tables verified.
✅ Map loaded: campus_demo
✅ MQTT bridge started (mock=False, host=localhost:1883)
```

### MQTT 環境變數

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `MQTT_BROKER_URL` | `localhost` | MQTT Broker 位址 |
| `MQTT_BROKER_PORT` | `1883` | MQTT Broker 埠號 |
| `MQTT_USE_MOCK` | `true` | `true` = 使用記憶體 Mock（不需 Broker）；`false` = 連接真實 Mosquitto |

> 開發/單元測試時保持 `MQTT_USE_MOCK=true`；實機測試時改為 `false`。

---

## 地圖設定（campus_demo）

地圖定義於 `data/map.json`，目前使用 `campus_demo`，拓樸為 3×3 格狀，所有邊長均為 **75 cm**：

```
C --- B --- A(HOME)
|    |    |
F --- E --- D
|    |    |
I --- H --- G
```

節點座標（單位：cm）：

| 節點 | x   | y   | 說明 |
|------|-----|-----|------|
| A    | 0   | 60  | HOME（機器人待機／送達點） |
| B    | 75  | 60  | |
| C    | 150 | 60  | |
| D    | 0   | 135 | |
| E    | 75  | 135 | |
| F    | 150 | 135 | |
| G    | 0   | 210 | |
| H    | 75  | 210 | |
| I    | 150 | 210 | |

**HOME_NODE = `"A"`**（定義於 `app/main.py`）：未指定 `to_node` 時，系統自動以 A 作為送達點。

---

## 店家節點對應

每家店的 `location_node` 定義於 `app/routers/stores.py`（`STORE_STORE`）：

| 店家 ID | 店名 | location_node |
|---------|------|---------------|
| S001 | 讚野烤肉飯 | B |
| S002 | 台灣第二味 | C |
| S003 | 8-11便利商店 | D |
| S004 | 麥脆雞 | E |
| S005 | 健康沙拉吧 | F |
| S006 | 咖啡研究室 | G |
| S007 | 日式拉麵屋 | H |
| S008 | 水果天堂 | I |
| S009 | 披薩工坊 | E |

首次啟動後端時，若資料庫無店家資料，會自動 seed 上述資料。

---

## 訂單 API

### POST `/orders`

支援兩種格式：

**新格式（推薦）** — 提供 `store_id`，系統自動推導取貨節點與 HOME 送達點：
```json
{ "map_id": "campus_demo", "store_id": "S001" }
```
- `from_node` 自動設為該店的 `location_node`（例如 S001 → `"B"`）
- `to_node` 自動設為 `HOME_NODE`（`"A"`）

**舊格式（向後相容）** — 直接指定節點：
```json
{ "map_id": "campus_demo", "from_node": "E", "to_node": "A" }
```

若兩者都未提供，回傳 `400: "Provide either from_node or store_id"`。

### POST `/orders/multi`

一次下多店訂單（每個店家會建立一筆實際訂單並加入同一波派送佇列）：

```json
{
    "map_id": "campus_demo",
    "store_ids": ["S001", "S002", "S006"],
    "to_node": "A",
    "items_by_store": {
        "S001": ["招牌便當 x1"],
        "S002": ["紅茶 x2"],
        "S006": ["拿鐵 x1"]
    },
    "total": 255
}
```

回傳會包含：
- `order_ids`: 這次多店下單產生的所有訂單 ID
- `orders`: 每筆訂單的路線與 ETA
- `total_distance_cm`: 所有子訂單距離總和
- `max_eta_sec`: 子訂單中最長 ETA

### 固定節點規則（目前版本）

目前規劃流程僅使用地圖內既有節點（`data/map.json`），
`from_node` / `to_node` 必須是已存在的節點 ID；不使用虛擬節點吸附（virtual node snapping）。

### 下單流程

1. 計算最短路徑（Dijkstra / A*）
2. 指派給待送訂單最少的機器人
3. 透過 MQTT 發布規劃結果至 `robot/{robot_id}/plan`
4. 透過 WebSocket 廣播 `order_assigned` 事件給前端

---

## 後端依賴管理 (使用 pip-tools)

為了確保開發環境的一致性和依賴版本的穩定，我們使用 `pip-tools` 來管理後端 (Python) 的依賴套件。

1.  **直接依賴定義**:
    所有直接依賴都定義在 `backend/requirements.in` 檔案中。**請勿直接修改 `requirements.txt`。**

2.  **新增/更新/刪除套件**:
    *   若要新增、更新或刪除任何 Python 套件，請編輯 `backend/requirements.in`。
    *   您可以指定版本 (`package==X.Y.Z`)，或只指定套件名稱讓 `pip-tools` 尋找最新版本。

3.  **重新產生 `requirements.txt`**:
    修改 `requirements.in` 後，請執行以下指令來更新 `requirements.txt`：
    ```bash
    docker compose run --rm backend sh -c "pip install pip-tools && pip-compile requirements.in -o requirements.txt"
    ```
    這個指令會在一個暫時的 Docker 容器中執行，並根據 `requirements.in` 產生最新的 `requirements.txt`。

4.  **重新建置後端映像檔**:
    更新 `requirements.txt` 後，您需要重新建置後端服務的 Docker 映像檔，以安裝新的依賴：
    ```bash
    docker compose build backend
    ```

5.  **重啟服務**:
    最後，重啟 Docker Compose 服務以應用變更：
    ```bash
    docker compose up -d
    ```

---

## 資料庫遷移 (使用 Alembic)

我們使用 Alembic 來進行資料庫結構的版控和遷移。這在開發和部署到生產環境 (例如 AWS RDS) 時都至關重要。

1.  **初始設定**:
    Alembic 環境已在專案根目錄下的 `alembic/` 資料夾中初始化。相關設定在 `alembic.ini` 和 `alembic/env.py` 中。

2.  **變更資料庫模型**:
    *   當您需要新增表、新增欄位或修改現有模型時，請在 `app/sql_models.py` 中修改您的 SQLAlchemy 模型定義。

3.  **產生新的遷移腳本**:
    修改模型後，執行以下指令來產生一個新的遷移腳本：
    ```bash
    docker compose run --rm backend alembic revision --autogenerate -m "請用英文簡潔描述您的變更"
    ```
    這會在 `alembic/versions/` 目錄中建立一個新的 Python 檔案，包含將資料庫從當前狀態遷移到新模型所需的變更。

4.  **審查遷移腳本**:
    **非常重要**：在應用遷移之前，請務必打開新產生的 `.py` 檔案 (`alembic/versions/xxxxx_your_message.py`) 仔細審查其內容，確保 Alembic 自動生成的 SQL 語句符合您的預期。Alembic 的 `autogenerate` 並非萬能。

5.  **應用遷移**:
    審查無誤後，執行以下指令將變更應用到資料庫：
    ```bash
    docker compose run --rm backend alembic upgrade head
    ```
    這將會執行所有尚未應用的遷移腳本，將資料庫更新到最新狀態。

---

## Team Collaboration Rules

### ✅ Do

* Always pull latest `dev` before starting work
* Create a feature branch for each task
* PR into `dev` (NOT `main`)
* Keep PR small (one PR = one feature)

### ❌ Don't

* Do NOT push directly to `main`
* Do NOT mix frontend + backend + firmware changes in one PR
* Do NOT commit `.env` / secrets

---

## Pull Request Checklist

Before creating PR:

* [ ] Code builds successfully
* [ ] Basic manual testing done
* [ ] No secrets committed
* [ ] PR title clearly describes the change

---

## Notes

* The `dev` branch is expected to change frequently.
* Use `main` branch for demo/recording/submission.
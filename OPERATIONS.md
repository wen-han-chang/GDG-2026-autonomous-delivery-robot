# GDG 小車 — 操作手冊

## SSH 連線到 EC2

```powershell
ssh -i "C:\Users\willy\Downloads\gdg-robot-key.pem" ec2-user@3.27.165.128
```

---

## Docker 容器管理

### 查看所有容器狀態
```bash
docker ps -a
```

### 查看 log（即時）
```bash
docker logs robot-apriltag -f
docker logs robot-mqtt -f
docker logs robot-backend -f
docker logs robot-frontend -f
```

### 重啟單一容器
```bash
docker restart robot-apriltag
docker restart robot-mqtt
docker restart robot-backend
docker restart robot-frontend
```

### 重啟所有容器
```bash
cd ~/robot && docker compose restart
```

### 更新 cloud_server.py（本機執行）
```powershell
scp -i "C:\Users\willy\Downloads\gdg-robot-key.pem" "C:\Users\willy\OneDrive\桌面\gdg小車\server\cloud_server.py" ec2-user@3.27.165.128:~/robot/server/cloud_server.py
```

```bash
docker cp ~/robot/server/cloud_server.py robot-apriltag:/app/cloud_server.py && docker restart robot-apriltag
```

---

## 控車 MQTT 指令

> 在 EC2 SSH 內執行

### 前進
```bash
docker exec robot-mqtt mosquitto_pub -t car/cmd -m '{"cmd":"forward","speed":100}'
```

### 左轉
```bash
docker exec robot-mqtt mosquitto_pub -t car/cmd -m '{"cmd":"left","speed":100}'
```

### 右轉
```bash
docker exec robot-mqtt mosquitto_pub -t car/cmd -m '{"cmd":"right","speed":100}'
```

### 停車
```bash
docker exec robot-mqtt mosquitto_pub -t car/cmd -m '{"cmd":"stop","speed":0}'
```

### 後退
```bash
docker exec robot-mqtt mosquitto_pub -t car/cmd -m '{"cmd":"backward","speed":100}'
```

### 等待取餐（停車等重量變化）
```bash
docker exec robot-mqtt mosquitto_pub -t car/cmd -m '{"cmd":"wait_weight","speed":0}'
```

### 手動觸發路口辨識
```bash
docker exec robot-mqtt mosquitto_pub -t car/at_node -m '{"state":"at_node"}'
```

### 手動觸發 ESP32-CAM 拍照
```bash
docker exec robot-mqtt mosquitto_pub -t car/capture_req -m '1'
```

---

## 抓取最新拍照圖片

### EC2 上執行
```bash
docker exec robot-apriltag ls -t /tmp/debug_*.jpg | head -1 | xargs -I{} sh -c 'docker cp robot-apriltag:{} ~/latest.jpg'
```

### 下載到本機（PowerShell）
```powershell
scp -i "C:\Users\willy\Downloads\gdg-robot-key.pem" ec2-user@3.27.165.128:~/latest.jpg "C:\Users\willy\Downloads\latest.jpg"
```

---

## 重置 heading（heading 錯亂時）
```bash
docker restart robot-apriltag
```

---

## MQTT Topic 對照表

| Topic | 方向 | 說明 |
|---|---|---|
| `car/cmd` | Server → 小車 | 行進指令 |
| `car/at_node` | 小車 → Server | 偵測到路口 |
| `car/capture_req` | Server → ESP32-CAM | 觸發拍照 |
| `car/node_id` | Server → 小車 | AprilTag 辨識結果 |
| `car/cam_ip` | ESP32-CAM → Server | 相機 IP（retained）|
| `car/weight_event` | 小車 → Server | 重量變化事件 |
| `car/status` | 小車 → Server | 小車狀態 |

---

## AWS EC2 監控

### 方法一：AWS Console
1. 開啟瀏覽器前往 [console.aws.amazon.com](https://console.aws.amazon.com)
2. 右上角區域切換為 **ap-southeast-2（雪梨）**
3. 進入 EC2 → Instances → 選擇 instance
4. 下方 **Monitoring** 頁籤可看 CPU、Network 使用率

### 方法二：SSH 直接查看
```bash
# CPU / 記憶體使用率
top

# 各容器資源使用
docker stats

# 磁碟空間
df -h

# 記憶體
free -h
```

### 方法三：CloudWatch（詳細監控）
1. AWS Console → CloudWatch → Metrics
2. 選 EC2 → Per-Instance Metrics
3. 選擇 instance ID 查看 CPUUtilization、NetworkIn/Out

---

## 服務端點

| 服務 | URL |
|---|---|
| 前端 | http://3.27.165.128 |
| 主後端 API | http://3.27.165.128:8001 |
| AprilTag 服務 | http://3.27.165.128:8000 |
| Health Check | http://3.27.165.128:8000/health |
| MQTT Broker | 3.27.165.128:1883 |

---

## ESP32 燒錄注意事項

### ESP32-CAM 燒錄步驟
1. GPIO0 接 GND
2. 插上 USB
3. Arduino IDE 點上傳
4. 看到 `Connecting...` 後拔掉 GPIO0 的 GND
5. 上傳完成後按 Reset
6. 平時運作只需接 5V + GND

### 主控 ESP32
- 正常燒錄，不需要特殊操作
- 燒錄後自動重啟

---

## 地圖與路徑

```
[0] ── [1] ── [2] ── [3]
               |
              [4] ── [5] ← 目的地
```

| 在 node | 下一步 | 指令 |
|---|---|---|
| 0 | → 1 | forward |
| 1 | → 2 | forward |
| 2 | → 4 | right |
| 3 | → 2 | left（掉頭）|
| 4 | → 5 | left |
| 5 | 到達 | wait_weight |

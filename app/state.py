from typing import Dict, Any, List
from datetime import datetime
from .models import MapData # 確保 models.py 已經包含 MapData

# ==========================================
# 1. 既有的地圖與機器人狀態 (Robot State)
# ==========================================
# 用於儲存地圖資料 (Map Upload)
MAP_STORE: Dict[str, MapData] = {}

# 用於儲存 NetworkX Graph 物件 (Path Finding)
GRAPH_STORE: Dict[str, Any] = {}   

# 用於儲存即時訂單狀態 (WebSocket Telemetry)
# Key: order_id
ORDER_STORE: Dict[str, Dict[str, Any]] = {}


# ==========================================
# 2. 新增的使用者與 Mock 資料庫 (User State)
# ==========================================

# 模擬使用者資料庫 (In-Memory)
# 預設有一筆測試帳號
fake_users_db = {
    "test@example.com": {
        "id": "u_test_001",
        "email": "test@example.com",
        "name": "測試用戶",
        # 密碼是 "123456" 的 bcrypt hash
        "hashed_password": "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWrn3ILA/qzfG.g.q/Bq.L1.L1.L1",
        "createdAt": datetime.now().isoformat()
    }
}

# 模擬訂單歷史紀錄 (App History)
fake_orders_db = [
    {
        "user_email": "test@example.com", 
        "id": "O001",
        "date": "2026-01-18",
        "store": "讚野烤肉飯",
        "items": ["招牌便當 x1", "紅茶 x2"],
        "total": 130,
        "status": "已完成"
    },
    {
        "user_email": "test@example.com",
        "id": "O002",
        "date": "2026-01-19",
        "store": "台灣第二味",
        "items": ["珍珠奶茶 x3"],
        "total": 105,
        "status": "已完成"
    }
]
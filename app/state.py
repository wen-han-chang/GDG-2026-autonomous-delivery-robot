from typing import Dict, Any
from .models import MapData

# ==========================================
# 地圖與路徑規劃 (In-Memory)
# ==========================================

# 用於儲存地圖資料
MAP_STORE: Dict[str, MapData] = {}

# 用於儲存 Graph 物件 (Path Finding)
GRAPH_STORE: Dict[str, Any] = {}

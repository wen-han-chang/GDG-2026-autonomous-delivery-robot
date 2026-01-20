from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/stores", tags=["stores"])

# Mock data - 店家資料
STORE_STORE = {
    "S001": {
        "id": "S001",
        "name": "讚野烤肉飯",
        "description": "新鮮食材，現點現做",
        "category": "餐廳",
        "rating": 4.5,
        "deliveryTime": "5-10 分鐘",
        "image": "https://images.unsplash.com/photo-1504674900247-0877df9cc836?w=400&h=300&fit=crop",
        "location_node": "A"
    },
    "S002": {
        "id": "S002",
        "name": "台灣第二味",
        "description": "台灣味手搖飲",
        "category": "飲料",
        "rating": 4.8,
        "deliveryTime": "3-5 分鐘",
        "image": "https://images.unsplash.com/photo-1558857563-b371033873b8?w=400&h=300&fit=crop",
        "location_node": "A"
    },
    "S003": {
        "id": "S003",
        "name": "8-11便利商店",
        "description": "24小時全年無休",
        "category": "便利商店",
        "rating": 4.2,
        "deliveryTime": "5-8 分鐘",
        "image": "https://images.unsplash.com/photo-1604719312566-8912e9227c6a?w=400&h=300&fit=crop",
        "location_node": "X1"
    }
}

# Mock data - 商品資料
PRODUCT_STORE = {
    "P001": {
        "id": "P001",
        "store_id": "S001",
        "name": "招牌便當",
        "price": 80,
        "description": "主菜 + 三樣配菜 + 白飯",
        "image": "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=400&h=300&fit=crop"
    },
    "P002": {
        "id": "P002",
        "store_id": "S001",
        "name": "雞腿便當",
        "price": 100,
        "description": "酥炸雞腿 + 三樣配菜 + 白飯",
        "image": "https://images.unsplash.com/photo-1598515214211-89d3c73ae83b?w=400&h=300&fit=crop"
    },
    "P003": {
        "id": "P003",
        "store_id": "S001",
        "name": "排骨便當",
        "price": 90,
        "description": "香酥排骨 + 三樣配菜 + 白飯",
        "image": "https://images.unsplash.com/photo-1432139509613-5c4255815697?w=400&h=300&fit=crop"
    },
    "P004": {
        "id": "P004",
        "store_id": "S002",
        "name": "紅茶",
        "price": 25,
        "description": "古早味紅茶 500ml",
        "image": "https://images.unsplash.com/photo-1556679343-c7306c1976bc?w=400&h=300&fit=crop"
    },
    "P005": {
        "id": "P005",
        "store_id": "S002",
        "name": "綠茶",
        "price": 25,
        "description": "無糖綠茶 500ml",
        "image": "https://images.unsplash.com/photo-1627435601361-ec25f5b1d0e5?w=400&h=300&fit=crop"
    },
    "P006": {
        "id": "P006",
        "store_id": "S002",
        "name": "珍珠奶茶",
        "price": 35,
        "description": "香濃珍珠奶茶 500ml",
        "image": "https://images.unsplash.com/photo-1558857563-b371033873b8?w=400&h=300&fit=crop"
    },
    "P007": {
        "id": "P007",
        "store_id": "S003",
        "name": "泡麵",
        "price": 35,
        "description": "經典牛肉麵",
        "image": "https://images.unsplash.com/photo-1569718212165-3a8278d5f624?w=400&h=300&fit=crop"
    },
    "P008": {
        "id": "P008",
        "store_id": "S003",
        "name": "餅乾",
        "price": 45,
        "description": "綜合餅乾組合包",
        "image": "https://images.unsplash.com/photo-1499636136210-6f4ee915583e?w=400&h=300&fit=crop"
    }
}


@router.get("")
def get_stores():
    return list(STORE_STORE.values())


@router.get("/{store_id}")
def get_store(store_id: str):
    if store_id not in STORE_STORE:
        raise HTTPException(status_code=404, detail="store not found")
    return STORE_STORE[store_id]


@router.get("/{store_id}/products")
def get_products_by_store(store_id: str):
    if store_id not in STORE_STORE:
        raise HTTPException(status_code=404, detail="store not found")
    return [p for p in PRODUCT_STORE.values() if p["store_id"] == store_id]

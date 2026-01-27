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
    },
    "S004": {
        "id": "S004",
        "name": "麥脆雞",
        "description": "酥脆炸雞專賣店",
        "category": "餐廳",
        "rating": 4.3,
        "deliveryTime": "8-12 分鐘",
        "image": "https://images.unsplash.com/photo-1626645738196-c2a7c87a8f58?w=400&h=300&fit=crop",
        "location_node": "X2"
    },
    "S005": {
        "id": "S005",
        "name": "健康沙拉吧",
        "description": "新鮮蔬果輕食",
        "category": "輕食",
        "rating": 4.6,
        "deliveryTime": "5-8 分鐘",
        "image": "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?w=400&h=300&fit=crop",
        "location_node": "B"
    },
    "S006": {
        "id": "S006",
        "name": "咖啡研究室",
        "description": "精品咖啡與甜點",
        "category": "咖啡",
        "rating": 4.7,
        "deliveryTime": "5-10 分鐘",
        "image": "https://images.unsplash.com/photo-1509042239860-f550ce710b93?w=400&h=300&fit=crop",
        "location_node": "C"
    },
    "S007": {
        "id": "S007",
        "name": "日式拉麵屋",
        "description": "道地日本風味拉麵",
        "category": "餐廳",
        "rating": 4.4,
        "deliveryTime": "10-15 分鐘",
        "image": "/images/stores/ramen.png",
        "location_node": "D"
    },
    "S008": {
        "id": "S008",
        "name": "水果天堂",
        "description": "現切水果與果汁",
        "category": "飲料",
        "rating": 4.5,
        "deliveryTime": "5-8 分鐘",
        "image": "https://images.unsplash.com/photo-1490474418585-ba9bad8fd0ea?w=400&h=300&fit=crop",
        "location_node": "A"
    },
    "S009": {
        "id": "S009",
        "name": "披薩工坊",
        "description": "手工現烤義式披薩",
        "category": "餐廳",
        "rating": 4.6,
        "deliveryTime": "12-18 分鐘",
        "image": "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=400&h=300&fit=crop",
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
    },
    "P009": {
        "id": "P009",
        "store_id": "S004",
        "name": "原味炸雞",
        "price": 75,
        "description": "酥脆多汁炸雞 3塊",
        "image": "https://images.unsplash.com/photo-1626645738196-c2a7c87a8f58?w=400&h=300&fit=crop"
    },
    "P010": {
        "id": "P010",
        "store_id": "S004",
        "name": "辣味炸雞",
        "price": 85,
        "description": "香辣炸雞 3塊",
        "image": "https://images.unsplash.com/photo-1575932444877-5106bee2a599?w=400&h=300&fit=crop"
    },
    "P011": {
        "id": "P011",
        "store_id": "S004",
        "name": "薯條",
        "price": 40,
        "description": "金黃酥脆薯條",
        "image": "https://images.unsplash.com/photo-1573080496219-bb080dd4f877?w=400&h=300&fit=crop"
    },
    "P012": {
        "id": "P012",
        "store_id": "S005",
        "name": "凱薩沙拉",
        "price": 95,
        "description": "羅蔓生菜+帕瑪森起司+凱薩醬",
        "image": "https://images.unsplash.com/photo-1550304943-4f24f54ddde9?w=400&h=300&fit=crop"
    },
    "P013": {
        "id": "P013",
        "store_id": "S005",
        "name": "雞肉沙拉",
        "price": 120,
        "description": "嫩煎雞胸+綜合蔬菜+油醋醬",
        "image": "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?w=400&h=300&fit=crop"
    },
    "P014": {
        "id": "P014",
        "store_id": "S005",
        "name": "鮮蔬果昔",
        "price": 65,
        "description": "香蕉+菠菜+蘋果",
        "image": "https://images.unsplash.com/photo-1502741224143-90386d7f8c82?w=400&h=300&fit=crop"
    },
    "P015": {
        "id": "P015",
        "store_id": "S006",
        "name": "美式咖啡",
        "price": 50,
        "description": "單品咖啡豆現沖",
        "image": "https://images.unsplash.com/photo-1509042239860-f550ce710b93?w=400&h=300&fit=crop"
    },
    "P016": {
        "id": "P016",
        "store_id": "S006",
        "name": "拿鐵",
        "price": 65,
        "description": "濃縮咖啡+綿密奶泡",
        "image": "https://images.unsplash.com/photo-1461023058943-07fcbe16d735?w=400&h=300&fit=crop"
    },
    "P017": {
        "id": "P017",
        "store_id": "S006",
        "name": "提拉米蘇",
        "price": 85,
        "description": "經典義式甜點",
        "image": "https://images.unsplash.com/photo-1571877227200-a0d98ea607e9?w=400&h=300&fit=crop"
    },
    "P018": {
        "id": "P018",
        "store_id": "S007",
        "name": "豚骨拉麵",
        "price": 140,
        "description": "濃郁豚骨湯底+叉燒+溏心蛋",
        "image": "/images/products/pork_ramen.png"
    },
    "P019": {
        "id": "P019",
        "store_id": "S007",
        "name": "醬油拉麵",
        "price": 130,
        "description": "醬油湯底+玉米+叉燒",
        "image": "/images/products/oil_ramen.png"
    },
    "P020": {
        "id": "P020",
        "store_id": "S007",
        "name": "煎餃",
        "price": 60,
        "description": "日式煎餃 6顆",
        "image": "https://images.unsplash.com/photo-1496116218417-1a781b1c416c?w=400&h=300&fit=crop"
    },
    "P021": {
        "id": "P021",
        "store_id": "S008",
        "name": "綜合水果盒",
        "price": 75,
        "description": "當季新鮮水果組合",
        "image": "https://images.unsplash.com/photo-1490474418585-ba9bad8fd0ea?w=400&h=300&fit=crop"
    },
    "P022": {
        "id": "P022",
        "store_id": "S008",
        "name": "西瓜汁",
        "price": 45,
        "description": "現打西瓜汁 500ml",
        "image": "https://images.unsplash.com/photo-1497534446932-c925b458314e?w=400&h=300&fit=crop"
    },
    "P023": {
        "id": "P023",
        "store_id": "S008",
        "name": "芒果冰沙",
        "price": 55,
        "description": "愛文芒果冰沙 500ml",
        "image": "https://images.unsplash.com/photo-1546173159-315724a31696?w=400&h=300&fit=crop"
    },
    "P024": {
        "id": "P024",
        "store_id": "S009",
        "name": "瑪格麗特披薩",
        "price": 180,
        "description": "番茄醬+莫札瑞拉起司+羅勒",
        "image": "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=400&h=300&fit=crop"
    },
    "P025": {
        "id": "P025",
        "store_id": "S009",
        "name": "夏威夷披薩",
        "price": 200,
        "description": "火腿+鳳梨+起司",
        "image": "https://images.unsplash.com/photo-1565299585323-38d6b0865b47?w=400&h=300&fit=crop"
    },
    "P026": {
        "id": "P026",
        "store_id": "S009",
        "name": "蒜香麵包",
        "price": 60,
        "description": "香蒜奶油烤麵包 4片",
        "image": "https://images.unsplash.com/photo-1619535860434-ba1d8fa12536?w=400&h=300&fit=crop"
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

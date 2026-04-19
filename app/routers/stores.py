from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..sql_models import StoreDB, ProductDB

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
        "image": "/images/stores/bbq_rice.png",
        "location_node": "A"
    },
    "S002": {
        "id": "S002",
        "name": "台灣第二味",
        "description": "台灣味手搖飲",
        "category": "飲料",
        "rating": 4.8,
        "deliveryTime": "3-5 分鐘",
        "image": "/images/stores/tw_second_flavor.png",
        "location_node": "B"
    },
    "S003": {
        "id": "S003",
        "name": "8-11便利商店",
        "description": "24小時全年無休",
        "category": "便利商店",
        "rating": 4.2,
        "deliveryTime": "5-8 分鐘",
        "image": "/images/stores/811.png",
        "location_node": "C"
    },
    "S004": {
        "id": "S004",
        "name": "麥脆雞",
        "description": "酥脆炸雞專賣店",
        "category": "餐廳",
        "rating": 4.3,
        "deliveryTime": "8-12 分鐘",
        "image": "/images/stores/chicken_store.png",
        "location_node": "D"
    },
    "S005": {
        "id": "S005",
        "name": "健康沙拉吧",
        "description": "新鮮蔬果輕食",
        "category": "輕食",
        "rating": 4.6,
        "deliveryTime": "5-8 分鐘",
        "image": "/images/stores/salad.png",
        "location_node": "E"
    },
    "S006": {
        "id": "S006",
        "name": "咖啡研究室",
        "description": "精品咖啡與甜點",
        "category": "咖啡",
        "rating": 4.7,
        "deliveryTime": "5-10 分鐘",
        "image": "/images/stores/coffee_shop.png",
        "location_node": "F"
    },
    "S007": {
        "id": "S007",
        "name": "日式拉麵屋",
        "description": "道地日本風味拉麵",
        "category": "餐廳",
        "rating": 4.4,
        "deliveryTime": "10-15 分鐘",
        "image": "/images/stores/ramen.png",
        "location_node": "G"
    },
    "S008": {
        "id": "S008",
        "name": "水果天堂",
        "description": "現切水果與果汁",
        "category": "飲料",
        "rating": 4.5,
        "deliveryTime": "5-8 分鐘",
        "image": "/images/stores/fruits.png",
        "location_node": "H"
    },
    "S009": {
        "id": "S009",
        "name": "披薩工坊",
        "description": "手工現烤義式披薩",
        "category": "餐廳",
        "rating": 4.6,
        "deliveryTime": "12-18 分鐘",
        "image": "/images/stores/pizza_store.png",
        "location_node": "I"
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
        "image": "/images/products/top_sale.png"
    },
    "P002": {
        "id": "P002",
        "store_id": "S001",
        "name": "雞腿便當",
        "price": 100,
        "description": "酥炸雞腿 + 三樣配菜 + 白飯",
        "image": "/images/products/chicken_rice.png"
    },
    "P003": {
        "id": "P003",
        "store_id": "S001",
        "name": "排骨便當",
        "price": 90,
        "description": "香酥排骨 + 三樣配菜 + 白飯",
        "image": "/images/products/pie_ku_rice.png"
    },
    "P004": {
        "id": "P004",
        "store_id": "S002",
        "name": "紅茶",
        "price": 25,
        "description": "古早味紅茶 500ml",
        "image": "/images/products/black_tea.png"
    },
    "P005": {
        "id": "P005",
        "store_id": "S002",
        "name": "綠茶",
        "price": 25,
        "description": "無糖綠茶 500ml",
        "image": "/images/products/green_tea.png"
    },
    "P006": {
        "id": "P006",
        "store_id": "S002",
        "name": "珍珠奶茶",
        "price": 35,
        "description": "香濃珍珠奶茶 500ml",
        "image": "/images/products/bubble_tea.png"
    },
    "P007": {
        "id": "P007",
        "store_id": "S003",
        "name": "泡麵",
        "price": 35,
        "description": "好吃的泡麵",
        "image": "/images/products/pao_mian.png"
    },
    "P008": {
        "id": "P008",
        "store_id": "S003",
        "name": "餅乾",
        "price": 45,
        "description": "餅乾組合包",
        "image": "/images/products/cookie.png"
    },
    "P009": {
        "id": "P009",
        "store_id": "S004",
        "name": "原味炸雞",
        "price": 75,
        "description": "酥脆多汁炸雞 3塊",
        "image": "/images/products/origin_chicken.png"
    },
    "P010": {
        "id": "P010",
        "store_id": "S004",
        "name": "辣味炸雞",
        "price": 85,
        "description": "香辣炸雞 3塊",
        "image": "/images/products/spicy_chicken.png"
    },
    "P011": {
        "id": "P011",
        "store_id": "S004",
        "name": "薯條",
        "price": 40,
        "description": "金黃酥脆薯條",
        "image": "/images/products/french_fries.png"
    },
    "P012": {
        "id": "P012",
        "store_id": "S005",
        "name": "凱薩沙拉",
        "price": 95,
        "description": "羅蔓生菜+帕瑪森起司+凱薩醬",
        "image": "/images/products/kaser_salad.png"
    },
    "P013": {
        "id": "P013",
        "store_id": "S005",
        "name": "雞肉沙拉",
        "price": 120,
        "description": "嫩煎雞胸+綜合蔬菜+油醋醬",
        "image": "/images/products/chicken_salad.png"
    },
    "P014": {
        "id": "P014",
        "store_id": "S005",
        "name": "鮮蔬果昔",
        "price": 65,
        "description": "香蕉+菠菜+蘋果",
        "image": "/images/products/juice.png"
    },
    "P015": {
        "id": "P015",
        "store_id": "S006",
        "name": "美式咖啡",
        "price": 50,
        "description": "單品咖啡豆現沖",
        "image": "/images/products/america_coffee.png"
    },
    "P016": {
        "id": "P016",
        "store_id": "S006",
        "name": "拿鐵",
        "price": 65,
        "description": "濃縮咖啡+綿密奶泡",
        "image": "/images/products/latte.png"
    },
    "P017": {
        "id": "P017",
        "store_id": "S006",
        "name": "提拉米蘇",
        "price": 85,
        "description": "經典義式甜點",
        "image": "/images/products/cake.png"
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
        "image": "/images/products/dumplings.png"
    },
    "P021": {
        "id": "P021",
        "store_id": "S008",
        "name": "綜合水果盒",
        "price": 75,
        "description": "當季新鮮水果組合",
        "image": "/images/products/fruits_box.png"
    },
    "P022": {
        "id": "P022",
        "store_id": "S008",
        "name": "西瓜汁",
        "price": 45,
        "description": "現打西瓜汁 500ml",
        "image": "/images/products/watermalen.png"
    },
    "P023": {
        "id": "P023",
        "store_id": "S008",
        "name": "芒果冰沙",
        "price": 55,
        "description": "愛文芒果冰沙 500ml",
        "image": "/images/products/mongo.png"
    },
    "P024": {
        "id": "P024",
        "store_id": "S009",
        "name": "瑪格麗特披薩",
        "price": 180,
        "description": "番茄醬+莫札瑞拉起司+羅勒",
        "image": "/images/products/magalita_pizza.png"
    },
    "P025": {
        "id": "P025",
        "store_id": "S009",
        "name": "夏威夷披薩",
        "price": 200,
        "description": "火腿+鳳梨+起司",
        "image": "/images/products/hkawii_pizza.png"
    },
    "P026": {
        "id": "P026",
        "store_id": "S009",
        "name": "蒜香麵包",
        "price": 60,
        "description": "香蒜奶油烤麵包 4片",
        "image": "/images/products/onion_bread.png"
    }
}


@router.get("")
def get_stores(db: Session = Depends(get_db)):
    # 改為從雲端資料庫抓取
    return db.query(StoreDB).all()

@router.get("/{store_id}")
def get_store(store_id: str, db: Session = Depends(get_db)):
    # 改為從雲端資料庫篩選
    store = db.query(StoreDB).filter(StoreDB.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="store not found")
    return store

@router.get("/{store_id}/products")
def get_products_by_store(store_id: str, db: Session = Depends(get_db)):
    # 確保店家存在，並從資料庫抓取該店商品
    store = db.query(StoreDB).filter(StoreDB.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="store not found")
    return db.query(ProductDB).filter(ProductDB.store_id == store_id).all()

# app/routers/cart.py (新增這個檔案)
from fastapi import APIRouter

router = APIRouter(prefix="/cart", tags=["cart"])

@router.get("")
def get_cart():
    return {"items": [], "total": 0}

@router.post("")
def sync_cart(cart_data: dict):
    # 之後可以把購物車存到資料庫
    return {"success": True, "message": "Cart synced"}
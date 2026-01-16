from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/stores", tags=["stores"])

# mock data
STORE_STORE = {
    "s1": {"id": "s1", "name": "Store A"},
    "s2": {"id": "s2", "name": "Store B"},
}

PRODUCT_STORE = {
    "p1": {"id": "p1", "name": "Apple", "store_id": "s1"},
    "p2": {"id": "p2", "name": "Orange", "store_id": "s1"},
    "p3": {"id": "p3", "name": "Bread", "store_id": "s2"},
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

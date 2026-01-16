from fastapi import APIRouter
from .stores import PRODUCT_STORE

router = APIRouter(prefix="/products", tags=["products"])

@router.get("")
def get_products():
    return list(PRODUCT_STORE.values())

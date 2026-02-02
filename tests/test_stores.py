"""商店 API 測試"""
import pytest


class TestStores:
    """商店相關測試"""

    def test_get_all_stores(self, client):
        """測試取得所有商店"""
        response = client.get("/stores")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

        # 檢查商店資料結構
        store = data[0]
        assert "id" in store
        assert "name" in store
        assert "category" in store
        assert "rating" in store

    def test_get_store_by_id(self, client):
        """測試取得單一商店"""
        response = client.get("/stores/S001")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "S001"
        assert data["name"] == "讚野烤肉飯"

    def test_get_store_not_found(self, client):
        """測試商店不存在"""
        response = client.get("/stores/NOTEXIST")
        assert response.status_code == 404

    def test_get_store_products(self, client):
        """測試取得商店商品"""
        response = client.get("/stores/S001/products")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

        # 檢查商品資料結構
        if len(data) > 0:
            product = data[0]
            assert "id" in product
            assert "name" in product
            assert "price" in product
            assert product["store_id"] == "S001"

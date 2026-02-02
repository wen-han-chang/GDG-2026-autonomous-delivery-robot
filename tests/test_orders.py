"""訂單 API 測試"""
import pytest


class TestOrders:
    """訂單相關測試"""

    def test_create_order_success(self, client):
        """測試成功建立訂單"""
        response = client.post("/orders", json={
            "map_id": "campus_demo",
            "from_node": "A",
            "to_node": "D",
            "algorithm": "dijkstra",
            "store_name": "測試商店",
            "items": ["商品A x1"],
            "total": 100,
            "user_email": "test@test.com"
        })
        assert response.status_code == 200
        data = response.json()
        assert "order_id" in data
        assert data["map_id"] == "campus_demo"
        assert isinstance(data["route"], list)
        assert data["total_distance_cm"] > 0
        assert data["eta_sec"] > 0

    def test_create_order_invalid_map(self, client):
        """測試無效的地圖 ID"""
        response = client.post("/orders", json={
            "map_id": "nonexistent_map",
            "from_node": "A",
            "to_node": "B"
        })
        assert response.status_code == 404
        assert "map_id not loaded" in response.json()["detail"]

    def test_create_order_astar(self, client):
        """測試使用 A* 演算法"""
        response = client.post("/orders", json={
            "map_id": "campus_demo",
            "from_node": "A",
            "to_node": "D",
            "algorithm": "astar"
        })
        assert response.status_code == 200

    def test_get_order_success(self, client):
        """測試取得訂單"""
        # 先建立訂單
        create_response = client.post("/orders", json={
            "map_id": "campus_demo",
            "from_node": "A",
            "to_node": "D"
        })
        order_id = create_response.json()["order_id"]

        # 取得訂單
        response = client.get(f"/orders/{order_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == order_id

    def test_get_order_not_found(self, client):
        """測試訂單不存在"""
        response = client.get("/orders/NOTEXIST")
        assert response.status_code == 404


class TestRootEndpoint:
    """根端點測試"""

    def test_root(self, client):
        """測試根端點"""
        response = client.get("/")
        assert response.status_code == 200
        assert "running" in response.json()["message"]

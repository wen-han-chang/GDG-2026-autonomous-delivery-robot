"""訂單 API 測試"""


class TestOrders:
    """訂單相關測試（需要認證）"""

    def test_create_order_success(self, client, auth_header):
        """測試成功建立訂單"""
        response = client.post("/orders", json={
            "map_id": "campus_demo",
            "from_node": "A",
            "to_node": "D",
            "algorithm": "dijkstra",
            "store_name": "測試商店",
            "items": ["商品A x1"],
            "total": 100,
        }, headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert "order_id" in data
        assert data["map_id"] == "campus_demo"
        assert isinstance(data["route"], list)
        assert data["total_distance_cm"] > 0
        assert data["eta_sec"] > 0

    def test_create_order_unauthorized(self, client):
        """測試未認證時建立訂單回 401"""
        response = client.post("/orders", json={
            "map_id": "campus_demo",
            "from_node": "A",
            "to_node": "D",
        })
        assert response.status_code == 401

    def test_create_order_invalid_map(self, client, auth_header):
        """測試無效的地圖 ID"""
        response = client.post("/orders", json={
            "map_id": "nonexistent_map",
            "from_node": "A",
            "to_node": "B"
        }, headers=auth_header)
        assert response.status_code == 404
        assert "map_id not loaded" in response.json()["detail"]

    def test_create_order_astar(self, client, auth_header):
        """測試使用 A* 演算法"""
        response = client.post("/orders", json={
            "map_id": "campus_demo",
            "from_node": "A",
            "to_node": "D",
            "algorithm": "astar"
        }, headers=auth_header)
        assert response.status_code == 200

    def test_create_order_rejects_multi_payload(self, client, auth_header):
        """舊單店端點不得混用多店 payload"""
        response = client.post("/orders", json={
            "map_id": "campus_demo",
            "store_ids": ["S001", "S002"],
            "to_node": "A"
        }, headers=auth_header)
        assert response.status_code == 400
        assert "Use /orders/multi" in response.json()["detail"]

    def test_create_multi_order_success(self, client, auth_header):
        """測試多店一次下單"""
        response = client.post("/orders/multi", json={
            "map_id": "campus_demo",
            "store_ids": ["S001", "S002"],
            "to_node": "A",
            "items_by_store": {
                "S001": ["招牌便當 x1"],
                "S002": ["紅茶 x2"]
            },
            "total": 130
        }, headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert data["map_id"] == "campus_demo"
        assert len(data["order_ids"]) == 2
        assert len(data["orders"]) == 2
        assert data["total_distance_cm"] > 0
        assert data["max_eta_sec"] > 0

    def test_create_multi_order_store_not_found(self, client, auth_header):
        """測試多店下單含不存在店家"""
        response = client.post("/orders/multi", json={
            "map_id": "campus_demo",
            "store_ids": ["S001", "S999"],
            "to_node": "A"
        }, headers=auth_header)
        assert response.status_code == 404
        assert "store_ids not found" in response.json()["detail"]

    def test_get_order_success(self, client, auth_header):
        """測試取得訂單"""
        # 先建立訂單
        create_response = client.post("/orders", json={
            "map_id": "campus_demo",
            "from_node": "A",
            "to_node": "D"
        }, headers=auth_header)
        order_id = create_response.json()["order_id"]

        # 取得訂單
        response = client.get(f"/orders/{order_id}", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == order_id

    def test_get_order_not_found(self, client, auth_header):
        """測試訂單不存在"""
        response = client.get("/orders/NOTEXIST", headers=auth_header)
        assert response.status_code == 404

    def test_get_order_forbidden(self, client, auth_header):
        """測試無法查看他人訂單"""
        # 用第一個使用者建立訂單
        create_response = client.post("/orders", json={
            "map_id": "campus_demo",
            "from_node": "A",
            "to_node": "D"
        }, headers=auth_header)
        order_id = create_response.json()["order_id"]

        # 註冊第二個使用者
        client.post("/auth/register", json={
            "email": "other@test.com",
            "password": "testpass123",
            "name": "Other"
        })
        login_resp = client.post("/auth/login", json={
            "email": "other@test.com",
            "password": "testpass123"
        })
        other_token = login_resp.json()["token"]
        other_header = {"Authorization": f"Bearer {other_token}"}

        # 用第二個使用者查詢第一個使用者的訂單
        response = client.get(f"/orders/{order_id}", headers=other_header)
        assert response.status_code == 403


class TestRootEndpoint:
    """根端點測試"""

    def test_root(self, client):
        """測試根端點"""
        response = client.get("/")
        assert response.status_code == 200
        assert "running" in response.json()["message"]

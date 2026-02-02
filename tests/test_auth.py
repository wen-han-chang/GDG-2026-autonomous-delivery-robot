"""認證 API 測試"""
import pytest


class TestRegister:
    """註冊功能測試"""

    def test_register_success(self, client):
        """測試成功註冊"""
        response = client.post("/auth/register", json={
            "email": "newuser@test.com",
            "password": "Test123456",
            "name": "新用戶"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "token" in data
        assert data["user"]["email"] == "newuser@test.com"
        assert data["user"]["name"] == "新用戶"

    def test_register_duplicate_email(self, client):
        """測試重複 Email 註冊"""
        # 先註冊一次
        client.post("/auth/register", json={
            "email": "duplicate@test.com",
            "password": "Test123456",
            "name": "用戶1"
        })

        # 再用同樣的 Email 註冊
        response = client.post("/auth/register", json={
            "email": "duplicate@test.com",
            "password": "Test123456",
            "name": "用戶2"
        })
        assert response.status_code == 400
        assert "已經註冊" in response.json()["detail"]

    def test_register_invalid_email(self, client):
        """測試無效 Email 格式"""
        response = client.post("/auth/register", json={
            "email": "invalid-email",
            "password": "Test123456",
            "name": "用戶"
        })
        assert response.status_code == 422  # Validation error


class TestLogin:
    """登入功能測試"""

    def test_login_success(self, client):
        """測試成功登入"""
        # 先註冊
        client.post("/auth/register", json={
            "email": "login@test.com",
            "password": "Test123456",
            "name": "登入測試"
        })

        # 登入
        response = client.post("/auth/login", json={
            "email": "login@test.com",
            "password": "Test123456"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "token" in data

    def test_login_wrong_password(self, client):
        """測試錯誤密碼"""
        # 先註冊
        client.post("/auth/register", json={
            "email": "wrongpw@test.com",
            "password": "Test123456",
            "name": "測試"
        })

        # 用錯誤密碼登入
        response = client.post("/auth/login", json={
            "email": "wrongpw@test.com",
            "password": "WrongPassword"
        })
        assert response.status_code == 400
        assert "錯誤" in response.json()["detail"]

    def test_login_nonexistent_user(self, client):
        """測試不存在的用戶"""
        response = client.post("/auth/login", json={
            "email": "notexist@test.com",
            "password": "Test123456"
        })
        assert response.status_code == 400

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.sql_models import StoreDB, ProductDB
from app.routers.stores import STORE_STORE, PRODUCT_STORE


# 使用 SQLite 記憶體資料庫進行測試
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def client():
    """建立測試用的 FastAPI TestClient"""
    # 建立測試資料表
    Base.metadata.create_all(bind=engine)

    # 覆蓋資料庫依賴
    app.dependency_overrides[get_db] = override_get_db

    # 植入商店與商品測試資料
    db = TestingSessionLocal()
    try:
        if db.query(StoreDB).count() == 0:
            for info in STORE_STORE.values():
                db.add(StoreDB(**info))
            for info in PRODUCT_STORE.values():
                db.add(ProductDB(**info))
            db.commit()
    finally:
        db.close()

    with TestClient(app) as test_client:
        yield test_client

    # 清理資料表
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def auth_header(client):
    """註冊測試使用者並登入（cookie 存於 TestClient jar，不再需要 Bearer header）"""
    client.post("/auth/register", json={
        "email": "order_test@test.com",
        "password": "testpass123",
        "name": "OrderTester"
    })
    client.post("/auth/login", json={
        "email": "order_test@test.com",
        "password": "testpass123"
    })
    return {}


@pytest.fixture(scope="function")
def db_session():
    """建立測試用的資料庫 Session"""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Set, Dict, Any
import json

from .models import Telemetry
from .database import SessionLocal
from .sql_models import OrderDB


ws_router = APIRouter()
CLIENTS: Set[WebSocket] = set()

async def broadcast(msg: Dict[str, Any]):
    dead = []
    for ws in CLIENTS:
        try:
            await ws.send_text(json.dumps(msg, ensure_ascii=False))
        except Exception:
            dead.append(ws)
    for ws in dead:
        CLIENTS.discard(ws)


def update_order_in_db(order_id: str, status: str):
    """同步更新資料庫中的訂單狀態"""
    db = SessionLocal()
    try:
        order = db.query(OrderDB).filter(OrderDB.id == order_id).first()
        if order:
            order.status = status
            db.commit()
            return True
        return False
    except Exception as e:
        db.rollback()
        print(f"❌ Failed to update order {order_id}: {e}")
        return False
    finally:
        db.close()


@ws_router.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    CLIENTS.add(ws)
    try:
        await ws.send_text(json.dumps({"type": "hello", "msg": "connected"}, ensure_ascii=False))
        while True:
            text = await ws.receive_text()
            data = json.loads(text)

            # 兩種消息：
            # 1) telemetry (robot -> server)
            # 2) subscribe (android -> server)
            msg_type = data.get("type")

            if msg_type == "telemetry":
                t = Telemetry.model_validate(data["payload"])

                # 更新資料庫中的訂單狀態
                update_order_in_db(t.order_id, t.state)

                # 廣播給所有連線的客戶端
                await broadcast({
                    "type": "order_update",
                    "order_id": t.order_id,
                    "robot_id": t.robot_id,
                    "node": t.node,
                    "progress": t.progress,
                    "speed": t.speed,
                    "state": t.state
                })

            elif msg_type == "subscribe":
                await ws.send_text(json.dumps({"type": "subscribed", "payload": data.get("payload")}, ensure_ascii=False))
            else:
                await ws.send_text(json.dumps({"type": "error", "msg": "unknown message type"}, ensure_ascii=False))

    except WebSocketDisconnect:
        CLIENTS.discard(ws)

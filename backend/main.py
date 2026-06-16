"""WIFY 서버 진입점.

ESP32 <-> Mosquitto <-> Server <-> Mosquitto <-> Android 중계.
- MQTT 브릿지: Mosquitto 상시 연결, 구독/발행
- REST API: 디바이스 상태 조회 + 명령 발행
- WebSocket: 실시간 이벤트 푸시
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.api.devices import router as devices_router
from backend.bridge import bridge
from backend.config import settings
from backend.ws import broadcaster

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await bridge.start()
    yield
    await bridge.stop()


app = FastAPI(title="WIFY Server", version="0.1.0", lifespan=lifespan)

# Android 앱/대시보드에서 접근 가능하도록 CORS 개방 (운영 시 도메인 제한 권장)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(devices_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "mqtt_connected": bridge.connected}


@app.websocket("/ws")
async def ws_events(ws: WebSocket) -> None:
    """접속 클라이언트에게 모든 디바이스의 인바운드 이벤트를 실시간 전달."""
    await broadcaster.connect(ws)
    try:
        while True:
            # 클라이언트로부터의 메시지는 keepalive 용도로만 소비
            await ws.receive_text()
    except WebSocketDisconnect:
        await broadcaster.disconnect(ws)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.http_host,
        port=settings.http_port,
        reload=True,
    )

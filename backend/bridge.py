"""MQTT 브릿지.

Mosquitto 브로커에 상시 연결을 유지하면서
- ESP32 가 올린 메시지를 구독 -> 상태 저장 + WebSocket 브로드캐스트
- API 요청에 따라 ESP32 로 명령 발행
을 담당한다.
"""

import asyncio
import logging

import aiomqtt

from backend import topics
from backend.config import settings
from backend.store import Event, _now, store
from backend.ws import broadcaster

log = logging.getLogger("wify.bridge")

RECONNECT_INTERVAL = 5  # 초


class MqttBridge:
    def __init__(self) -> None:
        self._client: aiomqtt.Client | None = None
        self._task: asyncio.Task | None = None
        self._stopping = False

    # --- lifecycle ---
    async def start(self) -> None:
        self._stopping = False
        self._task = asyncio.create_task(self._run(), name="mqtt-bridge")

    async def stop(self) -> None:
        self._stopping = True
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    @property
    def connected(self) -> bool:
        return self._client is not None

    # --- 발행 (Server -> ESP32) ---
    async def publish(self, topic: str, payload: str, qos: int = 1) -> None:
        if self._client is None:
            raise RuntimeError("MQTT broker is not connected")
        await self._client.publish(topic, payload.encode(), qos=qos)
        log.info("PUB %s <- %s", topic, payload)

    async def send_baseline(self, device_id: str) -> None:
        await self.publish(topics.device_topic(device_id, topics.SUB_BASELINE), "BASELINE")

    async def send_network(self, device_id: str, wifi_id: str, passwd: str) -> None:
        payload = f"id:{wifi_id}/passwd:{passwd}"
        await self.publish(topics.device_topic(device_id, topics.SUB_EDIT_NETWORK), payload)

    async def send_network_apply(self, device_id: str) -> None:
        await self.publish(
            topics.device_topic(device_id, topics.SUB_EDIT_EDITNETWORK), "NEWNETWORKEDIT"
        )

    # --- 내부 루프 ---
    async def _run(self) -> None:
        while not self._stopping:
            try:
                async with aiomqtt.Client(
                    hostname=settings.mqtt_host,
                    port=settings.mqtt_port,
                    username=settings.mqtt_username or None,
                    password=settings.mqtt_password or None,
                    identifier=settings.mqtt_client_id,
                ) as client:
                    self._client = client
                    await client.subscribe(topics.SUBSCRIBE_PATTERN)
                    log.info("MQTT connected, subscribed to %s", topics.SUBSCRIBE_PATTERN)
                    async for message in client.messages:
                        await self._dispatch(message)
            except aiomqtt.MqttError as exc:
                self._client = None
                if self._stopping:
                    break
                log.warning("MQTT error: %s — reconnecting in %ss", exc, RECONNECT_INTERVAL)
                await asyncio.sleep(RECONNECT_INTERVAL)
            finally:
                self._client = None

    async def _dispatch(self, message) -> None:
        topic = str(message.topic)
        device_id, suffix = topics.parse(topic)
        if device_id is None or suffix is None:
            return

        try:
            payload = message.payload.decode()
        except (UnicodeDecodeError, AttributeError):
            payload = repr(message.payload)

        # 인바운드(ESP -> Server) 토픽만 상태에 반영. 서버가 발행한 명령 echo 는 무시.
        if suffix in topics.INBOUND_SUFFIXES:
            self._apply_state(device_id, suffix, payload)
            store.record_event(Event(device_id=device_id, suffix=suffix, payload=payload))
            await broadcaster.broadcast(
                {"device_id": device_id, "suffix": suffix, "payload": payload}
            )
            log.info("SUB %s -> %s", topic, payload)

    def _apply_state(self, device_id: str, suffix: str, payload: str) -> None:
        if suffix == topics.SUB_STATUS:
            store.update(device_id, status=payload)
        elif suffix == topics.SUB_HEARTBEAT:
            store.update(device_id, last_heartbeat=_now())
        elif suffix == topics.SUB_RESTROOM:
            store.update(device_id, restroom=payload)
        elif suffix == topics.SUB_AI:
            store.update(device_id, ai=payload)
        elif suffix == topics.SUB_NOWNETWORK:
            store.update(device_id, network=payload)
        elif suffix == topics.SUB_NOWNETWORK_STATUS:
            store.update(device_id, network_status=payload)


bridge = MqttBridge()

"""인메모리 디바이스 상태/이벤트 저장소.

MVP 용. 나중에 SQLite / Supabase / Firestore 로 교체하기 쉽도록
DeviceStore 인터페이스를 단순하게 유지한다.
"""

from collections import deque
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from backend.config import settings


def _now() -> datetime:
    return datetime.now(timezone.utc)


class DeviceState(BaseModel):
    """디바이스 최신 상태 스냅샷."""

    device_id: str
    status: str | None = None          # online / offline
    last_heartbeat: datetime | None = None
    restroom: str | None = None        # ACT / DEACT / LOAD
    ai: str | None = None              # DAN / NOR / WARN
    network: str | None = None         # 현재 네트워크 정보
    network_status: str | None = None  # connect / disconnect
    updated_at: datetime = Field(default_factory=_now)


class Event(BaseModel):
    """수신한 단일 MQTT 메시지 기록."""

    device_id: str
    suffix: str
    payload: str
    at: datetime = Field(default_factory=_now)


class DeviceStore:
    def __init__(self, buffer_size: int = 200) -> None:
        self._buffer_size = buffer_size
        self._states: dict[str, DeviceState] = {}
        self._events: dict[str, deque[Event]] = {}

    def get_or_create(self, device_id: str) -> DeviceState:
        state = self._states.get(device_id)
        if state is None:
            state = DeviceState(device_id=device_id)
            self._states[device_id] = state
            self._events[device_id] = deque(maxlen=self._buffer_size)
        return state

    def update(self, device_id: str, **fields) -> DeviceState:
        state = self.get_or_create(device_id)
        for key, value in fields.items():
            setattr(state, key, value)
        state.updated_at = _now()
        return state

    def record_event(self, event: Event) -> None:
        self.get_or_create(event.device_id)
        self._events[event.device_id].append(event)

    def list_states(self) -> list[DeviceState]:
        return list(self._states.values())

    def get_state(self, device_id: str) -> DeviceState | None:
        return self._states.get(device_id)

    def list_events(self, device_id: str, limit: int = 50) -> list[Event]:
        events = self._events.get(device_id)
        if not events:
            return []
        return list(events)[-limit:]


store = DeviceStore(buffer_size=settings.event_buffer_size)

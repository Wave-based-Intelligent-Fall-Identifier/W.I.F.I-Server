"""디바이스 조회 + 명령 발행 REST API."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.bridge import bridge
from backend.store import DeviceState, Event, store

router = APIRouter(prefix="/devices", tags=["devices"])


class NetworkUpdate(BaseModel):
    wifi_id: str
    passwd: str
    apply: bool = True  # True 면 입력 후 적용(NEWNETWORKEDIT) 명령까지 전송


@router.get("", response_model=list[DeviceState])
def list_devices() -> list[DeviceState]:
    return store.list_states()


@router.get("/{device_id}", response_model=DeviceState)
def get_device(device_id: str) -> DeviceState:
    state = store.get_state(device_id)
    if state is None:
        raise HTTPException(status_code=404, detail="device not found")
    return state


@router.get("/{device_id}/events", response_model=list[Event])
def get_events(device_id: str, limit: int = 50) -> list[Event]:
    return store.list_events(device_id, limit=limit)


@router.post("/{device_id}/baseline")
async def trigger_baseline(device_id: str) -> dict:
    await bridge.send_baseline(device_id)
    return {"ok": True, "command": "BASELINE", "device_id": device_id}


@router.post("/{device_id}/network")
async def set_network(device_id: str, body: NetworkUpdate) -> dict:
    await bridge.send_network(device_id, body.wifi_id, body.passwd)
    if body.apply:
        await bridge.send_network_apply(device_id)
    return {"ok": True, "device_id": device_id, "applied": body.apply}

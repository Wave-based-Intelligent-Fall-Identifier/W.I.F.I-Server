"""WIFY MQTT 토픽 정의 및 파싱 유틸.

토픽 형식: {prefix}/{device_id}/{suffix}
suffix 는 여러 단계일 수 있음 (예: nownetwork/status, edit/nownetwork).
"""

from backend.config import settings

PREFIX = settings.topic_prefix

# --- ESP32 -> Broker -> Server (서버가 구독) ---
SUB_STATUS = "status"                       # "online" / "offline"
SUB_HEARTBEAT = "heartbeat"                 # heartbeat payload
SUB_RESTROOM = "restroom"                   # ACT / DEACT / LOAD (PIR)
SUB_NOWNETWORK = "nownetwork"              # 현재 네트워크 id/passwd
SUB_NOWNETWORK_STATUS = "nownetwork/status" # "connect" / "disconnect"
SUB_AI = "AI"                               # DAN / NOR / WARN

# --- Server -> Broker -> ESP32 (서버가 발행) ---
SUB_BASELINE = "baseline"                   # "BASELINE" (baseline 재구축 명령)
SUB_EDIT_NETWORK = "edit/nownetwork"        # "id:%s/passwd:%s" (새 네트워크 입력)
SUB_EDIT_EDITNETWORK = "edit/editnetwork"   # "NEWNETWORKEDIT" (적용 명령)

# 서버가 구독할 토픽 (디바이스 전체 와일드카드)
SUBSCRIBE_PATTERN = f"{PREFIX}/+/#"

# 서버가 처리하는(인바운드) suffix 집합
INBOUND_SUFFIXES = {
    SUB_STATUS,
    SUB_HEARTBEAT,
    SUB_RESTROOM,
    SUB_NOWNETWORK,
    SUB_NOWNETWORK_STATUS,
    SUB_AI,
}


def device_topic(device_id: str, suffix: str) -> str:
    """디바이스 토픽 문자열 생성."""
    return f"{PREFIX}/{device_id}/{suffix}"


def parse(topic: str) -> tuple[str | None, str | None]:
    """토픽에서 (device_id, suffix) 추출. prefix 불일치 시 (None, None)."""
    parts = topic.split("/")
    if len(parts) < 3 or parts[0] != PREFIX:
        return None, None
    device_id = parts[1]
    suffix = "/".join(parts[2:])
    return device_id, suffix

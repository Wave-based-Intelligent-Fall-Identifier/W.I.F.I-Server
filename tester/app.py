"""WIFY MQTT 테스터 (Flask).

Android 없이 브라우저에서:
- 브로커의 wify/# 토픽을 구독해 들어오는 메시지(RX) 로그 확인
- 서버 -> ESP 명령(baseline / 네트워크) 발행(TX)
- 보드가 없을 때 ESP -> 서버 메시지를 시뮬레이션 발행

브로커 주소는 프로젝트 루트 .env 의 MQTT_HOST / MQTT_PORT 를 재사용한다.
실행:  python tester/app.py   ->  http://localhost:5000
"""

import os
import threading
import time
from collections import deque
from pathlib import Path

import paho.mqtt.client as mqtt
from flask import Flask, jsonify, render_template, request


# --- 설정: 프로젝트 루트 .env 를 간단히 파싱해 브로커 주소 재사용 ---
def _load_env() -> dict:
    env: dict[str, str] = {}
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    return env


_env = _load_env()
MQTT_HOST = os.getenv("MQTT_HOST", _env.get("MQTT_HOST", "192.168.0.10"))
MQTT_PORT = int(os.getenv("MQTT_PORT", _env.get("MQTT_PORT", "1883")))
TOPIC_PREFIX = os.getenv("TOPIC_PREFIX", _env.get("TOPIC_PREFIX", "wify"))


# --- 메시지 로그 (스레드 안전) ---
_lock = threading.Lock()
_messages: deque[dict] = deque(maxlen=500)
_seq = 0
_state = {"connected": False}


def _log(direction: str, topic: str, payload: str) -> None:
    global _seq
    with _lock:
        _seq += 1
        _messages.append(
            {
                "id": _seq,
                "dir": direction,  # RX(수신) / TX(발행)
                "topic": topic,
                "payload": payload,
                "ts": time.strftime("%H:%M:%S"),
            }
        )


# --- MQTT 클라이언트 ---
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="wify-tester")


def _on_connect(c, userdata, flags, reason_code, properties=None):
    _state["connected"] = reason_code == 0
    c.subscribe(f"{TOPIC_PREFIX}/#")
    _log("SYS", f"{TOPIC_PREFIX}/#", f"connected to {MQTT_HOST}:{MQTT_PORT}, subscribed")


def _on_disconnect(c, userdata, *args):
    _state["connected"] = False
    _log("SYS", "-", "disconnected")


def _on_message(c, userdata, msg):
    try:
        payload = msg.payload.decode()
    except UnicodeDecodeError:
        payload = repr(msg.payload)
    _log("RX", msg.topic, payload)


client.on_connect = _on_connect
client.on_disconnect = _on_disconnect
client.on_message = _on_message


def _start_mqtt() -> None:
    try:
        client.connect_async(MQTT_HOST, MQTT_PORT, keepalive=60)
        client.loop_start()
    except Exception as exc:  # noqa: BLE001
        _log("SYS", "-", f"connect error: {exc}")


# --- Flask ---
app = Flask(__name__)


@app.get("/")
def index():
    return render_template(
        "index.html",
        broker=f"{MQTT_HOST}:{MQTT_PORT}",
        prefix=TOPIC_PREFIX,
    )


@app.get("/api/messages")
def api_messages():
    since = int(request.args.get("since", 0))
    with _lock:
        items = [m for m in _messages if m["id"] > since]
    return jsonify({"connected": _state["connected"], "messages": items})


@app.post("/api/publish")
def api_publish():
    data = request.get_json(force=True)
    topic = (data.get("topic") or "").strip()
    payload = data.get("payload", "")
    if not topic:
        return jsonify({"ok": False, "error": "topic required"}), 400
    result = client.publish(topic, str(payload), qos=1)
    _log("TX", topic, str(payload))
    return jsonify({"ok": result.rc == mqtt.MQTT_ERR_SUCCESS})


if __name__ == "__main__":
    _start_mqtt()
    # reloader 켜면 MQTT 스레드가 두 번 떠서 끔
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)

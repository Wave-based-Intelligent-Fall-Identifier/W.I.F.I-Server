# W.I.F.I-Server

ESP32 ↔ Android 를 **MQTT** 로 중계하는 서버. 화장실 안전 모니터링(WIFY) 시스템의 백엔드.

```
ESP32  ──pub/sub──►  Mosquitto Broker  ◄──pub/sub──  Android
                          ▲   │
                          │   ▼
                    [ FastAPI Server ]
              상태 저장 · 이력 · REST/WebSocket API · 명령 중계
```

ESP/Android 모두 MQTT 클라이언트이고, 서버는 그 사이에서
`ESP → Broker → Server → Broker → Android` 흐름을 처리한다.

## 구성

- **FastAPI** — REST API + WebSocket (실시간 푸시)
- **aiomqtt** — Mosquitto 브로커 상시 연결(구독/발행)
- **Mosquitto** — MQTT 브로커 (Docker)
- 저장소: 인메모리(MVP). 추후 SQLite / Supabase / Firebase 교체 용이하게 분리됨.

## 실행

### 1) 브로커 (Mosquitto)
```bash
docker compose up -d mosquitto
```
- MQTT: `1883`, WebSocket: `9001` (Android/웹에서 직접 구독 시)
- 개발용은 익명 접속 허용. 운영 전 `mosquitto/config/mosquitto.conf` 에서 인증 적용 필수.

### 2) 서버
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # 브로커 주소 등 설정
python -m app.main
```
- API 문서: http://localhost:8000/docs
- 헬스체크: http://localhost:8000/health

## 토픽 설계

### ESP32 → Broker → Server (서버 구독)
| Topic | 의미 | Payload |
| --- | --- | --- |
| `wify/{device}/status` | 기기 상태 | `online` / `offline` |
| `wify/{device}/heartbeat` | 작동 heartbeat | (payload) |
| `wify/{device}/restroom` | PIR 사람 감지 | `ACT` / `DEACT` / `LOAD` |
| `wify/{device}/nownetwork` | 현재 네트워크 정보 | id/passwd |
| `wify/{device}/nownetwork/status` | 네트워크 연결 상태 | `connect` / `disconnect` |
| `wify/{device}/AI` | AI 판단 | `DAN` / `NOR` / `WARN` |

### Server → Broker → ESP32 (서버 발행)
| Topic | 의미 | Payload |
| --- | --- | --- |
| `wify/{device}/baseline` | Baseline 재구축 명령 | `BASELINE` |
| `wify/{device}/edit/nownetwork` | 새 네트워크 입력 | `id:%s/passwd:%s` |
| `wify/{device}/edit/editnetwork` | 새 네트워크 적용 | `NEWNETWORKEDIT` |

> 서버는 `wify/+/#` 를 구독하고 토픽 suffix 로 라우팅한다.

## REST API
| Method | Path | 설명 |
| --- | --- | --- |
| GET | `/health` | 서버/브로커 연결 상태 |
| GET | `/devices` | 전체 디바이스 최신 상태 |
| GET | `/devices/{id}` | 단일 디바이스 상태 |
| GET | `/devices/{id}/events?limit=50` | 최근 수신 이벤트 |
| POST | `/devices/{id}/baseline` | Baseline 재구축 명령 발행 |
| POST | `/devices/{id}/network` | 새 네트워크 입력(+적용) 발행 |

`POST /devices/{id}/network` body:
```json
{ "wifi_id": "myssid", "passwd": "pw1234", "apply": true }
```

## WebSocket
`ws://localhost:8000/ws` — 접속하면 모든 디바이스의 인바운드 이벤트를 실시간 수신:
```json
{ "device_id": "device01", "suffix": "AI", "payload": "DAN" }
```

## 디렉터리 구조
```
app/
  main.py        # FastAPI 진입점, lifespan, WebSocket
  config.py      # 환경설정(.env)
  topics.py      # 토픽 정의/파싱
  bridge.py      # MQTT 브릿지(구독/발행/디스패치)
  store.py       # 인메모리 상태/이벤트 저장소
  ws.py          # WebSocket 브로드캐스터
  api/devices.py # 디바이스 REST 라우터
mosquitto/       # 브로커 설정
docker-compose.yml
```

## 다음 단계 (TODO)
- [ ] 영속 저장소 연동 (SQLite → Supabase/Firestore)
- [ ] 위험(`DAN`) 감지 시 FCM 푸시 알림
- [ ] 인증/접근제어 (브로커 + API)
- [ ] heartbeat 타임아웃 기반 offline 자동 판정

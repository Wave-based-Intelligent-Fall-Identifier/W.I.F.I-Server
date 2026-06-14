from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """환경변수(.env)로 주입되는 서버 설정."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # MQTT broker (Mosquitto)
    mqtt_host: str = "127.0.0.1"
    mqtt_port: int = 1883
    mqtt_username: str | None = None
    mqtt_password: str | None = None
    mqtt_client_id: str = "wify-server"

    # 토픽 prefix (wify/{device}/...)
    topic_prefix: str = "wify"

    # HTTP 서버
    http_host: str = "0.0.0.0"
    http_port: int = 8000

    # 디바이스별 인메모리 이벤트 보관 개수
    event_buffer_size: int = 200


settings = Settings()

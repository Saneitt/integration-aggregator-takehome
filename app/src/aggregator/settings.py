from functools import lru_cache

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False, extra="ignore")

    openbao_addr: str
    openbao_mount: str = "oauthapp"
    openbao_auth_method: str = "kubernetes"
    openbao_k8s_auth_path: str = "kubernetes"
    openbao_k8s_role: str = "integration-aggregator"
    openbao_k8s_token_file: str = "/var/run/secrets/openbao/token"
    openbao_token: SecretStr | None = None
    openbao_timeout_seconds: float = 5
    callback_url: str
    worker_concurrency: int = 16
    queue_max_size: int = 1000
    request_ttl_seconds: int = 300
    state_ttl_seconds: int = 600
    max_pending_states: int = 10_000
    log_level: str = "INFO"

    @model_validator(mode="after")
    def validate_runtime_settings(self) -> "Settings":
        if self.openbao_auth_method not in {"kubernetes", "token"}:
            raise ValueError("OPENBAO_AUTH_METHOD must be kubernetes or token")
        if self.openbao_auth_method == "token" and self.openbao_token is None:
            raise ValueError("OPENBAO_TOKEN is required when auth method is token")
        for key in (
            "worker_concurrency",
            "queue_max_size",
            "request_ttl_seconds",
            "state_ttl_seconds",
            "max_pending_states",
        ):
            if getattr(self, key) <= 0:
                raise ValueError(f"{key} must be positive")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

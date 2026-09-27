from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

from aggregator.validation import DEFAULT_SCOPES, PROVIDER_TYPES, scopes_valid


class ProviderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    provider: str
    client_id: str = Field(min_length=1, max_length=256)
    client_secret: SecretStr = Field(min_length=1, max_length=512)
    scopes: list[str] | None = None
    provider_options: dict[str, str] = Field(default_factory=dict)

    @field_validator("provider")
    @classmethod
    def provider_type_known(cls, value: str) -> str:
        if value not in PROVIDER_TYPES:
            raise ValueError("Unsupported provider type.")
        return value

    @field_validator("scopes")
    @classmethod
    def scope_tokens_valid(cls, value: list[str] | None) -> list[str] | None:
        if value is not None and not scopes_valid(value):
            raise ValueError("Scopes must contain at most 20 valid OAuth scope tokens.")
        return value

    @model_validator(mode="after")
    def options_valid(self) -> "ProviderCreate":
        if (
            self.provider == "custom"
            and not {"auth_code_url", "token_url"} <= self.provider_options.keys()
        ):
            raise ValueError("Custom providers require auth_code_url and token_url.")
        if self.provider == "oidc" and "issuer_url" not in self.provider_options:
            raise ValueError("OIDC providers require issuer_url.")
        return self

    def effective_scopes(self) -> list[str]:
        return self.scopes if self.scopes is not None else DEFAULT_SCOPES[self.provider]


class ProviderResponse(BaseModel):
    name: str
    provider: str
    scopes: list[str]


class ConnectResponse(BaseModel):
    provider: str
    user: str
    auth_url: str
    state: str
    expires_in: int


class TokenResult(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_at: str | None = None


class RequestResponse(BaseModel):
    request_id: str
    status: Literal["pending", "running", "succeeded", "failed"]
    provider: str | None = None
    user: str | None = None
    token: TokenResult | None = None
    error: dict[str, str] | None = None

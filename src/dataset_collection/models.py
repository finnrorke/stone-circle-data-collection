from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SourceType = Literal["download", "wfs", "api", "manual"]
SourceFormat = Literal["zip", "geojson", "json", "csv", "xml", "gml", "html", "unknown"]
HttpMethod = Literal["GET", "POST"]


class SourceDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    type: SourceType
    format: SourceFormat
    url: str = ""
    enabled: bool
    method: HttpMethod = "GET"
    headers: dict[str, str] = Field(default_factory=dict)
    params: dict[str, str] = Field(default_factory=dict)
    filename: str | None = None
    timeout: int = 60
    notes: str | None = None

    @field_validator("id", "name")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be empty")
        return value

    @field_validator("url")
    @classmethod
    def normalize_url(cls, value: str) -> str:
        return value.strip()

    @field_validator("timeout")
    @classmethod
    def validate_timeout(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("timeout must be greater than zero")
        return value

    @model_validator(mode="after")
    def validate_url_rules(self) -> SourceDefinition:
        if self.type == "manual":
            return self
        if self.enabled and not self.url:
            raise ValueError("enabled non-manual sources must define a non-empty url")
        return self

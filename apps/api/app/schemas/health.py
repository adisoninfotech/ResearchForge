"""Health check schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class LiveResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str


class ReadyComponent(BaseModel):
    name: str
    status: Literal["ok", "error"]


class ReadyResponse(BaseModel):
    status: Literal["ok", "degraded", "error"]
    components: list[ReadyComponent]

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class ComponentStatus(str, Enum):
    alive = "alive"
    dead = "dead"
    disabled = "disabled"
    unknown = "unknown"


class ComponentCredential(BaseModel):
    label: str
    value: str


class ServiceComponentItem(BaseModel):
    id: str
    name: str
    service_type: str
    host: str
    port: int
    status: ComponentStatus
    message: str | None = None
    response_time_ms: float | None = None
    exposed: bool = False
    external_port: int | None = None
    visit_port: int | None = None
    visit_path: str | None = None
    visit_label: str | None = None
    credentials: list[ComponentCredential] = Field(default_factory=list)


class ServiceComponentsStatusResponse(BaseModel):
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    items: list[ServiceComponentItem]

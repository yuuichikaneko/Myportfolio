from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel, Field


class UsageType(str, Enum):
    GAMING = "gaming"
    VIDEO_EDITING = "video_editing"
    GENERAL = "general"


class GenerateConfigRequest(BaseModel):
    budget: int = Field(..., ge=50000, le=500000)
    usage: UsageType


class PartResponse(BaseModel):
    category: str
    name: str
    price: int
    url: str


class GenerateConfigResponse(BaseModel):
    usage: UsageType
    budget: int
    total_price: int
    estimated_power_w: int
    parts: list[PartResponse]


@dataclass(frozen=True)
class Part:
    id: str
    category: str
    name: str
    price: int
    performance_score: float
    url: str
    socket: str | None = None
    memory_standard: str | None = None
    memory_capacity_gb: int | None = None
    storage_capacity_gb: int | None = None
    wattage: int | None = None
    form_factor: str | None = None
    supported_form_factors: tuple[str, ...] = ()

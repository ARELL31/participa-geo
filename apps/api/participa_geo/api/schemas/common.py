"""Shared response schemas: :class:`DatasetMeta` and the generic :class:`Page`."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, Field

T = TypeVar("T")


class DatasetMeta(BaseModel):
    """Versions, reference date and filters that identify a dataset snapshot."""

    dataset_version_ids: list[UUID] = Field(default_factory=list)
    reference_date: str = "2025-12-15"
    model_run_id: UUID | None = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    geographic_warning: str = ""
    filters: dict = Field(default_factory=dict)


class Page(BaseModel, Generic[T]):  # noqa: UP046 - pydantic-compatible Generic alias
    """The paginated envelope returned by every list endpoint."""

    items: list[T]
    page: int
    page_size: int
    total: int
    meta: DatasetMeta


__all__ = ["DatasetMeta", "Page"]

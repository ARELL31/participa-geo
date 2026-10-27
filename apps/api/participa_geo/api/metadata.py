"""Response metadata: the :class:`DatasetMeta` envelope carried by every list."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from participa_geo.api.schemas.common import DatasetMeta

REFERENCE_DATE = "2025-12-15"


def build_meta(
    *,
    dataset_version_ids: list[UUID] | None = None,
    reference_date: str = REFERENCE_DATE,
    model_run_id: UUID | None = None,
    generated_at: datetime | None = None,
    geographic_warning: str = "",
    filters: dict[str, Any] | None = None,
) -> DatasetMeta:
    """Build a :class:`DatasetMeta` with the current UTC timestamp by default."""
    return DatasetMeta(
        dataset_version_ids=dataset_version_ids or [],
        reference_date=reference_date,
        model_run_id=model_run_id,
        generated_at=generated_at or datetime.now(timezone.utc),
        geographic_warning=geographic_warning,
        filters=filters or {},
    )


__all__ = ["DatasetMeta", "REFERENCE_DATE", "build_meta"]

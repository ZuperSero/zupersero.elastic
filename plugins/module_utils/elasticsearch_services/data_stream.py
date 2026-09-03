# Copyright (c) 2026, zupersero
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Services and comparison helpers for Elasticsearch data streams."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any, Mapping

if TYPE_CHECKING:
    from ..elasticsearch import ElasticsearchClient, ElasticsearchResponse

from ..elasticsearch import compare_objects, quote_resource_path

_LIFECYCLE_WRITABLE_FIELDS = frozenset(
    ("data_retention", "downsampling", "enabled")
)


class DataStreamService:
    """Manage Elasticsearch data stream existence."""

    resource_path = "_data_stream"

    def __init__(self, client: ElasticsearchClient) -> None:
        self.client = client

    @classmethod
    def path(cls, name: str) -> str:
        """Return the URL-quoted data stream resource path."""
        return quote_resource_path(f"{cls.resource_path}/{{id}}", name)

    def get(self, name: str) -> tuple[ElasticsearchResponse, dict[str, Any] | None]:
        """Read and unwrap an exact named data stream."""
        response = self.client.request(self.path(name))
        current = None
        if response.status == 200 and isinstance(response.data, Mapping):
            candidates = response.data.get("data_streams")
            if isinstance(candidates, list):
                for candidate in candidates:
                    if (
                        isinstance(candidate, Mapping)
                        and candidate.get("name") == name
                    ):
                        current = copy.deepcopy(dict(candidate))
                        break
        return response, current

    def create(self, name: str) -> ElasticsearchResponse:
        """Create a data stream from its matching composable template."""
        return self.client.request(self.path(name), method="PUT")

    def delete(self, name: str) -> ElasticsearchResponse:
        """Delete a data stream and its backing indices."""
        return self.client.request(self.path(name), method="DELETE")


def _writable_lifecycle(resource: Mapping[str, Any]) -> dict[str, Any]:
    """Project a lifecycle response onto fields accepted by Stack 9.2 PUT."""
    return {
        key: copy.deepcopy(value)
        for key, value in resource.items()
        if key in _LIFECYCLE_WRITABLE_FIELDS
    }


def _normalize_replacement_lifecycle(
    resource: Mapping[str, Any],
) -> dict[str, Any]:
    """Normalize materialized defaults and server-cleared empty values."""
    normalized = _writable_lifecycle(resource)
    if normalized.get("enabled") is True:
        normalized.pop("enabled")
    if normalized.get("downsampling") == []:
        normalized.pop("downsampling")
    return normalized


class DataStreamLifecycleService:
    """Manage lifecycle attachment on an existing data stream."""

    resource_path = "_data_stream"

    def __init__(self, client: ElasticsearchClient) -> None:
        self.client = client

    @classmethod
    def path(cls, name: str) -> str:
        """Return the URL-quoted data stream lifecycle resource path."""
        stream_path = quote_resource_path(f"{cls.resource_path}/{{id}}", name)
        return f"{stream_path}/_lifecycle"

    def get(
        self,
        name: str,
    ) -> tuple[
        ElasticsearchResponse,
        bool,
        dict[str, Any] | None,
        dict[str, Any],
    ]:
        """Read one stream lifecycle and normalize the response envelope."""
        response = self.client.request(self.path(name))
        stream_exists = False
        current = None
        global_retention: dict[str, Any] = {}
        if response.status == 200 and isinstance(response.data, Mapping):
            retention = response.data.get("global_retention")
            if isinstance(retention, Mapping):
                global_retention = copy.deepcopy(dict(retention))
            candidates = response.data.get("data_streams")
            if isinstance(candidates, list):
                for candidate in candidates:
                    if (
                        isinstance(candidate, Mapping)
                        and candidate.get("name") == name
                    ):
                        stream_exists = True
                        lifecycle = candidate.get("lifecycle")
                        if isinstance(lifecycle, Mapping):
                            current = copy.deepcopy(dict(lifecycle))
                            current["name"] = name
                        break
        return response, stream_exists, current, global_retention

    @staticmethod
    def compare(
        current: Mapping[str, Any],
        desired: Mapping[str, Any],
        *,
        replace: bool = False,
    ) -> tuple[bool, dict[str, Any]]:
        """Compare typed lifecycle state, ignoring derived retention fields."""
        if replace:
            current_normalized = _normalize_replacement_lifecycle(current)
            desired_normalized = _normalize_replacement_lifecycle(desired)
            return compare_objects(
                current_normalized,
                desired_normalized,
                compare_fields=sorted(
                    set(current_normalized) | set(desired_normalized)
                ),
            )

        desired_writable = _writable_lifecycle(desired)
        current_writable = _writable_lifecycle(current)
        if desired_writable.get("downsampling") == []:
            current_writable.setdefault("downsampling", [])
        return compare_objects(current_writable, desired_writable)

    @staticmethod
    def payload(
        current: Mapping[str, Any] | None,
        desired: Mapping[str, Any],
        *,
        replace: bool = False,
    ) -> dict[str, Any]:
        """Build a lifecycle body with optional preservation of omitted fields."""
        desired_writable = _writable_lifecycle(desired)
        if replace or current is None:
            payload = desired_writable
        else:
            payload = _writable_lifecycle(current)
            payload.update(desired_writable)
        if desired_writable.get("downsampling") == []:
            payload.pop("downsampling", None)
        return payload

    def create_or_update(
        self,
        name: str,
        *,
        current: Mapping[str, Any] | None,
        desired: Mapping[str, Any],
        replace: bool = False,
    ) -> ElasticsearchResponse:
        """Create or update a data stream lifecycle attachment."""
        return self.client.request(
            self.path(name),
            method="PUT",
            data=self.payload(current, desired, replace=replace),
        )

    def delete(self, name: str) -> ElasticsearchResponse:
        """Detach lifecycle management without deleting the data stream."""
        return self.client.request(self.path(name), method="DELETE")

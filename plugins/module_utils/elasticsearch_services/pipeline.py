# Copyright (c) 2026, zupersero
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Service and comparison helpers for Elasticsearch ingest pipelines."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any, Mapping

if TYPE_CHECKING:
    from ..elasticsearch import ElasticsearchClient, ElasticsearchResponse

from ..elasticsearch import compare_objects, quote_resource_path

_READ_ONLY_FIELDS = frozenset(("name", "created_date_millis", "modified_date_millis"))


def _deep_merge(current: Mapping[str, Any], desired: Mapping[str, Any]) -> dict[str, Any]:
    """Recursively merge desired pipeline fields without dropping state."""
    merged = copy.deepcopy(dict(current))
    for key, value in desired.items():
        current_value = merged.get(key)
        if isinstance(current_value, Mapping) and isinstance(value, Mapping):
            merged[key] = _deep_merge(current_value, value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _writable_pipeline(resource: Mapping[str, Any]) -> dict[str, Any]:
    """Remove the pipeline identity before sending a request body."""
    return {
        key: copy.deepcopy(value)
        for key, value in resource.items()
        if key not in _READ_ONLY_FIELDS
    }


class PipelineService:
    """Manage named Elasticsearch ingest pipelines."""

    resource_path = "_ingest/pipeline"

    def __init__(self, client: ElasticsearchClient) -> None:
        self.client = client

    @classmethod
    def path(cls, name: str) -> str:
        """Return the URL-quoted ingest pipeline path."""
        return quote_resource_path(f"{cls.resource_path}/{{id}}", name)

    def get(self, name: str) -> tuple[ElasticsearchResponse, dict[str, Any] | None]:
        """Read and unwrap an exact named ingest pipeline."""
        response = self.client.request(self.path(name))
        current = None
        if response.status == 200 and isinstance(response.data, Mapping):
            candidate = response.data.get(name)
            if isinstance(candidate, Mapping):
                current = copy.deepcopy(dict(candidate))
                current["name"] = name
        return response, current

    @staticmethod
    def compare(
        current: Mapping[str, Any],
        desired: Mapping[str, Any],
        *,
        replace: bool = False,
    ) -> tuple[bool, dict[str, Any]]:
        """Compare pipeline fields while ignoring unknown server fields by default."""
        if replace:
            current_fields = _writable_pipeline(current)
            desired_fields = _writable_pipeline(desired)
            return compare_objects(
                current_fields,
                desired_fields,
                compare_fields=sorted(set(current_fields) | set(desired_fields)),
            )
        return compare_objects(_writable_pipeline(current), _writable_pipeline(desired))

    @staticmethod
    def payload(
        current: Mapping[str, Any] | None,
        desired: Mapping[str, Any],
        *,
        replace: bool = False,
    ) -> dict[str, Any]:
        """Build a pipeline body, preserving omitted fields unless replacing."""
        desired_fields = _writable_pipeline(desired)
        if replace or current is None:
            return desired_fields
        return _deep_merge(_writable_pipeline(current), desired_fields)

    def create_or_update(
        self,
        name: str,
        *,
        current: Mapping[str, Any] | None,
        desired: Mapping[str, Any],
        replace: bool = False,
    ) -> ElasticsearchResponse:
        """Create or update an ingest pipeline."""
        return self.client.request(
            self.path(name),
            method="PUT",
            data=self.payload(current, desired, replace=replace),
        )

    def delete(self, name: str) -> ElasticsearchResponse:
        """Delete a named ingest pipeline."""
        return self.client.request(self.path(name), method="DELETE")

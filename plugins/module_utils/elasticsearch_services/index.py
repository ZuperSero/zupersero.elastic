# Copyright (c) 2026, zupersero
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Service and comparison helpers for Elasticsearch indices."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping

if TYPE_CHECKING:
    from ..elasticsearch import ElasticsearchClient, ElasticsearchResponse

from ..elasticsearch import compare_objects, quote_resource_path


def flatten_index_settings(
    settings: Mapping[str, Any],
    prefix: str = "",
) -> dict[str, Any]:
    """Flatten settings and remove the optional leading ``index`` namespace."""
    flattened: dict[str, Any] = {}
    for key, value in settings.items():
        key_parts = [part for part in str(key).split(".") if part]
        path_parts = [part for part in prefix.split(".") if part]
        parts = [*path_parts, *key_parts]
        if parts and parts[0] == "index":
            parts = parts[1:]
        path = ".".join(parts)
        if isinstance(value, Mapping):
            flattened.update(flatten_index_settings(value, path))
        elif path:
            flattened[path] = value
    return flattened


def _normalize_setting_value(value: Any) -> Any:
    """Match Elasticsearch's string representation of scalar settings."""
    if value is None:
        return None
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return [_normalize_setting_value(item) for item in value]
    return value


def normalize_index_settings(settings: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return canonical flat settings suitable for idempotent comparison."""
    return {
        key: _normalize_setting_value(value)
        for key, value in flatten_index_settings(settings or {}).items()
    }


class IndexService:
    """Manage Elasticsearch index API operations and domain comparisons."""

    def __init__(self, client: ElasticsearchClient) -> None:
        self.client = client

    @staticmethod
    def path(name: str) -> str:
        """Return a URL-quoted index resource path."""
        return quote_resource_path("{id}", name)

    @classmethod
    def settings_path(cls, name: str) -> str:
        """Return the update-settings API path for an index."""
        return f"{cls.path(name)}/_settings"

    @classmethod
    def mapping_path(cls, name: str) -> str:
        """Return the update-mapping API path for an index."""
        return f"{cls.path(name)}/_mapping"

    def get(self, name: str) -> tuple[ElasticsearchResponse, dict[str, Any] | None]:
        """Read an index and unwrap the name-keyed API response."""
        response = self.client.request(self.path(name))
        index = None
        if response.status == 200 and isinstance(response.data, Mapping):
            candidate = response.data.get(name)
            if isinstance(candidate, Mapping):
                index = dict(candidate)
                index["name"] = name
        return response, index

    def create(
        self,
        name: str,
        *,
        settings: Mapping[str, Any] | None = None,
        mappings: Mapping[str, Any] | None = None,
    ) -> ElasticsearchResponse:
        """Create an index with the requested settings and mappings."""
        payload: dict[str, Any] = {}
        if settings is not None:
            payload["settings"] = dict(settings)
        if mappings is not None:
            payload["mappings"] = dict(mappings)
        return self.client.request(
            self.path(name),
            method="PUT",
            data=payload,
        )

    def compare_settings(
        self,
        current: Mapping[str, Any] | None,
        desired: Mapping[str, Any],
    ) -> tuple[bool, dict[str, Any], dict[str, Any]]:
        """Compare settings and build a payload containing only changed keys."""
        current_normalized = normalize_index_settings(current)
        desired_values = flatten_index_settings(desired)
        desired_normalized = {
            key: _normalize_setting_value(value)
            for key, value in desired_values.items()
        }
        changed, diff = compare_objects(current_normalized, desired_normalized)
        update_payload = {
            f"index.{key}": desired_values[key]
            for key in desired_values
            if current_normalized.get(key) != desired_normalized[key]
        }
        return changed, diff, update_payload

    @staticmethod
    def compare_mappings(
        current: Mapping[str, Any] | None,
        desired: Mapping[str, Any],
    ) -> tuple[bool, dict[str, Any]]:
        """Compare only user-supplied mapping fields."""
        return compare_objects(current or {}, desired)

    def update_settings(
        self,
        name: str,
        settings: Mapping[str, Any],
    ) -> ElasticsearchResponse:
        """Update dynamic index settings."""
        return self.client.request(
            self.settings_path(name),
            method="PUT",
            data={"settings": dict(settings)},
        )

    def update_mapping(
        self,
        name: str,
        mappings: Mapping[str, Any],
    ) -> ElasticsearchResponse:
        """Merge a mapping update into an existing index."""
        return self.client.request(
            self.mapping_path(name),
            method="PUT",
            data=dict(mappings),
        )

    def delete(self, name: str) -> ElasticsearchResponse:
        """Delete an index."""
        return self.client.request(self.path(name), method="DELETE")

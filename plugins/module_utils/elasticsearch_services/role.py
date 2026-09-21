# Copyright (c) 2026, zupersero
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Service and comparison helpers for Elasticsearch security roles."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping

if TYPE_CHECKING:
    from ..elasticsearch import ElasticsearchClient, ElasticsearchResponse

from ..elasticsearch import compare_objects, quote_resource_path


def _normalize_index_privilege(entry: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize one index privilege entry, tolerating the legacy 'index' alias."""
    cleaned = {key: value for key, value in entry.items() if value is not None}
    if "names" not in cleaned and "index" in cleaned:
        cleaned["names"] = cleaned.pop("index")
    else:
        cleaned.pop("index", None)
    if "allow_restricted_indices" in cleaned:
        cleaned["allow_restricted_indices"] = bool(cleaned["allow_restricted_indices"])
    return cleaned


def _normalize_application_privilege(entry: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize one application privilege entry."""
    return {key: value for key, value in entry.items() if value is not None}


def _writable_role(resource: Mapping[str, Any]) -> dict[str, Any]:
    """Project a role response onto its comparable, writable fields."""
    role: dict[str, Any] = {
        "cluster": list(resource.get("cluster") or []),
        "indices": [
            _normalize_index_privilege(entry) for entry in (resource.get("indices") or [])
        ],
        "applications": [
            _normalize_application_privilege(entry)
            for entry in (resource.get("applications") or [])
        ],
        "run_as": list(resource.get("run_as") or resource.get("runAs") or []),
        "metadata": resource.get("metadata") or {},
        "transient_metadata": (
            resource.get("transient_metadata")
            or resource.get("transientMetadata")
            or {"enabled": True}
        ),
    }
    if resource.get("global") is not None:
        role["global"] = resource["global"]
    return role


class RoleService:
    """Manage named Elasticsearch security roles."""

    resource_path = "_security/role"

    def __init__(self, client: ElasticsearchClient) -> None:
        self.client = client

    @classmethod
    def path(cls, name: str) -> str:
        """Return the URL-quoted role resource path."""
        return quote_resource_path(f"{cls.resource_path}/{{id}}", name)

    def get(self, name: str) -> tuple[ElasticsearchResponse, dict[str, Any] | None]:
        """Read and unwrap an exact named role."""
        response = self.client.request(self.path(name))
        current = None
        if response.status == 200 and isinstance(response.data, Mapping):
            role_data = response.data.get(name)
            if role_data is None and response.data:
                role_data = next(iter(response.data.values()), None)
            if isinstance(role_data, Mapping):
                current = dict(role_data)
                current["name"] = name
        return response, current

    @staticmethod
    def payload(
        current: Mapping[str, Any] | None,
        desired: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Shallow-merge explicitly supplied fields over the current role.

        Only fields present in ``desired`` (the fields a task actually set)
        override the current value; every other field is preserved as-is.
        """
        merged = dict(_writable_role(current if current is not None else {}))
        merged.update(desired)
        if "indices" in desired:
            merged["indices"] = [
                _normalize_index_privilege(entry) for entry in desired["indices"]
            ]
        if "applications" in desired:
            merged["applications"] = [
                _normalize_application_privilege(entry) for entry in desired["applications"]
            ]
        return merged

    @classmethod
    def compare(
        cls,
        current: Mapping[str, Any],
        desired: Mapping[str, Any],
    ) -> tuple[bool, dict[str, Any]]:
        """Compare the current role against explicitly supplied desired fields."""
        return compare_objects(
            _writable_role(current),
            cls.payload(current, desired),
            unordered_lists=True,
        )

    def create_or_update(
        self,
        name: str,
        *,
        current: Mapping[str, Any] | None,
        desired: Mapping[str, Any],
    ) -> ElasticsearchResponse:
        """Create or update a role with a preservation-aware payload."""
        return self.client.request(
            self.path(name),
            method="PUT",
            data=self.payload(current, desired),
        )

    def delete(self, name: str) -> ElasticsearchResponse:
        """Delete a role."""
        return self.client.request(self.path(name), method="DELETE")

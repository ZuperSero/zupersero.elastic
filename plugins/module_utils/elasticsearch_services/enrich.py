# Copyright (c) 2026, zupersero
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Service and comparison helpers for Elasticsearch enrich policies."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any, Mapping

if TYPE_CHECKING:
    from ..elasticsearch import ElasticsearchClient, ElasticsearchResponse

from ..elasticsearch import compare_objects, quote_resource_path

ENRICH_POLICY_TYPES = frozenset(("match", "range", "geo_match"))
_CANONICAL_FIELDS = frozenset(
    ("name", "policy_type", "source_indices", "match_field", "enrich_fields")
)


def _deep_merge(
    current: Mapping[str, Any],
    desired: Mapping[str, Any],
) -> dict[str, Any]:
    """Recursively merge desired fields without dropping omitted state."""
    merged = copy.deepcopy(dict(current))
    for key, value in desired.items():
        current_value = merged.get(key)
        if isinstance(current_value, Mapping) and isinstance(value, Mapping):
            merged[key] = _deep_merge(current_value, value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _writable_policy(resource: Mapping[str, Any]) -> dict[str, Any]:
    """Return the canonical policy fields without its resource identity."""
    return {
        key: copy.deepcopy(value)
        for key, value in resource.items()
        if key != "name"
    }


def validate_enrich_policy(
    policy_type: Any,
    source_indices: Any,
    match_field: Any,
    enrich_fields: Any,
) -> None:
    """Validate the stable top-level enrich policy envelope."""
    if policy_type is not None and policy_type not in ENRICH_POLICY_TYPES:
        raise ValueError(
            "policy_type must be one of: " + ", ".join(sorted(ENRICH_POLICY_TYPES))
        )
    if source_indices is not None and (
        not isinstance(source_indices, list)
        or not source_indices
        or any(not isinstance(item, str) or not item.strip() for item in source_indices)
    ):
        raise ValueError("source_indices must be a non-empty list of strings")
    if match_field is not None and (
        not isinstance(match_field, str) or not match_field.strip()
    ):
        raise ValueError("match_field must be a non-empty string")
    if enrich_fields is not None and (
        not isinstance(enrich_fields, list)
        or not enrich_fields
        or any(not isinstance(item, str) or not item.strip() for item in enrich_fields)
    ):
        raise ValueError("enrich_fields must be a non-empty list of strings")


class EnrichPolicyService:
    """Manage named Elasticsearch enrich policies."""

    resource_path = "_enrich/policy"

    def __init__(self, client: ElasticsearchClient) -> None:
        self.client = client

    @classmethod
    def path(cls, name: str) -> str:
        """Return the URL-quoted policy resource path."""
        return quote_resource_path(f"{cls.resource_path}/{{id}}", name)

    @classmethod
    def execute_path(cls, name: str) -> str:
        """Return the URL-quoted policy execution path."""
        return quote_resource_path(f"{cls.resource_path}/{{id}}/_execute", name)

    @staticmethod
    def _from_wire(
        name: str,
        body: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        """Normalize the type-keyed Elasticsearch response to module fields."""
        policy_type = next(
            (candidate for candidate in ENRICH_POLICY_TYPES if candidate in body),
            None,
        )
        if policy_type is None or not isinstance(body[policy_type], Mapping):
            return None
        policy = copy.deepcopy(dict(body[policy_type]))
        if "indices" in policy:
            policy["source_indices"] = policy.pop("indices")
        policy["name"] = name
        policy["policy_type"] = policy_type
        return policy

    @staticmethod
    def _to_wire(policy: Mapping[str, Any]) -> dict[str, Any]:
        """Convert canonical module fields to the type-keyed API body."""
        policy_type = policy.get("policy_type")
        if policy_type not in ENRICH_POLICY_TYPES:
            raise ValueError("policy_type is required and must be a supported type")
        body = {
            key: copy.deepcopy(value)
            for key, value in policy.items()
            if key not in _CANONICAL_FIELDS
        }
        if "source_indices" in policy:
            body["indices"] = copy.deepcopy(policy["source_indices"])
        for key in ("match_field", "enrich_fields"):
            if key in policy:
                body[key] = copy.deepcopy(policy[key])
        return {str(policy_type): body}

    def get(self, name: str) -> tuple[ElasticsearchResponse, dict[str, Any] | None]:
        """Read and unwrap an exact named enrich policy."""
        response = self.client.request(self.path(name))
        current = None
        if response.status == 200 and isinstance(response.data, Mapping):
            policies = response.data.get("policies")
            if isinstance(policies, list):
                if policies:
                    candidate = policies[0]
                    if isinstance(candidate, Mapping):
                        candidate = candidate.get("config", candidate)
                        if not isinstance(candidate, Mapping):
                            candidate = {}
                        current = self._from_wire(
                            str(candidate.get("name", name)), candidate
                        )
            else:
                current = self._from_wire(name, response.data)
        return response, current

    @staticmethod
    def compare(
        current: Mapping[str, Any],
        desired: Mapping[str, Any],
        *,
        replace: bool = False,
    ) -> tuple[bool, dict[str, Any]]:
        """Compare desired policy fields while preserving unknown server fields."""
        if replace:
            current_view = _writable_policy(current)
            desired_view = _writable_policy(desired)
            return compare_objects(
                current_view,
                desired_view,
                compare_fields=sorted(set(current_view) | set(desired_view)),
            )
        return compare_objects(_writable_policy(current), _writable_policy(desired))

    @classmethod
    def payload(
        cls,
        current: Mapping[str, Any] | None,
        desired: Mapping[str, Any],
        *,
        replace: bool = False,
    ) -> dict[str, Any]:
        """Build a type-keyed body, preserving omitted fields unless replacing."""
        desired_policy = _writable_policy(desired)
        if replace or current is None:
            return cls._to_wire(desired_policy)
        merged = _deep_merge(_writable_policy(current), desired_policy)
        return cls._to_wire(merged)

    def create_or_update(
        self,
        name: str,
        *,
        current: Mapping[str, Any] | None,
        desired: Mapping[str, Any],
        replace: bool = False,
    ) -> ElasticsearchResponse:
        """Create or update an enrich policy."""
        return self.client.request(
            self.path(name),
            method="PUT",
            data=self.payload(current, desired, replace=replace),
        )

    def delete(self, name: str) -> ElasticsearchResponse:
        """Delete an enrich policy."""
        return self.client.request(self.path(name), method="DELETE")

    def execute(self, name: str) -> ElasticsearchResponse:
        """Execute an enrich policy explicitly."""
        return self.client.request(self.execute_path(name), method="POST")

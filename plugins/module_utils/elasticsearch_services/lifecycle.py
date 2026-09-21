# Copyright (c) 2026, zupersero
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Service, validation, and comparison helpers for index lifecycle policies."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any, Mapping

if TYPE_CHECKING:
    from ..elasticsearch import ElasticsearchClient, ElasticsearchResponse

from ..elasticsearch import compare_objects, quote_resource_path

LIFECYCLE_PHASES = frozenset(("hot", "warm", "cold", "frozen", "delete"))
_PHASE_FIELDS = frozenset(("min_age", "actions"))
_READ_ONLY_FIELDS = frozenset(("in_use_by", "modified_date", "version"))


def _deep_merge(
    current: Mapping[str, Any],
    desired: Mapping[str, Any],
) -> dict[str, Any]:
    """Recursively merge desired policy fields without dropping omitted state."""
    merged = copy.deepcopy(dict(current))
    for key, value in desired.items():
        current_value = merged.get(key)
        if isinstance(current_value, Mapping) and isinstance(value, Mapping):
            merged[key] = _deep_merge(current_value, value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _writable_policy(resource: Mapping[str, Any]) -> dict[str, Any]:
    """Strip the resource identity and read-only policy response fields."""
    return {
        key: copy.deepcopy(value)
        for key, value in resource.items()
        if key != "name" and key not in _READ_ONLY_FIELDS
    }


def _normalize_replacement_policy(resource: Mapping[str, Any]) -> dict[str, Any]:
    """Remove known materialized API defaults from authoritative comparisons."""
    normalized = _writable_policy(resource)
    phases = normalized.get("phases")
    if not isinstance(phases, Mapping):
        return normalized

    normalized_phases = copy.deepcopy(dict(phases))
    for phase in normalized_phases.values():
        if not isinstance(phase, dict):
            continue
        if phase.get("min_age") == "0ms":
            phase.pop("min_age")
        actions = phase.get("actions")
        if not isinstance(actions, dict):
            continue
        delete = actions.get("delete")
        if (
            isinstance(delete, dict)
            and delete.get("delete_searchable_snapshot") is True
            and len(delete) == 1
        ):
            actions["delete"] = {}
        shrink = actions.get("shrink")
        if (
            isinstance(shrink, dict)
            and shrink.get("allow_write_after_shrink") is False
        ):
            shrink.pop("allow_write_after_shrink")
    normalized["phases"] = normalized_phases
    return normalized


def validate_lifecycle_phases(phases: Any) -> None:
    """Validate the stable ILM phase envelope while leaving action schemas to ES."""
    if not isinstance(phases, Mapping):
        raise ValueError("phases must be a dictionary")
    unknown_phases = sorted(
        (phase for phase in phases if phase not in LIFECYCLE_PHASES),
        key=str,
    )
    if unknown_phases:
        raise ValueError(
            "phases contains unsupported phase names: "
            + ", ".join(str(phase) for phase in unknown_phases)
        )
    for phase_name, phase in phases.items():
        if not isinstance(phase, Mapping):
            raise ValueError(f"phases.{phase_name} must be a dictionary")
        unknown_fields = sorted(
            (field for field in phase if field not in _PHASE_FIELDS),
            key=str,
        )
        if unknown_fields:
            raise ValueError(
                f"phases.{phase_name} contains unsupported fields: "
                + ", ".join(str(field) for field in unknown_fields)
            )
        min_age = phase.get("min_age")
        if min_age is not None and (
            not isinstance(min_age, str) or not min_age.strip()
        ):
            raise ValueError(f"phases.{phase_name}.min_age must be a non-empty string")
        actions = phase.get("actions")
        if actions is None:
            continue
        if not isinstance(actions, Mapping):
            raise ValueError(f"phases.{phase_name}.actions must be a dictionary")
        for action_name, action in actions.items():
            if not isinstance(action_name, str) or not action_name.strip():
                raise ValueError(
                    f"phases.{phase_name}.actions contains an empty action name"
                )
            if not isinstance(action, Mapping):
                raise ValueError(
                    f"phases.{phase_name}.actions.{action_name} "
                    "must be a dictionary"
                )


class LifecycleService:
    """Manage named Elasticsearch index lifecycle policies."""

    resource_path = "_ilm/policy"

    def __init__(self, client: ElasticsearchClient) -> None:
        self.client = client

    @classmethod
    def path(cls, name: str) -> str:
        """Return the URL-quoted lifecycle policy resource path."""
        return quote_resource_path(f"{cls.resource_path}/{{id}}", name)

    def get(self, name: str) -> tuple[ElasticsearchResponse, dict[str, Any] | None]:
        """Read and unwrap an exact named lifecycle policy."""
        response = self.client.request(self.path(name))
        current = None
        if response.status == 200 and isinstance(response.data, Mapping):
            candidate = response.data.get(name)
            if isinstance(candidate, Mapping) and isinstance(
                candidate.get("policy"), Mapping
            ):
                current = copy.deepcopy(dict(candidate["policy"]))
                current["name"] = name
                for field in _READ_ONLY_FIELDS:
                    if field in candidate:
                        current[field] = copy.deepcopy(candidate[field])
        return response, current

    @staticmethod
    def compare(
        current: Mapping[str, Any],
        desired: Mapping[str, Any],
        *,
        replace: bool = False,
    ) -> tuple[bool, dict[str, Any]]:
        """Compare desired policy state while ignoring runtime response fields."""
        if replace:
            current_normalized = _normalize_replacement_policy(current)
            desired_normalized = _normalize_replacement_policy(desired)
            return compare_objects(
                current_normalized,
                desired_normalized,
                compare_fields=sorted(
                    set(current_normalized) | set(desired_normalized)
                ),
            )
        return compare_objects(_writable_policy(current), _writable_policy(desired))

    @staticmethod
    def payload(
        current: Mapping[str, Any] | None,
        desired: Mapping[str, Any],
        *,
        replace: bool = False,
    ) -> dict[str, Any]:
        """Build the policy body, preserving omitted state unless replacing."""
        desired_policy = _writable_policy(desired)
        if replace or current is None:
            return desired_policy
        return _deep_merge(_writable_policy(current), desired_policy)

    def create_or_update(
        self,
        name: str,
        *,
        current: Mapping[str, Any] | None,
        desired: Mapping[str, Any],
        replace: bool = False,
    ) -> ElasticsearchResponse:
        """Create or replace an ILM policy with a preservation-aware body."""
        return self.client.request(
            self.path(name),
            method="PUT",
            data={"policy": self.payload(current, desired, replace=replace)},
        )

    def delete(self, name: str) -> ElasticsearchResponse:
        """Delete a named index lifecycle policy."""
        return self.client.request(self.path(name), method="DELETE")

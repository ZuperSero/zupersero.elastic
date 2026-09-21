# Copyright (c) 2026, zupersero
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Services and comparison helpers for composable Elasticsearch templates."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any, Mapping

if TYPE_CHECKING:
    from ..elasticsearch import ElasticsearchClient, ElasticsearchResponse

from ..elasticsearch import compare_objects, quote_resource_path
from .index import flatten_index_settings, normalize_index_settings

_READ_ONLY_FIELDS = frozenset(("created_date_millis", "modified_date_millis"))


def _deep_merge(
    current: Mapping[str, Any],
    desired: Mapping[str, Any],
) -> dict[str, Any]:
    """Recursively merge desired fields without dropping omitted current fields."""
    merged = copy.deepcopy(dict(current))
    for key, value in desired.items():
        current_value = merged.get(key)
        if isinstance(current_value, Mapping) and isinstance(value, Mapping):
            merged[key] = _deep_merge(current_value, value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _merge_settings(
    current: Mapping[str, Any],
    desired: Mapping[str, Any],
) -> dict[str, Any]:
    """Merge settings across nested and dotted forms without duplicate keys."""
    merged = flatten_index_settings(current)
    merged.update(flatten_index_settings(desired))
    return merged


def _merge_template(
    current: Mapping[str, Any],
    desired: Mapping[str, Any],
) -> dict[str, Any]:
    """Merge an index-template body, with canonical handling for settings."""
    merged = _deep_merge(current, desired)
    if "settings" in desired:
        current_settings = current.get("settings")
        desired_settings = desired.get("settings")
        if isinstance(current_settings, Mapping) and isinstance(desired_settings, Mapping):
            merged["settings"] = _merge_settings(current_settings, desired_settings)
    return merged


def normalize_template_resource(resource: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize settings while retaining all other template fields."""
    normalized = copy.deepcopy(dict(resource))
    template = normalized.get("template")
    if isinstance(template, Mapping):
        normalized_template = dict(template)
        settings = normalized_template.get("settings")
        if isinstance(settings, Mapping):
            normalized_template["settings"] = normalize_index_settings(settings)
        normalized["template"] = normalized_template
    return normalized


def normalize_replacement_resource(
    resource: Mapping[str, Any],
    *,
    keep_empty_template: bool = False,
) -> dict[str, Any]:
    """Normalize API defaults and empty clear values for full replacement."""
    normalized = normalize_template_resource(
        {
            key: value
            for key, value in resource.items()
            if key != "name" and key not in _READ_ONLY_FIELDS
        }
    )
    template = normalized.get("template")
    if isinstance(template, Mapping):
        normalized_template = {
            key: value
            for key, value in template.items()
            if value not in ({}, None)
        }
        if normalized_template or keep_empty_template:
            normalized["template"] = normalized_template
        else:
            normalized.pop("template", None)
    if normalized.get("_meta") in ({}, None):
        normalized.pop("_meta", None)
    for field in ("composed_of", "ignore_missing_component_templates"):
        if normalized.get(field) == []:
            normalized.pop(field)
    data_stream = normalized.get("data_stream")
    if isinstance(data_stream, Mapping):
        normalized["data_stream"] = {
            key: value
            for key, value in data_stream.items()
            if value is not False and value is not None
        }
    return normalized


class TemplateService:
    """Manage a named Elasticsearch composable-template API."""

    resource_path = ""
    response_collection = ""
    response_body = ""
    keep_empty_template = False

    def __init__(self, client: ElasticsearchClient) -> None:
        self.client = client

    @classmethod
    def path(cls, name: str) -> str:
        """Return the URL-quoted resource path."""
        return quote_resource_path(f"{cls.resource_path}/{{id}}", name)

    def get(self, name: str) -> tuple[ElasticsearchResponse, dict[str, Any] | None]:
        """Read and unwrap an exact named template from the list response."""
        response = self.client.request(self.path(name))
        current = None
        if response.status == 200 and isinstance(response.data, Mapping):
            candidates = response.data.get(self.response_collection)
            if isinstance(candidates, list):
                for candidate in candidates:
                    if (
                        isinstance(candidate, Mapping)
                        and candidate.get("name") == name
                        and isinstance(candidate.get(self.response_body), Mapping)
                    ):
                        current = dict(candidate[self.response_body])
                        current["name"] = name
                        break
        return response, current

    @classmethod
    def compare(
        cls,
        current: Mapping[str, Any],
        desired: Mapping[str, Any],
        *,
        replace: bool = False,
    ) -> tuple[bool, dict[str, Any]]:
        """Compare only user-supplied fields using canonical settings values."""
        if replace:
            current_normalized = normalize_replacement_resource(
                current,
                keep_empty_template=cls.keep_empty_template,
            )
            desired_normalized = normalize_replacement_resource(
                desired,
                keep_empty_template=cls.keep_empty_template,
            )
            return compare_objects(
                current_normalized,
                desired_normalized,
                compare_fields=sorted(
                    set(current_normalized) | set(desired_normalized)
                ),
            )
        return compare_objects(
            normalize_template_resource(current),
            normalize_template_resource(desired),
        )

    @staticmethod
    def payload(
        current: Mapping[str, Any] | None,
        desired: Mapping[str, Any],
        *,
        replace: bool = False,
    ) -> dict[str, Any]:
        """Build a replacement payload while retaining omitted writable fields."""
        current_payload = {
            key: value
            for key, value in (current or {}).items()
            if key != "name" and key not in _READ_ONLY_FIELDS
        }
        desired_payload = {
            key: value
            for key, value in desired.items()
            if key != "name" and key not in _READ_ONLY_FIELDS
        }
        if replace:
            return copy.deepcopy(desired_payload)
        payload = _deep_merge(current_payload, desired_payload)
        current_template = current_payload.get("template")
        desired_template = desired_payload.get("template")
        if isinstance(current_template, Mapping) and isinstance(desired_template, Mapping):
            payload["template"] = _merge_template(current_template, desired_template)
        return payload

    def create_or_update(
        self,
        name: str,
        *,
        current: Mapping[str, Any] | None,
        desired: Mapping[str, Any],
        replace: bool = False,
    ) -> ElasticsearchResponse:
        """Create or replace a template with a preservation-aware payload."""
        return self.client.request(
            self.path(name),
            method="PUT",
            data=self.payload(current, desired, replace=replace),
        )

    def delete(self, name: str) -> ElasticsearchResponse:
        """Delete a named template."""
        return self.client.request(self.path(name), method="DELETE")


class ComponentTemplateService(TemplateService):
    """Manage Elasticsearch component templates."""

    resource_path = "_component_template"
    response_collection = "component_templates"
    response_body = "component_template"
    keep_empty_template = True


class IndexTemplateService(TemplateService):
    """Manage Elasticsearch composable index templates."""

    resource_path = "_index_template"
    response_collection = "index_templates"
    response_body = "index_template"

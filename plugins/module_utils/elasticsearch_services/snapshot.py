# Copyright (c) 2026, zupersero
# GNU General Public License v3.0+
"""Elasticsearch snapshot repository and SLM services."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any, Mapping

if TYPE_CHECKING:
    from ..elasticsearch import ElasticsearchClient, ElasticsearchResponse

from ..elasticsearch import quote_resource_path


class SnapshotRepositoryService:
    def __init__(self, client: ElasticsearchClient) -> None:
        self.client = client

    @staticmethod
    def path(name: str) -> str:
        return quote_resource_path("_snapshot/{id}", name)

    def get(self, name: str) -> tuple[ElasticsearchResponse, dict[str, Any] | None]:
        response = self.client.request(self.path(name))
        current = None
        if response.status == 200 and isinstance(response.data, Mapping):
            value = response.data.get(name)
            if isinstance(value, Mapping):
                current = copy.deepcopy(dict(value))
        return response, current

    def put(
        self, name: str, payload: Mapping[str, Any], verify: bool
    ) -> ElasticsearchResponse:
        return self.client.request(
            self.path(name),
            method="PUT",
            query={"verify": str(verify).lower()},
            data=dict(payload),
        )

    def delete(self, name: str) -> ElasticsearchResponse:
        return self.client.request(self.path(name), method="DELETE")


class SnapshotLifecyclePolicyService:
    def __init__(self, client: ElasticsearchClient) -> None:
        self.client = client

    @staticmethod
    def path(name: str) -> str:
        return quote_resource_path("_slm/policy/{id}", name)

    def get(self, name: str) -> tuple[ElasticsearchResponse, dict[str, Any] | None]:
        response = self.client.request(self.path(name))
        current = None
        if response.status == 200 and isinstance(response.data, Mapping):
            value = response.data.get(name)
            if isinstance(value, Mapping):
                policy = value.get("policy")
                current = copy.deepcopy(
                    dict(policy if isinstance(policy, Mapping) else value)
                )
                if "name" in current:
                    current["snapshot_name"] = current.pop("name")
        return response, current

    def put(self, name: str, payload: Mapping[str, Any]) -> ElasticsearchResponse:
        data = dict(payload)
        if "snapshot_name" in data:
            data["name"] = data.pop("snapshot_name")
        return self.client.request(self.path(name), method="PUT", data=data)

    def delete(self, name: str) -> ElasticsearchResponse:
        return self.client.request(self.path(name), method="DELETE")

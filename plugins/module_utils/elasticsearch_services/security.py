# Copyright (c) 2026, zupersero
# GNU General Public License v3.0+
"""Elasticsearch API-key and role-mapping services."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any, Mapping

if TYPE_CHECKING:
    from ..elasticsearch import ElasticsearchClient, ElasticsearchResponse

from ..elasticsearch import quote_resource_path


class ApiKeyService:
    path = "_security/api_key"

    def __init__(self, client: ElasticsearchClient) -> None:
        self.client = client

    def get(self, key_id: str) -> tuple[ElasticsearchResponse, dict[str, Any] | None]:
        response = self.client.request(self.path, query={"id": key_id})
        current = None
        if response.status == 200 and isinstance(response.data, Mapping):
            keys = response.data.get("api_keys")
            if isinstance(keys, list) and keys and isinstance(keys[0], Mapping):
                current = copy.deepcopy(dict(keys[0]))
        return response, current

    def find_by_name(
        self, name: str
    ) -> tuple[ElasticsearchResponse, list[dict[str, Any]]]:
        response = self.client.request(self.path, query={"name": name})
        matches = []
        if response.status == 200 and isinstance(response.data, Mapping):
            keys = response.data.get("api_keys")
            if isinstance(keys, list):
                matches = [
                    copy.deepcopy(dict(key))
                    for key in keys
                    if isinstance(key, Mapping)
                    and key.get("name") == name
                    and not key.get("invalidated")
                ]
        return response, matches

    def create(self, payload: Mapping[str, Any]) -> ElasticsearchResponse:
        return self.client.request(self.path, method="POST", data=dict(payload))

    def update(self, key_id: str, payload: Mapping[str, Any]) -> ElasticsearchResponse:
        return self.client.request(
            quote_resource_path("_security/api_key/{id}", key_id),
            method="PUT",
            data=dict(payload),
        )

    def invalidate(self, key_id: str) -> ElasticsearchResponse:
        return self.client.request(self.path, method="DELETE", data={"ids": [key_id]})


class RoleMappingService:
    def __init__(self, client: ElasticsearchClient) -> None:
        self.client = client

    @staticmethod
    def path(name: str) -> str:
        return quote_resource_path("_security/role_mapping/{id}", name)

    def get(self, name: str) -> tuple[ElasticsearchResponse, dict[str, Any] | None]:
        response = self.client.request(self.path(name))
        current = None
        if response.status == 200 and isinstance(response.data, Mapping):
            value = response.data.get(name)
            if isinstance(value, Mapping):
                current = copy.deepcopy(dict(value))
        return response, current

    def put(self, name: str, payload: Mapping[str, Any]) -> ElasticsearchResponse:
        return self.client.request(self.path(name), method="PUT", data=dict(payload))

    def delete(self, name: str) -> ElasticsearchResponse:
        return self.client.request(self.path(name), method="DELETE")

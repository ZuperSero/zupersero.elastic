# Copyright (c) 2026, zupersero
# GNU General Public License v3.0+
"""Elasticsearch alias and cluster-settings services."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any, Mapping

if TYPE_CHECKING:
    from ..elasticsearch import ElasticsearchClient, ElasticsearchResponse

from ..elasticsearch import quote_resource_path


class IndexAliasService:
    """Manage one named index alias."""

    def __init__(self, client: ElasticsearchClient) -> None:
        self.client = client

    @staticmethod
    def path(name: str) -> str:
        return quote_resource_path("_alias/{id}", name)

    def get(self, name: str) -> tuple[ElasticsearchResponse, dict[str, Any]]:
        response = self.client.request(self.path(name))
        aliases: dict[str, Any] = {}
        if response.status == 200 and isinstance(response.data, Mapping):
            for index, definition in response.data.items():
                if not isinstance(definition, Mapping):
                    continue
                alias_map = definition.get("aliases")
                if isinstance(alias_map, Mapping) and isinstance(
                    alias_map.get(name), Mapping
                ):
                    aliases[str(index)] = copy.deepcopy(dict(alias_map[name]))
        return response, aliases

    def update(
        self, name: str, current: Mapping[str, Any], desired: Mapping[str, Any]
    ) -> ElasticsearchResponse:
        actions = [
            {"remove": {"index": index, "alias": name}}
            for index in sorted(set(current) - set(desired))
        ]
        actions.extend(
            {"add": {"index": index, "alias": name, **copy.deepcopy(options)}}
            for index, options in sorted(desired.items())
            if current.get(index) != options
        )
        return self.client.request("_aliases", method="POST", data={"actions": actions})


class ClusterSettingsService:
    """Manage the singleton cluster settings resource."""

    path = "_cluster/settings"

    def __init__(self, client: ElasticsearchClient) -> None:
        self.client = client

    def get(self) -> ElasticsearchResponse:
        return self.client.request(
            self.path, query={"flat_settings": "true", "include_defaults": "false"}
        )

    def update(self, payload: Mapping[str, Any]) -> ElasticsearchResponse:
        return self.client.request(self.path, method="PUT", data=dict(payload))

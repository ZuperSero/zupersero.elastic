# Copyright (c) 2025, zupersero
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations
from typing import TYPE_CHECKING
from urllib.parse import urlencode

if TYPE_CHECKING:
    from ..kibana import KibanaClient
else:
    from ansible_collections.zupersero.elastic.plugins.module_utils.kibana import KibanaClient

class AgentService:
    """
    Service for managing Kibana Agents.

    This service provides methods for CRUD operations on Kibana Agents.
    """

    def __init__(self, client: KibanaClient) -> None:
        """
        Initialize the Agent service.

        Args:
            client (KibanaClient): The Kibana client instance
        """
        self.client = client

    def get(self, agent_id: str) -> tuple[int, dict | None]:
        """
        Get an agent by ID.

        Args:
            agent_id (str): The agent ID to retrieve

        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, agent_data)
                - status_code: HTTP status code (200 if found, 404 if not found)
                - agent_data: Agent object if found, error dict if not found
        """
        path = f"api/fleet/agents/{agent_id}"
        return self.client.get(path)

    def list(
            self,
            page: int = 1,
            per_page: int = 20,
            kuery: str = "",
            show_agentless: bool = False,
            show_inactive: bool = False,
            with_metrics: bool = False,
            show_upgradeable: bool = False,
            get_status_summary: bool = False,
            sort_field: str = "",
            sort_order: str = "",
            search_after: str = "",
            open_pit: bool = False,
            pit_id: str = "",
            pit_keep_alive: str = "",
            extra_params: dict | None = None,
        ) -> tuple[int, dict | None]:
        """
        Get all agents.

        Args:
            params (dict | None): Optional query parameters for filtering, pagination, etc.

        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, agents_data)
                - status_code: HTTP status code (200 if successful)
                - agents_data: List of agent objects
        """
        query_params = {
            "page": page,
            "perPage": per_page,
            "kuery": kuery,
            "showAgentless": show_agentless,
            "showInactive": show_inactive,
            "withMetrics": with_metrics,
            "showUpgradeable": show_upgradeable,
            "getStatusSummary": get_status_summary,
            "sortField": sort_field,
            "sortOrder": sort_order,
            "searchAfter": search_after,
            "openPit": open_pit,
            "pitId": pit_id,
            "pitKeepAlive": pit_keep_alive,
        }
        if extra_params:
            query_params.update(extra_params)

        path = f"api/fleet/agents?{urlencode(query_params)}"
        return self.client.get(path)

    def update(self, agent_id: str, tags: list[str], user_provided_metadata: dict) -> tuple[int, dict | None]:
        """
        Update an existing agent.
        Args:
            agent_id (str): The agent ID to update
            tags (list[str]): List of tags to assign to the agent
            user_provided_metadata (dict): User-provided metadata for the agent
        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, updated_agent_data)
                - status_code: HTTP status code (200 if successful, 404 if not found)
                - updated_agent_data: Updated agent object or error dict
        """
        data = dict()
        if tags:
            data["tags"] = tags
        if user_provided_metadata:
            data["user_provided_metadata"] = user_provided_metadata

        path = f"api/fleet/agents/{agent_id}"
        return self.client.put(path, data=data)

    def delete(self, agent_id: str) -> tuple[int, dict | None]:
        """
        Delete an agent by ID.

        Args:
            agent_id (str): The agent ID to delete

        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, response_data)
                - status_code: HTTP status code (200 if successful, 404 if not found)
                - response_data: Success message or error dict
        """
        path = f"api/fleet/agents/{agent_id}"
        return self.client.delete(path)
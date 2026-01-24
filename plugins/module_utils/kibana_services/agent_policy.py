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

class AgentPolicyService:
    """
    Service for managing Kibana Agent Policies.

    This service provides methods for CRUD operations on Kibana Agent Policies.
    """

    def __init__(self, client: KibanaClient) -> None:
        """
        Initialize the Agent Policy service.

        Args:
            client (KibanaClient): The Kibana client instance
        """
        self.client = client

    def get(self, policy_id: str) -> tuple[int, dict | None]:
        """
        Get an agent policy by ID.

        Args:
            policy_id (str): The agent policy ID to retrieve

        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, policy_data)
                - status_code: HTTP status code (200 if found, 404 if not found)
                - policy_data: Agent policy object if found, error dict if not found
        """
        path = f"api/fleet/agent_policies/{policy_id}"
        return self.client.get(path)

    def get_full(self, policy_id: str) -> tuple[int, dict | None]:
        """
        Get an agent policy by ID with full details.

        Args:
            policy_id (str): The agent policy ID to retrieve
        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, policy_data)
                - status_code: HTTP status code (200 if found, 404 if not found)
                - policy_data: Agent policy object with full details if found, error dict if not found
        """
        path = f"api/fleet/agent_policies/{policy_id}/full"
        return self.client.get(path)

    def get_outputs(self, policy_id: str) -> tuple[int, dict | None]:
        """
        Get outputs associated with an agent policy.

        Args:
            policy_id (str): The agent policy ID to retrieve outputs for
        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, outputs_data)
                - status_code: HTTP status code (200 if found, 404 if not found)
                - outputs_data: Outputs associated with the agent policy if found, error dict if not found
        """
        path = f"api/fleet/agent_policies/{policy_id}/outputs"
        return self.client.get(path)

    def get_status(self, policy_id: str, policy_ids: list, kuery: str) -> tuple[int, dict | None]:
        """
        Get status of an agent policy.

        Args:
            policy_id (str): The agent policy ID to retrieve status for
            policy_ids (list): List of agent policy IDs to filter status
            kuery (str): KQL query to filter the status results
        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, status_data)
                - status_code: HTTP status code (200 if found, 404 if not found)
                - status_data: Status of the agent policy if found, error dict if not found
        """
        query_params = dict()
        if policy_id:
            query_params["policyId"] = policy_id
        if policy_ids:
            query_params["policyIds"] = policy_ids
        if kuery:
            query_params["kuery"] = kuery

        path = f"api/fleet/agent_policies/{policy_id}/status?{urlencode(query_params)}"
        return self.client.get(path)

    def list(
            self,
            page: int = 1,
            per_page: int = 20,
            sort_field: str ="name",
            sort_order: str ="asc",
            show_upgradeable: bool = False,
            kuery: str = "",
            with_agent_count: bool = False,
            full: bool = False,
            format: str = "simplified",
            extra_params: dict | None = None,
            ) -> tuple[int, dict | None]:
        """
        Get all agent policies.

        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, policies_data)
                - status_code: HTTP status code (200 if successful)
                - policies_data: List of agent policy objects
        """
        query_params = {
            "page": page,
            "perPage": per_page,
            "sortField": sort_field,
            "sortOrder": sort_order,
            "show_upgradeable": str(show_upgradeable).lower(),
            "kuery": kuery,
            "with_agent_count": str(with_agent_count).lower(),
            "full": str(full).lower(),
            "format": format
        }
        if extra_params:
            query_params.update(extra_params)
        path = f"api/fleet/agent_policies?{urlencode(query_params)}"
        return self.client.get(path)

    def create(self, policy_data: dict, sys_monitoring: bool=False) -> tuple[int, dict | None]:
        """
        Create a new agent policy.

        Args:
            policy_data (dict): Agent policy configuration including name, description, namespace, etc.
            sys_monitoring (bool): Whether to enable system monitoring on the policy

        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, created_policy_data)
                - status_code: HTTP status code (200/201 if successful, 409 if already exists)
                - created_policy_data: Created agent policy object or error dict
        """
        path = f"api/fleet/agent_policies?sys_monitoring={str(sys_monitoring).lower()}"
        return self.client.post(path, data=policy_data)

    def update(self, policy_id: str, policy_data: dict, format: str="simplified") -> tuple[int, dict | None]:
        """
        Update an existing agent policy.

        Args:
            policy_id (str): The agent policy ID to update
            policy_data (dict): Updated agent policy configuration
            format (str): Response format, either "simplified" or "full"

        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, updated_policy_data)
                - status_code: HTTP status code (200 if successful, 404 if not found)
                - updated_policy_data: Updated agent policy object or error dict
        """
        path = f"api/fleet/agent_policies/{policy_id}?format={format}"
        return self.client.put(path, data=policy_data)

    def copy(self, policy_id: str, new_name: str, description: str="", format: str="simplified") -> tuple[int, dict | None]:
        """
        Copy an existing agent policy.

        Args:
            policy_id (str): The agent policy ID to copy
            new_name (str): The name for the new copied agent policy
            description (str): The description for the new copied agent policy
            format (str): Response format, either "simplified" or "full"
        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, copied_policy_data)
                - status_code: HTTP status code (200/201 if successful, 404 if not found)
                - copied_policy_data: Copied agent policy object or error dict
        """
        path = f"api/fleet/agent_policies/{policy_id}/copy?format={format}"
        data = {"name": new_name, "description": description}
        return self.client.post(path, data=data)

    def delete(self, policy_id: str, force: bool=False) -> tuple[int, dict | None]:
        """
        Delete an agent policy.

        Args:
            policy_id (str): The agent policy ID to delete
            force (bool): Whether to force delete the policy even if in use

        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, response_data)
                - status_code: HTTP status code (200/204 if successful, 404 if not found)
                - response_data: Empty or error dict
        """
        data = dict(
            agentPolicyId=policy_id,
            force=force
        )
        path = "api/fleet/agent_policies/delete"
        return self.client.post(path,data=data)
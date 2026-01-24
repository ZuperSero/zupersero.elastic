# Copyright (c) 2025, zupersero
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..kibana import KibanaClient
else:
    from ansible_collections.zupersero.elastic.plugins.module_utils.kibana import KibanaClient


class RoleService:
    """
    Service for managing Kibana Roles.

    This service provides methods for CRUD operations on Kibana Roles.
    """

    def __init__(self, client: KibanaClient) -> None:
        """
        Initialize the Role service.

        Args:
            client (KibanaClient): The Kibana client instance
        """
        self.client = client

    def list(self) -> tuple[int, dict | None]:
        """
        Get all roles.

        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, roles_data)
                - status_code: HTTP status code (200 if successful)
                - roles_data: Dictionary of all roles
        """
        path = "api/security/role"
        return self.client.get(path)

    def get(self, role_name: str) -> tuple[int, dict | None]:
        """
        Get a role by name.

        Args:
            role_name (str): The role name to retrieve

        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, role_data)
                - status_code: HTTP status code (200 if found, 404 if not found)
                - role_data: Role object if found, error dict if not found
        """
        path = f"api/security/role/{role_name}"
        return self.client.get(path)

    def create(self, role_name: str, role_data: dict) -> tuple[int, dict | None]:
        """
        Create or update a role.

        Args:
            role_name (str): The name of the role to create
            role_data (dict): Role configuration including privileges and metadata

        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, created_role_data)
                - status_code: HTTP status code (200/201 if successful, 409 if already exists)
                - created_role_data: Created role object or error dict
        """
        path = f"api/security/role/{role_name}"
        return self.client.put(path, data=role_data)


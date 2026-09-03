# Copyright (c) 2025, zupersero
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..elasticsearch import ElasticsearchClient


class RoleService:
    """
    Service for managing Elasticsearch roles.
    """

    def __init__(self, client: ElasticsearchClient) -> None:
        """
        Initialize the Role service.
        """
        self.client = client

    def get(self, role_name: str) -> tuple[int, dict | None]:
        """
        Retrieve a role by name.

        Args:
            role_name (str): Role name to fetch

        Returns:
            tuple[int, dict | None]: (status_code, role_data or None)
        """
        path = f"_security/role/{role_name}"
        status_code, response = self.client.get(path)

        if status_code == 200 and isinstance(response, dict):
            role_data = response.get(role_name)
            if role_data is None and response:
                role_data = next(iter(response.values()))
            if isinstance(role_data, dict):
                role_data.setdefault("name", role_name)
                return status_code, role_data
        return status_code, response

    def create_or_update(self, role_name: str, role_data: dict) -> tuple[int, dict | None]:
        """
        Create or update a role.

        Args:
            role_name (str): Role name to create/update
            role_data (dict): Role payload

        Returns:
            tuple[int, dict | None]: (status_code, response_data)
        """
        path = f"_security/role/{role_name}"
        return self.client.put(path, data=role_data)

    def delete(self, role_name: str) -> tuple[int, dict | None]:
        """
        Delete a role.

        Args:
            role_name (str): Role name to delete

        Returns:
            tuple[int, dict | None]: (status_code, response_data)
        """
        path = f"_security/role/{role_name}"
        return self.client.delete(path)

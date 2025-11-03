# Copyright (c) 2025, zupersero
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ansible_collections.zupersero.elastic.plugins.module_utils.kibana import KibanaClient


class SpaceService:
    """
    Service for managing Kibana Spaces.

    This service provides methods for CRUD operations on Kibana Spaces.
    """

    def __init__(self, client: KibanaClient) -> None:
        """
        Initialize the Space service.

        Args:
            client (KibanaClient): The Kibana client instance
        """
        self.client = client

    def get(self, space_id: str) -> tuple[int, dict | None]:
        """
        Get a space by ID.

        Args:
            space_id (str): The space ID to retrieve

        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, space_data)
                - status_code: HTTP status code (200 if found, 404 if not found)
                - space_data: Space object if found, error dict if not found
        """
        path = f"api/spaces/space/{space_id}"
        return self.client.get(path)

    def create(self, space_data: dict) -> tuple[int, dict | None]:
        """
        Create a new space.

        Args:
            space_data (dict): Space configuration including id, name, description, disabledFeatures

        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, created_space_data)
                - status_code: HTTP status code (200/201 if successful, 409 if already exists)
                - created_space_data: Created space object or error dict
        """
        path = "api/spaces/space"
        return self.client.post(path, data=space_data)

    def update(self, space_id: str, space_data: dict) -> tuple[int, dict | None]:
        """
        Update an existing space.

        Args:
            space_id (str): The space ID to update
            space_data (dict): Updated space configuration

        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, updated_space_data)
                - status_code: HTTP status code (200 if successful, 404 if not found)
                - updated_space_data: Updated space object or error dict
        """
        path = f"api/spaces/space/{space_id}"
        return self.client.put(path, data=space_data)

    def delete(self, space_id: str) -> tuple[int, dict | None]:
        """
        Delete a space.

        Args:
            space_id (str): The space ID to delete

        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, response_data)
                - status_code: HTTP status code (200/204 if successful, 404 if not found)
                - response_data: Empty or error dict
        """
        path = f"api/spaces/space/{space_id}"
        return self.client.delete(path)

    def list(self) -> tuple[int, list[dict] | None]:
        """
        List all spaces.

        Returns:
            tuple[int, list[dict] | None]: Tuple containing (status_code, list_of_spaces)
                - status_code: HTTP status code (200 if successful)
                - list_of_spaces: List of space objects
        """
        path = "api/spaces/space"
        return self.client.get(path)
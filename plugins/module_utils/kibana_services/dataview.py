# Copyright (c) 2025, zupersero
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..kibana import KibanaClient
else:
    from ansible_collections.zupersero.elastic.plugins.module_utils.kibana import KibanaClient


class DataViewService:
    """
    Service for managing Kibana Data Views.

    This service provides methods for CRUD operations on Kibana Data Views.
    """

    def __init__(self, client: KibanaClient) -> None:
        """
        Initialize the Data View service.

        Args:
            client (KibanaClient): The Kibana client instance
        """
        self.client = client

    def get(self, data_view_id: str) -> tuple[int, dict | None]:
        """
        Get a data view by ID.

        Args:
            data_view_id (str): The data view ID to retrieve

        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, data_view_data)
                - status_code: HTTP status code (200 if found, 404 if not found)
                - data_view_data: Data view object if found, error dict if not found
        """
        path = f"api/data_views/data_view/{data_view_id}"
        return self.client.get(path)

    def list(self) -> tuple[int, dict | None]:
        """
        Get all data views.

        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, data_views_data)
                - status_code: HTTP status code (200 if successful)
                - data_views_data: List of data view objects
        """
        path = "api/data_views"
        return self.client.get(path)

    def create(self, data_view_data: dict) -> tuple[int, dict | None]:
        """
        Create a new data view.

        Args:
            data_view_data (dict): Data view configuration including title, timeFieldName, etc.

        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, created_data_view_data)
                - status_code: HTTP status code (200/201 if successful, 409 if already exists)
                - created_data_view_data: Created data view object or error dict
        """
        path = "api/data_views/data_view"
        return self.client.post(path, data=data_view_data)

    def update(self, data_view_id: str, data_view_data: dict) -> tuple[int, dict | None]:
        """
        Update an existing data view.

        Args:
            data_view_id (str): The data view ID to update
            data_view_data (dict): Updated data view configuration

        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, updated_data_view_data)
                - status_code: HTTP status code (200 if successful, 404 if not found)
                - updated_data_view_data: Updated data view object or error dict
        """
        path = f"api/data_views/data_view/{data_view_id}"
        return self.client.post(path, data=data_view_data)

    def delete(self, data_view_id: str) -> tuple[int, dict | None]:
        """
        Delete a data view.

        Args:
            data_view_id (str): The data view ID to delete

        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, response_data)
                - status_code: HTTP status code (200/204 if successful, 404 if not found)
                - response_data: Empty or error dict
        """
        path = f"api/data_views/data_view/{data_view_id}"
        return self.client.delete(path)

    def get_default(self) -> tuple[int, dict | None]:
        """
        Get the default data view.

        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, default_data_view_data)
                - status_code: HTTP status code (200 if found, 404 if not found)
                - default_data_view_data: Default data view object if found, error dict if not found
        """
        path = "api/data_views/default"
        return self.client.get(path)

    def set_default(self, data_view_id: str, force: bool = False) -> tuple[int, dict | None]:
        """
        Set a data view as the default.

        Args:
            data_view_id (str): The data view ID to set as default
            force (bool): Whether to force setting the default data view
        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, response_data)
        """
        path = "api/data_views/default"
        return self.client.post(path, data={"data_view_id": data_view_id, "force": force})
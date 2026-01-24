# Copyright (c) 2025, zupersero
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..kibana import KibanaClient
else:
    from ansible_collections.zupersero.elastic.plugins.module_utils.kibana import KibanaClient

class ConnectorService:
    """
    Service for managing Kibana Connectors.

    This service provides methods for CRUD operations on Kibana Connectors.
    """

    def __init__(self, client: KibanaClient) -> None:
        """
        Initialize the Connector service.

        Args:
            client (KibanaClient): The Kibana client instance
        """
        self.client = client

    def get(self, connector_id: str) -> tuple[int, dict | None]:
        """
        Get a connector by ID.

        Args:
            connector_id (str): The connector ID to retrieve

        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, connector_data)
                - status_code: HTTP status code (200 if found, 404 if not found)
                - connector_data: Connector object if found, error dict if not found
        """
        path = f"api/actions/connector/{connector_id}"
        return self.client.get(path)

    def list(self) -> tuple[int, dict | None]:
        """
        Get all connectors.

        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, connectors_data)
                - status_code: HTTP status code (200 if successful)
                - connectors_data: List of connector objects
        """
        path = "api/actions/connectors"
        return self.client.get(path)

    def create(self, connector_data: dict) -> tuple[int, dict | None]:
        """
        Create a new connector.

        Args:
            connector_data (dict): Connector configuration including name, connector_type_id, config, secrets

        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, created_connector_data)
                - status_code: HTTP status code (200/201 if successful, 409 if already exists)
                - created_connector_data: Created connector object or error dict
        """
        path = "api/actions/connector"
        return self.client.post(path, data=connector_data)

    def update(self, connector_id: str, connector_data: dict) -> tuple[int, dict | None]:
        """
        Update an existing connector.

        Args:
            connector_id (str): The connector ID to update
            connector_data (dict): Updated connector configuration

        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, updated_connector_data)
                - status_code: HTTP status code (200 if successful, 404 if not found)
                - updated_connector_data: Updated connector object or error dict
        """
        path = f"api/actions/connector/{connector_id}"
        return self.client.put(path, data=connector_data)

    def delete(self, connector_id: str) -> tuple[int, dict | None]:
        """
        Delete a connector.

        Args:
            connector_id (str): The connector ID to delete

        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, response_data)
                - status_code: HTTP status code (200/204 if successful, 404 if not found)
                - response_data: Empty or error dict
        """
        path = f"api/actions/connector/{connector_id}"
        return self.client.delete(path)

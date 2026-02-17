# Copyright (c) 2025, zupersero
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .. import kibana


class ConnectorService:
    """
    Service for interacting with Kibana Connectors API.
    """

    def __init__(self, client: "kibana.KibanaClient") -> None:
        """
        Initialize the ConnectorService.

        Args:
            client (kibana.KibanaClient): The Kibana client.
        """
        self.client = client
        self.base_path = "/api/actions"

    def get(self, connector_id: str) -> tuple[int, dict[str, Any] | None]:
        """
        Get a connector by ID.

        Args:
            connector_id (str): The ID of the connector to get.

        Returns:
            tuple[int, dict[str, Any] | None]: A tuple containing the status code and the connector data.
        """
        path = f"{self.base_path}/connector/{connector_id}"
        return self.client.get(path)

    def create(self, connector_data: dict[str, Any]) -> tuple[int, dict[str, Any] | None]:
        """
        Create a new connector.

        Args:
            connector_data (dict[str, Any]): The data for the new connector.

        Returns:
            tuple[int, dict[str, Any] | None]: A tuple containing the status code and the created connector data.
        """
        path = f"{self.base_path}/connector"
        return self.client.post(path, data=connector_data)

    def update(self, connector_id: str, connector_data: dict[str, Any]) -> tuple[int, dict[str, Any] | None]:
        """
        Update an existing connector.

        Args:
            connector_id (str): The ID of the connector to update.
            connector_data (dict[str, Any]): The updated connector data.

        Returns:
            tuple[int, dict[str, Any] | None]: A tuple containing the status code and the updated connector data.
        """
        path = f"{self.base_path}/connector/{connector_id}"
        return self.client.put(path, data=connector_data)

    def delete(self, connector_id: str) -> tuple[int, dict[str, Any] | None]:
        """
        Delete a connector by ID.

        Args:
            connector_id (str): The ID of the connector to delete.

        Returns:
            tuple[int, dict[str, Any] | None]: A tuple containing the status code and the response data.
        """
        path = f"{self.base_path}/connector/{connector_id}"
        return self.client.delete(path)

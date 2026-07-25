# Copyright (c) 2025, zupersero
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..elasticsearch import ElasticsearchClient


class UserService:
    """
    Service for managing Elasticsearch users.
    """

    def __init__(self, client: ElasticsearchClient) -> None:
        """
        Initialize the User service.
        """
        self.client = client

    def get(self, username: str) -> tuple[int, dict | None]:
        """
        Retrieve a user by username.

        Args:
            username (str): Username to fetch

        Returns:
            tuple[int, dict | None]: (status_code, user_data or None)
        """
        path = f"_security/user/{username}"
        status_code, response = self.client.get(path)

        if status_code == 200 and isinstance(response, dict):
            # The API returns a dict keyed by username
            user_data = response.get(username)
            if user_data is None and response:
                # Fallback: take the first user entry
                user_data = next(iter(response.values()))
            if isinstance(user_data, dict):
                user_data.setdefault("username", username)
                return status_code, user_data
        return status_code, response

    def create_or_update(self, username: str, user_data: dict) -> tuple[int, dict | None]:
        """
        Create or update a user.

        Args:
            username (str): Username to create/update
            user_data (dict): User payload

        Returns:
            tuple[int, dict | None]: (status_code, response_data)
        """
        path = f"_security/user/{username}"
        return self.client.put(path, data=user_data)

    def delete(self, username: str) -> tuple[int, dict | None]:
        """
        Delete a user.

        Args:
            username (str): Username to delete

        Returns:
            tuple[int, dict | None]: (status_code, response_data)
        """
        path = f"_security/user/{username}"
        return self.client.delete(path)

# Copyright (c) 2026, zupersero
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Service and comparison helpers for Elasticsearch security users."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping

if TYPE_CHECKING:
    from ..elasticsearch import ElasticsearchClient, ElasticsearchResponse

from ..elasticsearch import compare_objects, quote_resource_path


def _writable_user(resource: Mapping[str, Any]) -> dict[str, Any]:
    """Project a user response onto its comparable, writable fields.

    Passwords are excluded: Elasticsearch never returns them, so they can
    never participate in drift comparison.
    """
    return {
        "roles": list(resource.get("roles") or []),
        "full_name": resource.get("full_name") or resource.get("fullName") or "",
        "email": resource.get("email") or "",
        "metadata": resource.get("metadata") or {},
        "enabled": resource.get("enabled", True),
    }


class UserService:
    """Manage named Elasticsearch security users."""

    resource_path = "_security/user"

    def __init__(self, client: ElasticsearchClient) -> None:
        self.client = client

    @classmethod
    def path(cls, username: str) -> str:
        """Return the URL-quoted user resource path."""
        return quote_resource_path(f"{cls.resource_path}/{{id}}", username)

    def get(self, username: str) -> tuple[ElasticsearchResponse, dict[str, Any] | None]:
        """Read and unwrap an exact named user."""
        response = self.client.request(self.path(username))
        current = None
        if response.status == 200 and isinstance(response.data, Mapping):
            user_data = response.data.get(username)
            if user_data is None and response.data:
                user_data = next(iter(response.data.values()), None)
            if isinstance(user_data, Mapping):
                current = dict(user_data)
                current["username"] = username
        return response, current

    @staticmethod
    def payload(
        current: Mapping[str, Any] | None,
        desired: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Shallow-merge explicitly supplied fields over the current user.

        Only fields present in ``desired`` (the fields a task actually set)
        override the current value; every other field is preserved as-is.
        Never includes password/password_hash; callers add those separately
        through ``create_or_update``'s ``secrets`` argument.
        """
        merged = dict(_writable_user(current if current is not None else {}))
        merged.update(desired)
        return merged

    @classmethod
    def compare(
        cls,
        current: Mapping[str, Any],
        desired: Mapping[str, Any],
    ) -> tuple[bool, dict[str, Any]]:
        """Compare the current user against explicitly supplied desired fields."""
        return compare_objects(
            _writable_user(current),
            cls.payload(current, desired),
            unordered_lists=True,
            sensitive_fields=["password", "password_hash"],
        )

    def create_or_update(
        self,
        username: str,
        *,
        current: Mapping[str, Any] | None,
        desired: Mapping[str, Any],
        secrets: Mapping[str, Any] | None = None,
    ) -> ElasticsearchResponse:
        """Create or update a user with a preservation-aware payload.

        ``secrets`` carries ``password``/``password_hash`` when they should be
        applied on this request; whether that's the case is a module-level
        decision based on ``update_password`` and creation state.
        """
        payload = self.payload(current, desired)
        if secrets:
            payload.update(secrets)
        return self.client.request(self.path(username), method="PUT", data=payload)

    def delete(self, username: str) -> ElasticsearchResponse:
        """Delete a user."""
        return self.client.request(self.path(username), method="DELETE")

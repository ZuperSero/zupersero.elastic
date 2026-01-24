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

class EPMService:
    """
    Service for managing Kibana EPM (Elastic Package Manager).

    This service provides methods for CRUD operations on Kibana EPM packages.
    """

    def __init__(self, client: KibanaClient) -> None:
        """
        Initialize the EPM service.

        Args:
            client (KibanaClient): The Kibana client instance
        """
        self.client = client

    def get(
            self,
            package_name: str,
            package_version: str | None = None,
            ignore_unverified: bool = False,
            prerelease: bool = False,
            full: bool = False,
            withMetadata: bool = False,
        ) -> tuple[int, dict | None]:
        """
        Get a package by name and optional version.

        Args:
            package_name (str): The package name to retrieve
            package_version (str | None): The package version to retrieve (optional)
        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, package_data)
                - status_code: HTTP status code (200 if found, 404 if not found)
                - package_data: Package object if found, error dict if not found
        """
        query_params = {}
        if ignore_unverified:
            query_params["ignore_unverified"] = str(ignore_unverified).lower()
        if prerelease:
            query_params["prerelease"] = str(prerelease).lower()
        if full:
            query_params["full"] = str(full).lower()
        if withMetadata:
            query_params["withMetadata"] = str(withMetadata).lower()

        path = f"api/fleet/epm/packages/{package_name}"
        if package_version:
            path += f"/{package_version}"
        if query_params:
            path += "?" + urlencode(query_params)
        return self.client.get(path)

    def list(
            self,
            category: str | None = None,
            prerelease: bool | None = None,
            exclude_install_status: str | None = None,
            with_package_policies_count: bool | None = None,
        ) -> tuple[int, dict | None]:
        """
        Get all packages.
        Args:
            category (str | None): Filter by category (optional)
            prerelease (bool | None): Include prerelease packages (optional)
            exclude_install_status (str | None): Exclude packages by install status (optional)
            with_package_policies_count (bool | None): Include package policies count (optional)
        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, packages_data)
                - status_code: HTTP status code (200 if successful)
                - packages_data: List of package objects
        """
        query_params = {}
        if category:
            query_params["category"] = category
        if prerelease is not None:
            query_params["prerelease"] = str(prerelease).lower()
        if exclude_install_status:
            query_params["exclude_install_status"] = exclude_install_status
        if with_package_policies_count is not None:
            query_params["with_package_policies_count"] = str(with_package_policies_count).lower()
        path = "api/fleet/epm/packages"
        if query_params:
            path += "?" + urlencode(query_params)
        return self.client.get(path)

    def list_installed(self) -> tuple[int, dict | None]:
        """
        Get all installed packages.

        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, installed_packages_data)
                - status_code: HTTP status code (200 if successful)
                - installed_packages_data: List of installed package objects
        """
        path = "api/fleet/epm/packages/installed"
        return self.client.get(path)

    def install(
            self,
            package_name: str,
            package_version: str | None = None,
            prerelease: bool | None = None,
            ignore_mapping_update_errors: bool | None = None,
            skip_data_stream_rollover: bool | None = None,
            force: bool = False,
            ignore_constraints: bool = False,
        ) -> tuple[int, dict | None]:
        """
        Install a package by name and optional version.

        Args:
            package_name (str): The package name to install
            package_version (str | None): The package version to install (optional)
        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, install_response_data)
                - status_code: HTTP status code (200/201 if successful, 409 if already installed)
                - install_response_data: Installation response object or error dict
        """
        query_params = {}
        if prerelease is not None:
            query_params["prerelease"] = str(prerelease).lower()
        if ignore_mapping_update_errors is not None:
            query_params["ignoreMappingUpdateErrors"] = str(ignore_mapping_update_errors).lower()
        if skip_data_stream_rollover is not None:
            query_params["skipDataStreamRollover"] = str(skip_data_stream_rollover).lower()

        data = {
            "force": str(force).lower(),
            "ignore_constraints": str(ignore_constraints).lower()
        }

        path = f"api/fleet/epm/packages/{package_name}"
        if package_version:
            path += f"/{package_version}"
        if query_params:
            path += "?" + urlencode(query_params)

        return self.client.post(path, data=data)

    def update(
            self,
            package_name: str,
            package_version: str | None = None,
            keep_policies_up_to_date: bool = False,
    ) -> tuple[int, dict | None]:
        """
        Update a package by name and optional version.

        Args:
            package_name (str): The package name to update
            package_version (str | None): The package version to update (optional)
            keep_policies_up_to_date (bool): Whether to keep package policies up to date
        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, update_response_data)
                - status_code: HTTP status code (200 if successful, 404 if not found)
                - update_response_data: Update response object or error dict
        """
        data = {
            "keepPoliciesUpToDate": keep_policies_up_to_date
        }

        path = f"api/fleet/epm/packages/{package_name}"
        if package_version:
            path += f"/{package_version}"

        return self.client.put(path, data=data)


    def delete(
            self,
            package_name: str,
            package_version: str | None = None,
            force: bool = False,
        ) -> tuple[int, dict | None]:
        """
        Delete a package by name and optional version.

        Args:
            package_name (str): The package name to delete
            package_version (str | None): The package version to delete (optional)
        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, delete_response_data)
                - status_code: HTTP status code (200 if successful, 404 if not found)
                - delete_response_data: Deletion response object or error dict
        """
        query_params = {"force": str(force).lower()}
        path = f"api/fleet/epm/packages/{package_name}"
        if package_version:
            path += f"/{package_version}"
        path += "?" + urlencode(query_params)
        return self.client.delete(path)
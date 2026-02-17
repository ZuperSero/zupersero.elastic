# Copyright (c) 2025, zupersero
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations
from typing import Any
import json

from ansible.module_utils.basic import env_fallback
from ansible.module_utils.urls import url_argument_spec, fetch_url, basic_auth_header
from ansible.module_utils.api import retry_argument_spec, retry_with_delays_and_condition, generate_jittered_backoff



class KibanaRetryableError(Exception):
    """Exception raised for errors that should trigger a retry."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        """
        Initialize the retryable error.

        Args:
            message (str): Error message
            status_code (int | None, optional): HTTP status code. Defaults to None
        """
        super().__init__(message)
        self.status_code = status_code


def kibana_argument_spec() -> dict[str, dict[str, Any]]:
    """
    Build the argument specification for Kibana modules.

    Returns:
        dict[str, dict[str, Any]]: Ansible argument specification dictionary
    """
    argument_spec = url_argument_spec()

    # Delete unused parameters from url_argument_spec
    del argument_spec['force']
    del argument_spec['http_agent']
    del argument_spec['use_proxy']
    del argument_spec['validate_certs']
    if "use_gssapi" in argument_spec:
        del argument_spec["use_gssapi"]

    # Add Ansible native retry argument spec
    retry_spec = retry_argument_spec()

    # Update retries default from 10 to 3 for Kibana
    retry_spec['retries']['default'] = 3

    # Update with kibana specific parameters used in every module
    argument_spec.update(retry_spec)
    argument_spec.update(
        state=dict(type='str', choices=['present', 'absent'], default='present'),
        url=dict(type='str', required=False, fallback=(env_fallback, ['KIBANA_URL'])),
        username=dict(type='str', required=False, fallback=(env_fallback, ['KIBANA_USERNAME'])),
        password=dict(type='str', required=False, no_log=True, fallback=(env_fallback, ['KIBANA_PASSWORD'])),
        api_key=dict(type='str', required=False, no_log=True, fallback=(env_fallback, ['KIBANA_API_KEY'])),
        space=dict(type='str', required=False, default='default', fallback=(env_fallback, ['KIBANA_SPACE'])),
        validate_certs=dict(type='bool', default=True, fallback=(env_fallback, ['KIBANA_VALIDATE_CERTS'])),
        timeout=dict(type='int', default=30),
    )
    return argument_spec


def kibana_required_together() -> list[list[str]]:
    """
    Define required_together constraints for Kibana modules.

    Returns:
        list[list[str]]: Empty list as there are no required_together constraints
    """
    return []


def kibana_required_if() -> list[list[str]]:
    """
    Define required_if constraints for Kibana modules.

    Returns:
        list[list[str]]: Empty list as there are no required_if constraints
    """
    return []


def kibana_mutually_exclusive() -> list[list[str]]:
    """
    Define mutually_exclusive constraints for Kibana modules.

    Returns:
        list[list[str]]: Empty list as there are no mutually_exclusive constraints
    """
    return []


class KibanaClient:
    """
    Client for interacting with Kibana API.

    This client handles authentication, retries, and provides access to Kibana services.
    """

    def __init__(self, module: Any) -> None:
        """
        Initialize the Kibana client.

        Args:
            module (AnsibleModule): The Ansible module instance
        """
        from ansible_collections.zupersero.elastic.plugins.module_utils.kibana_services import (
            SpaceService,
            DataViewService,
            AgentService,
            AgentPolicyService,
            EPMService,
            ConnectorService,
            RoleService,
        )
        self.module = module
        self.url = module.params.get("url")
        self.username = module.params.get("username")
        self.password = module.params.get("password")
        self.api_key = module.params.get("api_key")
        self.validate_certs = module.params.get("validate_certs")
        self.timeout = module.params.get("timeout")
        # Convert to int to ensure compatibility with generate_jittered_backoff
        self.retries = int(module.params.get("retries"))
        self.retry_pause = int(module.params.get("retry_pause"))
        self.space_id = module.params.get("space")

        # Validate that we have either username/password or api_key
        if not self.api_key and not (self.username and self.password):
            module.fail_json(msg="Either api_key or username and password must be provided")

        if not self.url:
            module.fail_json(msg="Kibana URL is required")

        # Create retry decorator with jittered exponential backoff
        backoff_iterator = generate_jittered_backoff(
            retries=self.retries,
            delay_base=self.retry_pause,
            delay_threshold=60
        )
        self._retry_decorator = retry_with_delays_and_condition(
            backoff_iterator=backoff_iterator,
            should_retry_error=lambda e: isinstance(e, KibanaRetryableError)
        )

        # Services
        self.spaces = SpaceService(self)
        self.epm = EPMService(self)
        self.agent_policies = AgentPolicyService(self)
        self.agents = AgentService(self)
        self.data_views = DataViewService(self)
        self.connectors = ConnectorService(self)
        self.roles = RoleService(self)

    def _send_request_impl(self, path: str, method: str = 'GET', data: dict | None = None, extra_headers: dict | None = None) -> tuple[int, dict | None]:
        """
        Internal implementation of sending HTTP request to Kibana API.

        Args:
            path (str): API path (relative to Kibana base URL)
            method (str, optional): HTTP method. Defaults to 'GET'
            data (dict | None, optional): Request body data. Defaults to None
            extra_headers (dict | None, optional): Additional HTTP headers. Defaults to None

        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, response_data)

        Raises:
            KibanaRetryableError: For server errors (5xx) or connection failures that should be retried
        """
        if extra_headers is None:
            extra_headers = {}

        # Build full URL
        url = f"{self.url.rstrip('/')}/{path.lstrip('/')}"

        # Build headers
        headers = {
            'Content-Type': 'application/json',
            'kbn-xsrf': 'true',
            **extra_headers
        }

        # Add authentication
        if self.api_key:
            headers['Authorization'] = f'ApiKey {self.api_key}'
        elif self.username and self.password:
            headers['Authorization'] = basic_auth_header(self.username, self.password)

        # Prepare data
        body = json.dumps(data) if data else None

        try:
            resp, info = fetch_url(
                self.module,
                url,
                data=body,
                headers=headers,
                method=method,
                timeout=self.timeout,
            )

            status_code = info['status']

            # Try to parse response body
            response_data = None
            if resp:
                response_body = resp.read()
                if response_body:
                    # Try to parse as JSON first
                    try:
                        response_data = json.loads(response_body)
                    except (ValueError, json.JSONDecodeError):
                        # If not JSON, keep as string (decode if bytes)
                        if isinstance(response_body, bytes):
                            response_data = response_body.decode('utf-8', errors='replace')
                        else:
                            response_data = response_body

            # If successful, return
            if 200 <= status_code < 300:
                return status_code, response_data
            # Client errors shouldn't be retried
            elif 400 <= status_code < 500:
                # Extract error message from response
                if isinstance(response_data, dict):
                    error_msg = response_data.get('message', info.get('msg', 'Unknown error'))
                elif response_data:
                    error_msg = str(response_data)
                else:
                    error_msg = info.get('msg', 'Unknown error')
                return status_code, {'error': error_msg, 'status': status_code}
            # Server errors should be retried
            else:
                error_msg = f"HTTP {status_code}: {info.get('msg', 'Server error')}"
                raise KibanaRetryableError(error_msg, status_code)

        except KibanaRetryableError:
            # Re-raise retryable errors
            raise
        except Exception as e:
            # Connection errors and other exceptions should be retried
            raise KibanaRetryableError(f"Connection error: {str(e)}")

    def _send_request(self, path: str, method: str = 'GET', data: dict | None = None, extra_headers: dict | None = None) -> tuple[int, dict | None]:
        """
        Send an HTTP request to Kibana API with retry logic.

        Args:
            path (str): API path (relative to Kibana base URL)
            method (str, optional): HTTP method. Defaults to 'GET'
            data (dict | None, optional): Request body data. Defaults to None
            extra_headers (dict | None, optional): Additional HTTP headers. Defaults to None

        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, response_data)
        """
        # Apply retry decorator to the implementation
        retrying_func = self._retry_decorator(self._send_request_impl)
        try:
            return retrying_func(path, method, data, extra_headers)
        except KibanaRetryableError as e:
            # All retries exhausted
            self.module.fail_json(msg=f"Failed to connect to Kibana after {self.retries} attempts: {str(e)}")

    def get(self, path: str, headers: dict | None = None) -> tuple[int, dict | None]:
        """
        Send a GET request to Kibana API.

        Args:
            path (str): API path (relative to Kibana base URL)
            headers (dict | None, optional): Additional HTTP headers. Defaults to None

        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, response_data)
        """
        return self._send_request(path, method='GET', extra_headers=headers)

    def post(self, path: str, data: dict | None = None, headers: dict | None = None) -> tuple[int, dict | None]:
        """
        Send a POST request to Kibana API.

        Args:
            path (str): API path (relative to Kibana base URL)
            data (dict | None, optional): Request body data. Defaults to None
            headers (dict | None, optional): Additional HTTP headers. Defaults to None

        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, response_data)
        """
        return self._send_request(path, method='POST', data=data, extra_headers=headers)

    def put(self, path: str, data: dict | None = None, headers: dict | None = None) -> tuple[int, dict | None]:
        """
        Send a PUT request to Kibana API.

        Args:
            path (str): API path (relative to Kibana base URL)
            data (dict | None, optional): Request body data. Defaults to None
            headers (dict | None, optional): Additional HTTP headers. Defaults to None

        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, response_data)
        """
        return self._send_request(path, method='PUT', data=data, extra_headers=headers)

    def patch(self, path: str, data: dict | None = None, headers: dict | None = None) -> tuple[int, dict | None]:
        """
        Send a PATCH request to Kibana API.

        Args:
            path (str): API path (relative to Kibana base URL)
            data (dict | None, optional): Request body data. Defaults to None
            headers (dict | None, optional): Additional HTTP headers. Defaults to None

        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, response_data)
        """
        return self._send_request(path, method='PATCH', data=data, extra_headers=headers)

    def delete(self, path: str, headers: dict | None = None) -> tuple[int, dict | None]:
        """
        Send a DELETE request to Kibana API.

        Args:
            path (str): API path (relative to Kibana base URL)
            headers (dict | None, optional): Additional HTTP headers. Defaults to None

        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, response_data)
        """
        return self._send_request(path, method='DELETE', extra_headers=headers)

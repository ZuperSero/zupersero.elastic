# Copyright (c) 2025, zupersero
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations
from typing import Any
import json
from typing import TYPE_CHECKING

from ansible.module_utils.basic import env_fallback
from ansible.module_utils.urls import url_argument_spec, fetch_url, basic_auth_header
from ansible.module_utils.api import retry_argument_spec, retry_with_delays_and_condition, generate_jittered_backoff


if TYPE_CHECKING:
    from .elasticsearch_services import (
        UserService
    )
else:
    from ansible_collections.zupersero.elastic.plugins.module_utils.elasticsearch_services import (
        UserService
    )


class ElasticsearchRetryableError(Exception):
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


def elasticsearch_argument_spec() -> dict[str, dict[str, Any]]:
    """
    Build the argument specification for Elasticsearch modules.

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

    # Update retries default from 10 to 3 for Elasticsearch
    retry_spec['retries']['default'] = 3

    # Update with Elasticsearch specific parameters used in every module
    argument_spec.update(retry_spec)
    argument_spec.update(
        state=dict(type='str', choices=['present', 'absent'], default='present'),
        url=dict(type='str', required=False, fallback=(env_fallback, ['ELASTICSEARCH_URL'])),
        username=dict(type='str', required=False, fallback=(env_fallback, ['ELASTICSEARCH_USERNAME'])),
        password=dict(type='str', required=False, no_log=True, fallback=(env_fallback, ['ELASTICSEARCH_PASSWORD'])),
        api_key=dict(type='str', required=False, no_log=True, fallback=(env_fallback, ['ELASTICSEARCH_API_KEY'])),
        validate_certs=dict(type='bool', default=True, fallback=(env_fallback, ['ELASTICSEARCH_VALIDATE_CERTS'])),
        timeout=dict(type='int', default=30),
    )
    return argument_spec


def elasticsearch_required_together() -> list[list[str]]:
    """
    Define required_together constraints for Elasticsearch modules.

    Returns:
        list[list[str]]: Empty list as there are no required_together constraints
    """
    return []


def elasticsearch_required_if() -> list[list[str]]:
    """
    Define required_if constraints for Elasticsearch modules.

    Returns:
        list[list[str]]: Empty list as there are no required_if constraints
    """
    return []


def elasticsearch_mutually_exclusive() -> list[list[str]]:
    """
    Define mutually_exclusive constraints for Elasticsearch modules.

    Returns:
        list[list[str]]: Empty list as there are no mutually_exclusive constraints
    """
    return []


class ElasticsearchClient:
    """
    Client for interacting with Elasticsearch API.

    This client handles authentication, retries, and provides helper request methods.
    """

    def __init__(self, module: Any) -> None:
        """
        Initialize the Elasticsearch client.

        Args:
            module (AnsibleModule): The Ansible module instance
        """
        self.module = module
        self.url = module.params.get("url")
        self.username = module.params.get("username")
        self.password = module.params.get("password")
        self.api_key = module.params.get("api_key")
        self.validate_certs = module.params.get("validate_certs")
        self.timeout = module.params.get("timeout")
        self.retries = int(module.params.get("retries"))
        self.retry_pause = int(module.params.get("retry_pause"))

        # Validate authentication and URL
        if not self.api_key and not (self.username and self.password):
            module.fail_json(msg="Either api_key or username and password must be provided")

        if not self.url:
            module.fail_json(msg="Elasticsearch URL is required")

        # Create retry decorator with jittered exponential backoff
        backoff_iterator = generate_jittered_backoff(
            retries=self.retries,
            delay_base=self.retry_pause,
            delay_threshold=60
        )
        self._retry_decorator = retry_with_delays_and_condition(
            backoff_iterator=backoff_iterator,
            should_retry_error=lambda e: isinstance(e, ElasticsearchRetryableError)
        )

        # Services
        self.user = UserService(self)

    def _send_request_impl(self, path: str, method: str = 'GET', data: dict | None = None, extra_headers: dict | None = None) -> tuple[int, dict | None]:
        """
        Internal implementation of sending HTTP request to Elasticsearch API.

        Args:
            path (str): API path (relative to Elasticsearch base URL)
            method (str, optional): HTTP method. Defaults to 'GET'
            data (dict | None, optional): Request body data. Defaults to None
            extra_headers (dict | None, optional): Additional HTTP headers. Defaults to None

        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, response_data)

        Raises:
            ElasticsearchRetryableError: For server errors (5xx) or connection failures that should be retried
        """
        if extra_headers is None:
            extra_headers = {}

        url = f"{self.url.rstrip('/')}/{path.lstrip('/')}"

        headers = {
            'Content-Type': 'application/json',
            **extra_headers
        }

        if self.api_key:
            headers['Authorization'] = f'ApiKey {self.api_key}'
        elif self.username and self.password:
            headers['Authorization'] = basic_auth_header(self.username, self.password)

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

            response_data = None
            if resp:
                response_body = resp.read()
                if response_body:
                    try:
                        response_data = json.loads(response_body)
                    except (ValueError, json.JSONDecodeError):
                        if isinstance(response_body, bytes):
                            response_data = response_body.decode('utf-8', errors='replace')
                        else:
                            response_data = response_body

            if 200 <= status_code < 300:
                return status_code, response_data
            elif 400 <= status_code < 500:
                if isinstance(response_data, dict):
                    error_msg = response_data.get('error') or response_data.get('message') or info.get('msg', 'Unknown error')
                elif response_data:
                    error_msg = str(response_data)
                else:
                    error_msg = info.get('msg', 'Unknown error')
                return status_code, {'error': error_msg, 'status': status_code}
            else:
                error_msg = f"HTTP {status_code}: {info.get('msg', 'Server error')}"
                raise ElasticsearchRetryableError(error_msg, status_code)

        except ElasticsearchRetryableError:
            raise
        except Exception as e:
            raise ElasticsearchRetryableError(f"Connection error: {str(e)}")

    def _send_request(self, path: str, method: str = 'GET', data: dict | None = None, extra_headers: dict | None = None) -> tuple[int, dict | None]:
        """
        Send an HTTP request to Elasticsearch API with retry logic.

        Args:
            path (str): API path (relative to Elasticsearch base URL)
            method (str, optional): HTTP method. Defaults to 'GET'
            data (dict | None, optional): Request body data. Defaults to None
            extra_headers (dict | None, optional): Additional HTTP headers. Defaults to None

        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, response_data)
        """
        retrying_func = self._retry_decorator(self._send_request_impl)
        try:
            return retrying_func(path, method, data, extra_headers)
        except ElasticsearchRetryableError as e:
            self.module.fail_json(msg=f"Failed to connect to Elasticsearch after {self.retries} attempts: {str(e)}")

    def get(self, path: str, headers: dict | None = None) -> tuple[int, dict | None]:
        """
        Send a GET request to Elasticsearch API.

        Args:
            path (str): API path (relative to Elasticsearch base URL)
            headers (dict | None, optional): Additional HTTP headers. Defaults to None

        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, response_data)
        """
        return self._send_request(path, method='GET', extra_headers=headers)

    def post(self, path: str, data: dict | None = None, headers: dict | None = None) -> tuple[int, dict | None]:
        """
        Send a POST request to Elasticsearch API.

        Args:
            path (str): API path (relative to Elasticsearch base URL)
            data (dict | None, optional): Request body data. Defaults to None
            headers (dict | None, optional): Additional HTTP headers. Defaults to None

        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, response_data)
        """
        return self._send_request(path, method='POST', data=data, extra_headers=headers)

    def put(self, path: str, data: dict | None = None, headers: dict | None = None) -> tuple[int, dict | None]:
        """
        Send a PUT request to Elasticsearch API.

        Args:
            path (str): API path (relative to Elasticsearch base URL)
            data (dict | None, optional): Request body data. Defaults to None
            headers (dict | None, optional): Additional HTTP headers. Defaults to None

        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, response_data)
        """
        return self._send_request(path, method='PUT', data=data, extra_headers=headers)

    def delete(self, path: str, headers: dict | None = None) -> tuple[int, dict | None]:
        """
        Send a DELETE request to Elasticsearch API.

        Args:
            path (str): API path (relative to Elasticsearch base URL)
            headers (dict | None, optional): Additional HTTP headers. Defaults to None

        Returns:
            tuple[int, dict | None]: Tuple containing (status_code, response_data)
        """
        return self._send_request(path, method='DELETE', extra_headers=headers)

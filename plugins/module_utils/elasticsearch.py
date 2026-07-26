# Copyright (c) 2025, zupersero
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Shared Elasticsearch connection, transport, and object helpers."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import socket
import ssl
import tempfile
import time
import urllib.error
import urllib.parse
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Iterable, Mapping, Sequence

from ansible.module_utils.basic import env_fallback
from ansible.module_utils.urls import basic_auth_header, open_url, url_argument_spec

if TYPE_CHECKING:
    from .elasticsearch_services import RoleService, UserService
else:
    from ansible_collections.zupersero.elastic.plugins.module_utils.elasticsearch_services import (
        RoleService,
        UserService,
    )


DEFAULT_SUCCESS_CODES = list(range(200, 300))
DEFAULT_RETRY_STATUS_CODES = [429, 502, 503, 504]
SAFE_METHODS = frozenset(("GET", "HEAD", "OPTIONS"))
SENSITIVE_KEY_PATTERN = re.compile(
    r"(?:authorization|api[_-]?key|bearer|credential|encoded|password|private[_-]?key|secret|token)",
    re.IGNORECASE,
)
FEATURE_MINIMUM_VERSIONS = {
    "data_stream_lifecycle": (8, 11, 0),
    "inference": (8, 11, 0),
    "query_rules": (8, 10, 0),
    "synonyms": (8, 10, 0),
}


class ElasticsearchRetryableError(Exception):
    """An endpoint or transport failure that can be retried."""


@dataclass(frozen=True)
class ElasticsearchResponse:
    """A parsed Elasticsearch HTTP response."""

    status: int
    data: Any
    headers: Mapping[str, str]

    @property
    def is_success(self) -> bool:
        return 200 <= self.status < 300

    @property
    def is_async(self) -> bool:
        return self.status == 202 or async_task_id(self.data) is not None


def elasticsearch_argument_spec() -> dict[str, dict[str, Any]]:
    """Return the common argument specification used by Elasticsearch modules."""
    argument_spec = url_argument_spec()
    for parameter in ("force", "http_agent", "use_proxy", "validate_certs"):
        argument_spec.pop(parameter, None)
    argument_spec.pop("use_gssapi", None)

    argument_spec.update(
        state=dict(type="str", choices=["present", "absent"], default="present"),
        url=dict(
            type="str",
            required=False,
            fallback=(env_fallback, ["ELASTICSEARCH_URL"]),
        ),
        urls=dict(
            type="list",
            elements="str",
            required=False,
            fallback=(env_fallback, ["ELASTICSEARCH_URLS"]),
        ),
        username=dict(
            type="str",
            required=False,
            fallback=(env_fallback, ["ELASTICSEARCH_USERNAME"]),
        ),
        password=dict(
            type="str",
            required=False,
            no_log=True,
            fallback=(env_fallback, ["ELASTICSEARCH_PASSWORD"]),
        ),
        api_key=dict(
            type="str",
            required=False,
            no_log=True,
            fallback=(env_fallback, ["ELASTICSEARCH_API_KEY"]),
        ),
        bearer_token=dict(
            type="str",
            required=False,
            no_log=True,
            fallback=(env_fallback, ["ELASTICSEARCH_BEARER_TOKEN"]),
        ),
        headers=dict(
            type="dict",
            required=False,
            default={},
            no_log=True,
            fallback=(env_fallback, ["ELASTICSEARCH_HEADERS"]),
        ),
        validate_certs=dict(
            type="bool",
            default=True,
            fallback=(env_fallback, ["ELASTICSEARCH_VALIDATE_CERTS"]),
        ),
        ca_path=dict(
            type="path",
            required=False,
            fallback=(env_fallback, ["ELASTICSEARCH_CA_PATH"]),
        ),
        ca_data=dict(
            type="str",
            required=False,
            fallback=(env_fallback, ["ELASTICSEARCH_CA_DATA"]),
        ),
        client_cert=dict(
            type="path",
            required=False,
            fallback=(env_fallback, ["ELASTICSEARCH_CLIENT_CERT"]),
        ),
        client_key=dict(
            type="path",
            required=False,
            no_log=True,
            fallback=(env_fallback, ["ELASTICSEARCH_CLIENT_KEY"]),
        ),
        certificate_fingerprint=dict(
            type="str",
            required=False,
            fallback=(env_fallback, ["ELASTICSEARCH_CERTIFICATE_FINGERPRINT"]),
        ),
        timeout=dict(
            type="int",
            default=30,
            fallback=(env_fallback, ["ELASTICSEARCH_TIMEOUT"]),
        ),
        retries=dict(
            type="int",
            default=3,
            fallback=(env_fallback, ["ELASTICSEARCH_RETRIES"]),
        ),
        retry_pause=dict(
            type="float",
            default=1.0,
            fallback=(env_fallback, ["ELASTICSEARCH_RETRY_PAUSE"]),
        ),
        retry_status_codes=dict(
            type="list",
            elements="int",
            default=DEFAULT_RETRY_STATUS_CODES,
        ),
        retry_mutating_requests=dict(
            type="bool",
            default=False,
            fallback=(env_fallback, ["ELASTICSEARCH_RETRY_MUTATING_REQUESTS"]),
        ),
    )
    return argument_spec


def elasticsearch_required_together(
    *,
    username: str = "username",
    password: str = "password",
) -> list[list[str]]:
    """Return paired basic-auth constraints, with overridable module option names."""
    return [[username, password], ["url_username", "url_password"]]


def elasticsearch_required_if() -> list[list[Any]]:
    """Return common conditional constraints."""
    return []


def elasticsearch_mutually_exclusive(
    *,
    username: str = "username",
    password: str = "password",
    api_key: str = "api_key",
    bearer_token: str = "bearer_token",
) -> list[list[str]]:
    """Return endpoint, TLS, and authentication constraints."""
    return [
        ["url", "urls"],
        ["ca_path", "ca_data"],
        [username, api_key, bearer_token, "url_username"],
        [password, api_key, bearer_token, "url_password"],
    ]


def _redact_response_path(value: Any, components: list[str]) -> None:
    """Redact a dotted path, traversing every list entry when needed."""
    if not components:
        return
    component = components[0]
    remaining = components[1:]
    if isinstance(value, dict):
        if component not in value:
            for child in value.values():
                _redact_response_path(child, components)
            return
        if remaining:
            _redact_response_path(value[component], remaining)
        else:
            value[component] = "<redacted>"
    elif isinstance(value, list):
        if component.isdigit():
            index = int(component)
            if index < len(value):
                if remaining:
                    _redact_response_path(value[index], remaining)
                else:
                    value[index] = "<redacted>"
        else:
            for child in value:
                _redact_response_path(child, components)


def sanitize_data(
    value: Any,
    sensitive_fields: Iterable[str] | None = None,
) -> Any:
    """Recursively redact credential-like keys and configured dotted paths."""
    if isinstance(value, Mapping):
        sanitized = {}
        for key, item in value.items():
            sanitized[key] = (
                "<redacted>"
                if SENSITIVE_KEY_PATTERN.search(str(key))
                else sanitize_data(item)
            )
    elif isinstance(value, list):
        sanitized = [sanitize_data(item) for item in value]
    elif isinstance(value, tuple):
        sanitized = tuple(sanitize_data(item) for item in value)
    else:
        sanitized = value

    if sensitive_fields and isinstance(sanitized, (dict, list)):
        for path in sensitive_fields:
            _redact_response_path(sanitized, path.split("."))
    return sanitized


def extract_response_path(value: Any, path: str | None, default: Any = None) -> Any:
    """Extract a dotted dictionary/list path from a response."""
    if not path:
        return value
    current = value
    for part in path.split("."):
        if isinstance(current, Mapping) and part in current:
            current = current[part]
        elif isinstance(current, Sequence) and not isinstance(current, (str, bytes)):
            try:
                current = current[int(part)]
            except (IndexError, TypeError, ValueError):
                return default
        else:
            return default
    return current


def _set_response_path(target: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    current = target
    for part in parts[:-1]:
        child = current.get(part)
        if not isinstance(child, dict):
            child = {}
            current[part] = child
        current = child
    current[parts[-1]] = copy.deepcopy(value)


def _delete_response_path(value: Any, path: str) -> None:
    parts = path.split(".")
    current = value
    for part in parts[:-1]:
        if not isinstance(current, dict) or part not in current:
            return
        current = current[part]
    if isinstance(current, dict):
        current.pop(parts[-1], None)


def _project_like(current: Any, desired: Any) -> Any:
    if isinstance(desired, Mapping) and isinstance(current, Mapping):
        return {
            key: _project_like(current.get(key), desired_value)
            for key, desired_value in desired.items()
        }
    return copy.deepcopy(current)


def normalize_object(
    value: Any,
    *,
    ignore_fields: Iterable[str] | None = None,
    unordered_lists: bool = False,
) -> Any:
    """Normalize an API object for stable comparisons and diffs."""
    normalized = copy.deepcopy(value)
    if isinstance(normalized, dict):
        for path in ignore_fields or ():
            _delete_response_path(normalized, path)

    def normalize(item: Any) -> Any:
        if isinstance(item, Mapping):
            return {key: normalize(item[key]) for key in sorted(item)}
        if isinstance(item, list):
            result = [normalize(entry) for entry in item]
            if unordered_lists:
                result.sort(key=lambda entry: json.dumps(entry, sort_keys=True, separators=(",", ":")))
            return result
        return item

    return normalize(normalized)


def compare_objects(
    current: Any,
    desired: Any,
    *,
    compare_fields: Iterable[str] | None = None,
    ignore_fields: Iterable[str] | None = None,
    sensitive_fields: Iterable[str] | None = None,
    unordered_lists: bool = False,
) -> tuple[bool, dict[str, Any]]:
    """Compare desired state without treating unknown server fields as drift."""
    fields = list(compare_fields or ())
    if fields:
        current_comparable: dict[str, Any] = {}
        desired_comparable: dict[str, Any] = {}
        for path in fields:
            _set_response_path(current_comparable, path, extract_response_path(current, path))
            _set_response_path(desired_comparable, path, extract_response_path(desired, path))
    else:
        current_comparable = _project_like(current, desired)
        desired_comparable = copy.deepcopy(desired)

    before = normalize_object(
        current_comparable,
        ignore_fields=ignore_fields,
        unordered_lists=unordered_lists,
    )
    after = normalize_object(
        desired_comparable,
        ignore_fields=ignore_fields,
        unordered_lists=unordered_lists,
    )
    return before != after, {
        "before": sanitize_data(before, sensitive_fields),
        "after": sanitize_data(after, sensitive_fields),
    }


def quote_resource_path(path: str, resource_id: str | None = None) -> str:
    """Append or interpolate a URL-quoted resource identity."""
    if resource_id is None:
        return path
    quoted_id = urllib.parse.quote(str(resource_id), safe="")
    if "{id}" in path:
        return path.replace("{id}", quoted_id)
    return f"{path.rstrip('/')}/{quoted_id}"


def validate_api_path(path: str) -> str:
    """Validate that a request target is a well-formed relative API path."""
    if not path or any(ord(character) < 32 for character in path):
        raise ValueError("Elasticsearch API path must be a non-empty relative path")
    try:
        parsed = urllib.parse.urlsplit(path)
    except ValueError as exc:
        raise ValueError("Elasticsearch API path is malformed") from exc
    if (
        not parsed.path
        or parsed.scheme
        or parsed.netloc
        or parsed.fragment
        or path.startswith(("//", "\\\\"))
        or "\\" in path
        or re.search(r"%(?![0-9a-fA-F]{2})", path)
    ):
        raise ValueError(
            "Elasticsearch API path must be relative; absolute, cross-origin, "
            "and malformed paths are not allowed"
        )
    return path


def async_task_id(response: Any) -> str | None:
    """Return a task identifier from common Elasticsearch async responses."""
    if not isinstance(response, Mapping):
        return None
    task = response.get("task")
    if isinstance(task, str):
        return task
    if isinstance(task, Mapping):
        task_id = task.get("id") or task.get("task")
        return str(task_id) if task_id is not None else None
    if response.get("is_running") is True and response.get("id") is not None:
        return str(response["id"])
    return None


def encode_bulk_operations(operations: Iterable[Mapping[str, Any]]) -> str:
    """Encode bulk request lines as newline-delimited JSON."""
    lines = [json.dumps(operation, separators=(",", ":")) for operation in operations]
    return "\n".join(lines) + ("\n" if lines else "")


def parse_version(version: str | None) -> tuple[int, int, int]:
    """Parse an Elasticsearch version into a comparable three-part tuple."""
    match = re.match(r"^(\d+)\.(\d+)(?:\.(\d+))?", version or "")
    if not match:
        return (0, 0, 0)
    return tuple(int(part or 0) for part in match.groups())  # type: ignore[return-value]


def feature_available(
    feature: str,
    version: str | tuple[int, int, int],
    *,
    serverless: bool = False,
) -> bool:
    """Return whether a known feature is available for a deployment."""
    if serverless:
        return True
    current = parse_version(version) if isinstance(version, str) else version
    minimum = FEATURE_MINIMUM_VERSIONS.get(feature)
    return minimum is None or current >= minimum


def fail_api_error(
    module: Any,
    *,
    operation: str,
    path: str,
    response: ElasticsearchResponse,
    success_codes: Iterable[int],
    sensitive_fields: Iterable[str] | None = None,
) -> None:
    """Fail with actionable, credential-safe API context."""
    module.fail_json(
        msg=(
            f"Elasticsearch {operation} request to {path!r} returned HTTP "
            f"{response.status}; expected one of {sorted(set(success_codes))}"
        ),
        status=response.status,
        response=sanitize_data(response.data, sensitive_fields),
    )


class ElasticsearchClient:
    """Elasticsearch HTTP client with authentication, TLS, failover, and retries."""

    def __init__(self, module: Any) -> None:
        self.module = module
        params = module.params
        self.endpoints = self._resolve_endpoints(params.get("url"), params.get("urls"))
        self.url = self.endpoints[0]
        self.username = params.get("username") or params.get("url_username")
        self.password = params.get("password") or params.get("url_password")
        self.api_key = params.get("api_key")
        self.bearer_token = params.get("bearer_token")
        self.custom_headers = dict(params.get("headers") or {})
        self.validate_certs = params.get("validate_certs", True)
        self.ca_path = params.get("ca_path")
        self.ca_data = params.get("ca_data")
        self.client_cert = params.get("client_cert")
        self.client_key = params.get("client_key")
        self.certificate_fingerprint = self._normalize_fingerprint(
            params.get("certificate_fingerprint")
        )
        self.timeout = float(params.get("timeout", 30.0))
        self.retries = int(params.get("retries", 3))
        self.retry_pause = float(params.get("retry_pause", 1.0))
        self.retry_status_codes = set(
            params.get("retry_status_codes") or DEFAULT_RETRY_STATUS_CODES
        )
        self.retry_mutating_requests = bool(
            params.get("retry_mutating_requests", False)
        )
        self._active_endpoint_index = 0
        self._server_info: dict[str, Any] | None = None
        self._validate_options()

        self.role = RoleService(self)
        self.user = UserService(self)

    def _resolve_endpoints(
        self,
        url: str | None,
        urls: Iterable[str] | None,
    ) -> list[str]:
        endpoints = [str(item).strip() for item in (urls or ()) if str(item).strip()]
        if url:
            endpoints = [url.strip()]
        if not endpoints:
            self.module.fail_json(
                msg="An Elasticsearch endpoint is required through url, urls, "
                "ELASTICSEARCH_URL, or ELASTICSEARCH_URLS"
            )
        for endpoint in endpoints:
            parsed = urllib.parse.urlsplit(endpoint)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                self.module.fail_json(msg="Each Elasticsearch endpoint must be an absolute HTTP(S) URL")
            if parsed.username is not None or parsed.password is not None:
                self.module.fail_json(
                    msg="Credentials embedded in Elasticsearch endpoint URLs are not supported"
                )
        return [endpoint.rstrip("/") for endpoint in endpoints]

    @staticmethod
    def _normalize_fingerprint(value: str | None) -> str | None:
        if value is None:
            return None
        return re.sub(r"[:\s]", "", value).lower()

    def _validate_options(self) -> None:
        auth_modes = [
            bool(self.api_key),
            bool(self.bearer_token),
            bool(self.username or self.password),
        ]
        if sum(auth_modes) > 1:
            self.module.fail_json(
                msg="username/password, api_key, and bearer_token are mutually exclusive"
            )
        if bool(self.username) != bool(self.password):
            self.module.fail_json(msg="username and password must be provided together")
        if self.ca_path and self.ca_data:
            self.module.fail_json(msg="ca_path and ca_data are mutually exclusive")
        if self.client_key and not self.client_cert:
            self.module.fail_json(msg="client_key requires client_cert")
        if self.retries < 0:
            self.module.fail_json(msg="retries must be zero or greater")
        if self.retry_pause < 0:
            self.module.fail_json(msg="retry_pause must be zero or greater")
        if self.certificate_fingerprint and not re.fullmatch(
            r"[0-9a-f]{64}",
            self.certificate_fingerprint,
        ):
            self.module.fail_json(
                msg="certificate_fingerprint must be a SHA-256 fingerprint"
            )
        if self.certificate_fingerprint and any(
            not endpoint.startswith("https://") for endpoint in self.endpoints
        ):
            self.module.fail_json(
                msg="certificate_fingerprint can only be used with HTTPS endpoints"
            )
        if self.certificate_fingerprint and self.client_cert:
            self.module.fail_json(
                msg=(
                    "certificate_fingerprint cannot be combined with client_cert; "
                    "the server certificate must be pinned before client credentials "
                    "are disclosed"
                )
            )

    def _request_ca_path(self) -> str | None:
        if not self.ca_data:
            return self.ca_path
        temporary_directory = getattr(self.module, "tmpdir", None)
        if not temporary_directory:
            self.module.fail_json(
                msg="The Ansible module temporary directory is unavailable for ca_data"
            )
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=temporary_directory,
            prefix="elasticsearch-ca-",
            suffix=".pem",
            delete=False,
        ) as ca_file:
            ca_file.write(self.ca_data)
            self.ca_path = ca_file.name
        self.ca_data = None
        return self.ca_path

    def _headers(self, extra_headers: Mapping[str, str] | None) -> dict[str, str]:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        headers.update({str(key): str(value) for key, value in self.custom_headers.items()})
        if extra_headers:
            headers.update({str(key): str(value) for key, value in extra_headers.items()})
        authorization_key = next(
            (key for key in headers if key.lower() == "authorization"),
            None,
        )
        if self.api_key:
            headers[authorization_key or "Authorization"] = f"ApiKey {self.api_key}"
        elif self.bearer_token:
            headers[authorization_key or "Authorization"] = f"Bearer {self.bearer_token}"
        elif self.username and self.password:
            basic_header = basic_auth_header(
                self.username,
                self.password,
            )
            if isinstance(basic_header, bytes):
                basic_header = basic_header.decode("ascii")
            headers[authorization_key or "Authorization"] = basic_header
        return headers

    def _preflight_fingerprint(self, endpoint: str) -> None:
        """Pin the endpoint certificate before any authenticated HTTP request."""
        if not self.certificate_fingerprint:
            return
        parsed = urllib.parse.urlsplit(endpoint)
        hostname = parsed.hostname
        if not hostname:
            raise ElasticsearchRetryableError(
                "TLS certificate fingerprint preflight requires an endpoint hostname"
            )
        port = parsed.port or 443
        if self.validate_certs:
            context = ssl.create_default_context(cafile=self._request_ca_path())
        else:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        try:
            with socket.create_connection(
                (hostname, port),
                timeout=self.timeout,
            ) as raw_socket:
                with context.wrap_socket(
                    raw_socket,
                    server_hostname=hostname,
                ) as tls_socket:
                    certificate = tls_socket.getpeercert(binary_form=True)
        except (OSError, ssl.SSLError, ValueError) as exc:
            raise ElasticsearchRetryableError(
                f"TLS certificate fingerprint preflight failed: {exc.__class__.__name__}: {exc}"
            ) from exc
        if not certificate:
            raise ElasticsearchRetryableError(
                "TLS certificate fingerprint preflight returned no peer certificate"
            )
        actual = hashlib.sha256(certificate).hexdigest()
        if actual != self.certificate_fingerprint:
            raise ElasticsearchRetryableError("TLS certificate fingerprint verification failed")

    @staticmethod
    def _parse_body(body: Any) -> Any:
        if body in (None, b"", ""):
            return None
        if isinstance(body, bytes):
            body = body.decode("utf-8", errors="replace")
        try:
            return json.loads(body)
        except (TypeError, ValueError):
            return body

    def _single_request(
        self,
        endpoint: str,
        path: str,
        *,
        method: str,
        data: Any,
        headers: Mapping[str, str] | None,
        query: Mapping[str, Any] | None,
    ) -> ElasticsearchResponse:
        request_path = path.lstrip("/")
        request_url = f"{endpoint}/{request_path}"
        if query:
            separator = "&" if "?" in request_url else "?"
            request_url = f"{request_url}{separator}{urllib.parse.urlencode(query, doseq=True)}"

        if data is None:
            body = None
        elif isinstance(data, (bytes, str)):
            body = data
        else:
            body = json.dumps(data)

        self._preflight_fingerprint(endpoint)
        request_headers = self._headers(headers)
        unredirected_headers = [
            key for key in request_headers if SENSITIVE_KEY_PATTERN.search(key)
        ]
        try:
            response = open_url(
                request_url,
                data=body,
                headers=request_headers,
                method=method,
                timeout=self.timeout,
                validate_certs=self.validate_certs,
                client_cert=self.client_cert,
                client_key=self.client_key,
                ca_path=self._request_ca_path(),
                unredirected_headers=unredirected_headers,
                use_proxy=not bool(self.certificate_fingerprint),
                use_netrc=False,
            )
            response_body = response.read()
            response_headers = {
                str(key).lower(): str(value) for key, value in response.headers.items()
            }
            return ElasticsearchResponse(
                status=int(response.code),
                data=self._parse_body(response_body),
                headers=response_headers,
            )
        except urllib.error.HTTPError as exc:
            try:
                response_body = exc.read()
            finally:
                exc.close()
            return ElasticsearchResponse(
                status=int(exc.code),
                data=self._parse_body(response_body),
                headers={
                    str(key).lower(): str(value)
                    for key, value in (exc.headers.items() if exc.headers else ())
                },
            )
        except ElasticsearchRetryableError:
            raise
        except (OSError, urllib.error.URLError, ValueError) as exc:
            raise ElasticsearchRetryableError(
                f"{exc.__class__.__name__}: {str(exc)}"
            ) from exc

    def request(
        self,
        path: str,
        *,
        method: str = "GET",
        data: Any = None,
        headers: Mapping[str, str] | None = None,
        query: Mapping[str, Any] | None = None,
        retry_status_codes: Iterable[int] | None = None,
        retry_mutating: bool | None = None,
    ) -> ElasticsearchResponse:
        """Send a request, failing over endpoints between retry attempts."""
        try:
            validate_api_path(path)
        except ValueError as exc:
            self.module.fail_json(msg=str(exc))
        method = method.upper()
        retry_codes = set(retry_status_codes or self.retry_status_codes)
        last_error: ElasticsearchRetryableError | None = None
        mutation_retries = (
            self.retry_mutating_requests
            if retry_mutating is None
            else retry_mutating
        )
        attempts = (
            self.retries + 1
            if method in SAFE_METHODS or mutation_retries
            else 1
        )
        for attempt in range(attempts):
            endpoint_index = (
                self._active_endpoint_index + attempt
            ) % len(self.endpoints)
            endpoint = self.endpoints[endpoint_index]
            try:
                response = self._single_request(
                    endpoint,
                    path,
                    method=method,
                    data=data,
                    headers=headers,
                    query=query,
                )
                if response.status not in retry_codes:
                    self._active_endpoint_index = endpoint_index
                    return response
                if attempt == attempts - 1:
                    return response
            except ElasticsearchRetryableError as exc:
                last_error = exc
                if attempt == attempts - 1:
                    break
            if self.retry_pause:
                time.sleep(min(self.retry_pause * (2**attempt), 60.0))

        message = "Elasticsearch request failed after all endpoint attempts"
        if last_error is not None:
            message = f"{message}: {last_error}"
        self.module.fail_json(msg=message)
        raise AssertionError("module.fail_json must not return")

    def _send_request(
        self,
        path: str,
        method: str = "GET",
        data: Any = None,
        extra_headers: Mapping[str, str] | None = None,
    ) -> tuple[int, Any]:
        """Compatibility wrapper for existing tuple-based services."""
        response = self.request(
            path,
            method=method,
            data=data,
            headers=extra_headers,
        )
        if 400 <= response.status < 500:
            error = sanitize_data(response.data)
            if isinstance(error, Mapping):
                error = error.get("error") or error.get("message") or error
            return response.status, {"error": error, "status": response.status}
        if response.status >= 500:
            return response.status, sanitize_data(response.data)
        return response.status, response.data

    def get(
        self,
        path: str,
        headers: Mapping[str, str] | None = None,
    ) -> tuple[int, Any]:
        return self._send_request(path, method="GET", extra_headers=headers)

    def post(
        self,
        path: str,
        data: Any = None,
        headers: Mapping[str, str] | None = None,
    ) -> tuple[int, Any]:
        return self._send_request(path, method="POST", data=data, extra_headers=headers)

    def put(
        self,
        path: str,
        data: Any = None,
        headers: Mapping[str, str] | None = None,
    ) -> tuple[int, Any]:
        return self._send_request(path, method="PUT", data=data, extra_headers=headers)

    def patch(
        self,
        path: str,
        data: Any = None,
        headers: Mapping[str, str] | None = None,
    ) -> tuple[int, Any]:
        return self._send_request(path, method="PATCH", data=data, extra_headers=headers)

    def delete(
        self,
        path: str,
        headers: Mapping[str, str] | None = None,
    ) -> tuple[int, Any]:
        return self._send_request(path, method="DELETE", extra_headers=headers)

    def bulk(
        self,
        operations: Iterable[Mapping[str, Any]],
        *,
        path: str = "_bulk",
        query: Mapping[str, Any] | None = None,
    ) -> ElasticsearchResponse:
        """Submit newline-delimited bulk operations."""
        return self.request(
            path,
            method="POST",
            data=encode_bulk_operations(operations),
            headers={"Content-Type": "application/x-ndjson"},
            query=query,
        )

    def paginate(
        self,
        path: str,
        *,
        response_path: str,
        query: Mapping[str, Any] | None = None,
        sensitive_fields: Iterable[str] | None = None,
        page_size: int = 100,
        max_pages: int = 100,
        offset_parameter: str = "from",
        page_size_parameter: str = "size",
    ) -> tuple[list[Any], list[Any], int]:
        """Collect offset-based Elasticsearch pages."""
        objects: list[Any] = []
        responses: list[Any] = []
        status = 200
        base_query = dict(query or {})
        for page in range(max_pages):
            page_query = dict(base_query)
            page_query[offset_parameter] = page * page_size
            page_query[page_size_parameter] = page_size
            response = self.request(path, query=page_query)
            status = response.status
            sanitized_response = sanitize_data(response.data, sensitive_fields)
            responses.append(sanitized_response)
            if not response.is_success:
                return objects, responses, status
            page_objects = extract_response_path(sanitized_response, response_path)
            if not isinstance(page_objects, list):
                self.module.fail_json(
                    msg=f"Pagination response_path {response_path!r} did not resolve to a list"
                )
            objects.extend(page_objects)
            if len(page_objects) < page_size:
                break
            if page == max_pages - 1:
                self.module.fail_json(
                    msg=(
                        f"Pagination reached max_pages={max_pages} before "
                        "Elasticsearch returned a short page"
                    )
                )
        return objects, responses, status

    def supports_version(self, minimum_version: str | tuple[int, int, int]) -> bool:
        """Return whether the deployment meets a minimum Stack version."""
        minimum = (
            parse_version(minimum_version)
            if isinstance(minimum_version, str)
            else minimum_version
        )
        return self.is_serverless or self.version >= minimum

    def server_info(self, *, refresh: bool = False) -> dict[str, Any]:
        """Return cached cluster version and distribution metadata."""
        if self._server_info is None or refresh:
            response = self.request("/")
            if not response.is_success or not isinstance(response.data, dict):
                fail_api_error(
                    self.module,
                    operation="server info",
                    path="/",
                    response=response,
                    success_codes=[200],
                )
            self._server_info = response.data
        return self._server_info

    @property
    def version(self) -> tuple[int, int, int]:
        return parse_version(extract_response_path(self.server_info(), "version.number"))

    @property
    def is_serverless(self) -> bool:
        info = self.server_info()
        return (
            extract_response_path(info, "version.build_flavor") == "serverless"
            or info.get("serverless") is True
        )

    def supports_feature(self, feature: str) -> bool:
        return feature_available(feature, self.version, serverless=self.is_serverless)

    def wait_for_task(
        self,
        task_id: str,
        *,
        timeout: float = 300.0,
        poll_interval: float = 1.0,
    ) -> ElasticsearchResponse:
        """Poll an Elasticsearch task until completion or timeout."""
        deadline = time.monotonic() + timeout
        path = f"_tasks/{urllib.parse.quote(task_id, safe='')}"
        while True:
            response = self.request(path)
            if not response.is_success:
                return response
            if not isinstance(response.data, Mapping) or response.data.get("completed") is True:
                return response
            if time.monotonic() >= deadline:
                self.module.fail_json(
                    msg=f"Elasticsearch asynchronous task {task_id!r} did not complete before timeout"
                )
            time.sleep(poll_interval)

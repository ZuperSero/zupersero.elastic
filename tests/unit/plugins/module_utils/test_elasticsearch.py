# Copyright (c) 2026, zupersero
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import hashlib
import io
import json
import urllib.error
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import pytest

from ansible_collections.zupersero.elastic.plugins.module_utils import elasticsearch


class ModuleFailure(Exception):
    def __init__(self, result):
        super().__init__(result["msg"])
        self.result = result


class DummyModule:
    def __init__(self, tmp_path, **params):
        defaults = {
            "url": "https://first.invalid:9200",
            "urls": None,
            "username": None,
            "password": None,
            "api_key": None,
            "bearer_token": None,
            "headers": {},
            "validate_certs": True,
            "ca_path": None,
            "ca_data": None,
            "client_cert": None,
            "client_key": None,
            "certificate_fingerprint": None,
            "timeout": 30,
            "retries": 0,
            "retry_pause": 0,
            "retry_status_codes": [429, 502, 503, 504],
            "retry_mutating_requests": False,
            "url_username": None,
            "url_password": None,
        }
        defaults.update(params)
        self.params = defaults
        self.tmpdir = str(tmp_path)

    def fail_json(self, **kwargs):
        raise ModuleFailure(kwargs)


class FakeResponse:
    def __init__(self, status=200, data=None, certificate=None):
        self.code = status
        self.headers = {"Content-Type": "application/json"}
        self._data = json.dumps(data).encode() if data is not None else b""
        if certificate is not None:
            socket = Mock()
            socket.getpeercert.return_value = certificate
            self.fp = SimpleNamespace(raw=SimpleNamespace(_sock=socket))

    def read(self):
        return self._data


def test_argument_spec_exposes_aligned_secure_connection_contract():
    argument_spec = elasticsearch.elasticsearch_argument_spec()

    assert {
        "url",
        "urls",
        "username",
        "password",
        "api_key",
        "bearer_token",
        "headers",
        "validate_certs",
        "ca_path",
        "ca_data",
        "client_cert",
        "client_key",
        "certificate_fingerprint",
        "timeout",
        "retries",
        "retry_pause",
        "retry_status_codes",
        "retry_mutating_requests",
    } <= argument_spec.keys()
    assert argument_spec["password"]["no_log"] is True
    assert argument_spec["api_key"]["no_log"] is True
    assert argument_spec["bearer_token"]["no_log"] is True
    assert argument_spec["headers"]["no_log"] is True
    assert elasticsearch.elasticsearch_required_together() == [
        ["username", "password"],
        ["url_username", "url_password"],
    ]
    assert elasticsearch.elasticsearch_mutually_exclusive() == [
        ["url", "urls"],
        ["ca_path", "ca_data"],
        ["username", "api_key", "bearer_token", "url_username"],
        ["password", "api_key", "bearer_token", "url_password"],
    ]


def test_auth_constraints_support_managed_user_option_names():
    assert elasticsearch.elasticsearch_required_together(
        username="auth_username",
        password="auth_password",
    )[0] == ["auth_username", "auth_password"]
    assert elasticsearch.elasticsearch_mutually_exclusive(
        username="auth_username",
        password="auth_password",
        api_key="auth_api_key",
    )[2] == ["auth_username", "auth_api_key", "bearer_token", "url_username"]


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"username": "elastic", "password": "changeme"}, "Basic "),
        ({"api_key": "encoded-key"}, "ApiKey encoded-key"),
        ({"bearer_token": "access-token"}, "Bearer access-token"),
    ],
)
def test_authentication_headers_are_sent_without_leaking_into_results(
    tmp_path,
    params,
    expected,
):
    module = DummyModule(tmp_path, **params)
    with patch.object(elasticsearch, "open_url", return_value=FakeResponse(data={"ok": True})) as mocked:
        response = elasticsearch.ElasticsearchClient(module).request("_cluster/health")

    authorization = mocked.call_args.kwargs["headers"]["Authorization"]
    assert authorization.startswith(expected)
    assert response.data == {"ok": True}


def test_custom_headers_and_query_are_applied(tmp_path):
    module = DummyModule(tmp_path, headers={"X-Opaque-Id": "ansible"})
    with patch.object(elasticsearch, "open_url", return_value=FakeResponse(data={})) as mocked:
        elasticsearch.ElasticsearchClient(module).request(
            "_search",
            query={"filter_path": ["hits.total", "took"], "pretty": True},
        )

    assert mocked.call_args.kwargs["headers"]["X-Opaque-Id"] == "ansible"
    requested_url = mocked.call_args.args[0]
    assert "filter_path=hits.total" in requested_url
    assert "filter_path=took" in requested_url
    assert "pretty=True" in requested_url


@pytest.mark.parametrize(
    "path",
    [
        "",
        "https://evil.invalid/_search",
        "//evil.invalid/_search",
        "\\\\evil.invalid\\_search",
        "_search\\evil",
        "/_search#fragment",
        "/_search%ZZ",
        "?query=only",
        "/_search\nX-Injected: true",
    ],
)
def test_unsafe_api_paths_are_rejected_before_sensitive_headers(tmp_path, path):
    module = DummyModule(
        tmp_path,
        username="elastic",
        password="must-not-be-sent",
        headers={"X-Secret-Token": "must-not-be-sent"},
    )
    client = elasticsearch.ElasticsearchClient(module)
    with (
        patch.object(client, "_preflight_fingerprint") as preflight,
        patch.object(client, "_headers", wraps=client._headers) as build_headers,
        patch.object(elasticsearch, "open_url") as open_url,
        pytest.raises(ModuleFailure) as failure,
    ):
        client.request(path)

    assert "relative" in failure.value.result["msg"]
    assert "must-not-be-sent" not in failure.value.result["msg"]
    preflight.assert_not_called()
    build_headers.assert_not_called()
    open_url.assert_not_called()


@pytest.mark.parametrize(
    "params",
    [
        {"username": "elastic"},
        {"username": "elastic", "password": "x", "api_key": "key"},
        {"api_key": "key", "bearer_token": "token"},
        {"client_key": "/tmp/client.key"},
        {"certificate_fingerprint": "not-a-sha256-fingerprint"},
        {
            "url": "http://first.invalid:9200",
            "certificate_fingerprint": "0" * 64,
        },
        {
            "client_cert": "/tmp/client.crt",
            "certificate_fingerprint": "0" * 64,
        },
    ],
)
def test_invalid_connection_combinations_fail_before_transport(tmp_path, params):
    with pytest.raises(ModuleFailure):
        elasticsearch.ElasticsearchClient(DummyModule(tmp_path, **params))


def test_retry_rotates_endpoints_and_uses_backoff(tmp_path):
    module = DummyModule(
        tmp_path,
        url=None,
        urls=["https://one.invalid:9200", "https://two.invalid:9200"],
        retries=1,
        retry_pause=0.5,
    )
    with (
        patch.object(
            elasticsearch,
            "open_url",
            side_effect=[
                FakeResponse(status=503, data={"error": "busy"}),
                FakeResponse(status=200, data={"ok": True}),
                FakeResponse(status=200, data={"affinity": True}),
            ],
        ) as mocked,
        patch.object(elasticsearch.time, "sleep") as sleep,
    ):
        client = elasticsearch.ElasticsearchClient(module)
        response = client.request("_cluster/health")
        affinity_response = client.request("_cluster/health")

    assert response.status == 200
    assert affinity_response.data == {"affinity": True}
    assert mocked.call_args_list[0].args[0].startswith("https://one.invalid:9200/")
    assert mocked.call_args_list[1].args[0].startswith("https://two.invalid:9200/")
    assert mocked.call_args_list[2].args[0].startswith("https://two.invalid:9200/")
    sleep.assert_called_once_with(0.5)


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_mutating_requests_are_not_retried_by_default(tmp_path, method):
    module = DummyModule(tmp_path, retries=3, retry_pause=0.5)
    with (
        patch.object(
            elasticsearch,
            "open_url",
            side_effect=[
                FakeResponse(status=503, data={"error": "busy"}),
                FakeResponse(status=200, data={"ok": True}),
            ],
        ) as mocked,
        patch.object(elasticsearch.time, "sleep") as sleep,
    ):
        response = elasticsearch.ElasticsearchClient(module).request(
            "_action",
            method=method,
        )

    assert response.status == 503
    assert mocked.call_count == 1
    sleep.assert_not_called()


def test_mutating_request_retry_requires_explicit_opt_in(tmp_path):
    module = DummyModule(
        tmp_path,
        retries=1,
        retry_pause=0.5,
        retry_mutating_requests=True,
    )
    with (
        patch.object(
            elasticsearch,
            "open_url",
            side_effect=[
                FakeResponse(status=503, data={"error": "busy"}),
                FakeResponse(status=200, data={"ok": True}),
            ],
        ) as mocked,
        patch.object(elasticsearch.time, "sleep") as sleep,
    ):
        response = elasticsearch.ElasticsearchClient(module).request(
            "_action",
            method="POST",
        )

    assert response.status == 200
    assert mocked.call_count == 2
    sleep.assert_called_once_with(0.5)


def test_404_response_body_is_preserved(tmp_path):
    error = urllib.error.HTTPError(
        "https://first.invalid:9200/missing",
        404,
        "not found",
        {"Content-Type": "application/json"},
        io.BytesIO(b'{"error":{"type":"resource_not_found_exception"}}'),
    )
    with patch.object(elasticsearch, "open_url", side_effect=error):
        response = elasticsearch.ElasticsearchClient(DummyModule(tmp_path)).request("missing")

    assert response.status == 404
    assert response.data["error"]["type"] == "resource_not_found_exception"


def test_malformed_json_response_is_returned_as_text(tmp_path):
    malformed = FakeResponse()
    malformed._data = b"{not-json"
    with patch.object(elasticsearch, "open_url", return_value=malformed):
        response = elasticsearch.ElasticsearchClient(DummyModule(tmp_path)).request("/")

    assert response.data == "{not-json"


def test_ca_data_is_written_to_module_tempdir_and_passed_to_transport(tmp_path):
    module = DummyModule(tmp_path, ca_data="-----BEGIN CERTIFICATE-----\ntest\n")
    with patch.object(elasticsearch, "open_url", return_value=FakeResponse(data={})) as mocked:
        elasticsearch.ElasticsearchClient(module).request("/")

    ca_path = Path(mocked.call_args.kwargs["ca_path"])
    assert ca_path.parent == tmp_path
    assert ca_path.read_text() == module.params["ca_data"]


def test_certificate_fingerprint_is_verified(tmp_path):
    certificate = b"peer certificate"
    fingerprint = hashlib.sha256(certificate).hexdigest()
    module = DummyModule(tmp_path, certificate_fingerprint=fingerprint)
    raw_socket = MagicMock()
    tls_socket = MagicMock()
    tls_socket.getpeercert.return_value = certificate
    context = MagicMock()
    context.wrap_socket.return_value.__enter__.return_value = tls_socket
    with (
        patch.object(
            elasticsearch.socket,
            "create_connection",
            return_value=raw_socket,
        ) as create_connection,
        patch.object(
            elasticsearch.ssl,
            "create_default_context",
            return_value=context,
        ),
        patch.object(
            elasticsearch,
            "open_url",
            return_value=FakeResponse(data={"ok": True}),
        ) as open_url,
    ):
        response = elasticsearch.ElasticsearchClient(module).request("/")

    assert response.is_success
    create_connection.assert_called_once_with(
        ("first.invalid", 9200),
        timeout=30.0,
    )
    context.wrap_socket.assert_called_once_with(
        raw_socket.__enter__.return_value,
        server_hostname="first.invalid",
    )
    assert open_url.call_args.kwargs["use_proxy"] is False


def test_fingerprint_mismatch_sends_no_authentication_or_custom_headers(tmp_path):
    module = DummyModule(
        tmp_path,
        username="elastic",
        password="credential-that-must-not-be-sent",
        headers={"X-Secret-Token": "custom-secret-that-must-not-be-sent"},
        certificate_fingerprint="0" * 64,
    )
    raw_socket = MagicMock()
    tls_socket = MagicMock()
    tls_socket.getpeercert.return_value = b"unexpected"
    context = MagicMock()
    context.wrap_socket.return_value.__enter__.return_value = tls_socket
    client = elasticsearch.ElasticsearchClient(module)
    with (
        patch.object(
            elasticsearch.socket,
            "create_connection",
            return_value=raw_socket,
        ),
        patch.object(
            elasticsearch.ssl,
            "create_default_context",
            return_value=context,
        ),
        patch.object(elasticsearch, "open_url") as open_url,
        patch.object(client, "_headers", wraps=client._headers) as build_headers,
        pytest.raises(ModuleFailure) as failure,
    ):
        client.request("/")

    assert "fingerprint verification failed" in failure.value.result["msg"]
    assert "unexpected" not in failure.value.result["msg"]
    assert "credential-that-must-not-be-sent" not in failure.value.result["msg"]
    assert "custom-secret-that-must-not-be-sent" not in failure.value.result["msg"]
    build_headers.assert_not_called()
    open_url.assert_not_called()


def test_normalization_ignores_unknown_fields_and_redacts_secrets():
    changed, diff = elasticsearch.compare_objects(
        {
            "name": "pipeline",
            "server_managed": 42,
            "steps": ["b", "a"],
            "password": "returned-secret",
        },
        {"name": "pipeline", "steps": ["a", "b"], "password": "returned-secret"},
        unordered_lists=True,
    )

    assert changed is False
    assert diff["before"]["password"] == "<redacted>"
    assert diff["after"]["password"] == "<redacted>"
    assert "server_managed" not in diff["before"]


def test_api_key_creation_response_fields_are_redacted():
    assert elasticsearch.sanitize_data(
        {"id": "key-id", "api_key": "raw-secret", "encoded": "base64-secret"}
    ) == {
        "id": "key-id",
        "api_key": "<redacted>",
        "encoded": "<redacted>",
    }


def test_legacy_service_error_response_is_redacted(tmp_path):
    error = urllib.error.HTTPError(
        "https://first.invalid:9200/_security/user/test",
        400,
        "bad request",
        {"Content-Type": "application/json"},
        io.BytesIO(b'{"error":{"password":"echoed-secret","reason":"invalid"}}'),
    )
    with patch.object(elasticsearch, "open_url", side_effect=error):
        status, result = elasticsearch.ElasticsearchClient(DummyModule(tmp_path)).put(
            "_security/user/test",
            data={"password": "echoed-secret"},
        )

    assert status == 400
    assert result["error"]["password"] == "<redacted>"


def test_explicit_compare_and_ignore_paths():
    changed, diff = elasticsearch.compare_objects(
        {"spec": {"enabled": True, "revision": 3}},
        {"spec": {"enabled": False, "revision": 4}},
        compare_fields=["spec.enabled", "spec.revision"],
        ignore_fields=["spec.revision"],
    )

    assert changed is True
    assert diff == {
        "before": {"spec": {"enabled": True}},
        "after": {"spec": {"enabled": False}},
    }


def test_explicit_sensitive_paths_are_redacted_from_comparison_diff():
    changed, diff = elasticsearch.compare_objects(
        {"attributes": {"name": "example", "pin": "1234"}},
        {"attributes": {"name": "example", "pin": "5678"}},
        sensitive_fields=["attributes.pin"],
    )

    assert changed is True
    assert diff["before"]["attributes"]["pin"] == "<redacted>"
    assert diff["after"]["attributes"]["pin"] == "<redacted>"


def test_sensitive_paths_traverse_every_list_item():
    value = {
        "items": [
            {"name": "one", "pin": "1111"},
            {"name": "two", "pin": "2222"},
        ]
    }

    assert elasticsearch.sanitize_data(value, ["items.pin"]) == {
        "items": [
            {"name": "one", "pin": "<redacted>"},
            {"name": "two", "pin": "<redacted>"},
        ]
    }


def test_extract_quote_bulk_async_and_feature_helpers():
    assert elasticsearch.extract_response_path({"hits": [{"_id": "1"}]}, "hits.0._id") == "1"
    assert elasticsearch.quote_resource_path("_scripts/{id}", "score/v2") == "_scripts/score%2Fv2"
    assert elasticsearch.encode_bulk_operations([{"index": {"_index": "logs"}}, {"message": "ok"}]).endswith("\n")
    assert elasticsearch.async_task_id({"task": "node:123"}) == "node:123"
    assert elasticsearch.parse_version("8.11.2-SNAPSHOT") == (8, 11, 2)
    assert elasticsearch.feature_available("inference", "8.10.4") is False
    assert elasticsearch.feature_available("inference", "8.10.4", serverless=True) is True


def test_bulk_uses_ndjson_content_type(tmp_path):
    with patch.object(elasticsearch, "open_url", return_value=FakeResponse(data={"errors": False})) as mocked:
        response = elasticsearch.ElasticsearchClient(DummyModule(tmp_path)).bulk(
            [{"index": {"_index": "logs"}}, {"message": "test"}]
        )

    assert response.data == {"errors": False}
    assert mocked.call_args.kwargs["headers"]["Content-Type"] == "application/x-ndjson"
    assert mocked.call_args.kwargs["data"].endswith("\n")


def test_offset_pagination_collects_pages(tmp_path):
    with patch.object(
        elasticsearch,
        "open_url",
        side_effect=[
            FakeResponse(
                data={
                    "hits": {
                        "hits": [
                            {"_id": "1", "pin": "1111"},
                            {"_id": "2", "pin": "2222"},
                        ]
                    }
                }
            ),
            FakeResponse(data={"hits": {"hits": [{"_id": "3", "pin": "3333"}]}}),
        ],
    ):
        objects, responses, status = elasticsearch.ElasticsearchClient(
            DummyModule(tmp_path)
        ).paginate(
            "_search",
            response_path="hits.hits",
            page_size=2,
            sensitive_fields=["hits.hits.pin"],
        )

    assert [item["_id"] for item in objects] == ["1", "2", "3"]
    assert [item["pin"] for item in objects] == [
        "<redacted>",
        "<redacted>",
        "<redacted>",
    ]
    assert responses[0]["hits"]["hits"][0]["pin"] == "<redacted>"
    assert len(responses) == 2
    assert status == 200


def test_server_version_and_features_are_cached(tmp_path):
    response = FakeResponse(
        data={"version": {"number": "8.11.1", "build_flavor": "default"}}
    )
    with patch.object(elasticsearch, "open_url", return_value=response) as mocked:
        client = elasticsearch.ElasticsearchClient(DummyModule(tmp_path))
        assert client.version == (8, 11, 1)
        assert client.supports_version("8.10.0") is True
        assert client.supports_feature("inference") is True

    mocked.assert_called_once()

# Copyright (c) 2026, zupersero
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from unittest.mock import Mock

import pytest

from ansible_collections.zupersero.elastic.plugins.module_utils.elasticsearch import (
    ElasticsearchResponse,
)
from ansible_collections.zupersero.elastic.plugins.modules import (
    elasticsearch_info,
    elasticsearch_object,
    elasticsearch_request,
)


class ModuleExit(Exception):
    def __init__(self, result):
        super().__init__()
        self.result = result


class ModuleFailure(Exception):
    def __init__(self, result):
        super().__init__(result["msg"])
        self.result = result


class FakeModule:
    def __init__(self, params, check_mode=False):
        self.params = params
        self.check_mode = check_mode

    def exit_json(self, **kwargs):
        raise ModuleExit(kwargs)

    def fail_json(self, **kwargs):
        raise ModuleFailure(kwargs)


def object_params(**overrides):
    params = {
        "path": "_ingest/pipeline",
        "id": "managed/pipeline",
        "payload": {"description": "managed", "processors": []},
        "query": {},
        "create_path": None,
        "get_method": "GET",
        "create_method": "PUT",
        "update_method": "PUT",
        "delete_method": "DELETE",
        "get_success_codes": [200],
        "create_success_codes": [200, 201, 202],
        "update_success_codes": [200, 201, 202],
        "delete_success_codes": [200, 202, 204],
        "not_found_codes": [404],
        "response_path": "managed/pipeline",
        "compare_fields": [],
        "ignore_fields": [],
        "sensitive_fields": [],
        "unordered_lists": False,
        "state": "present",
    }
    params.update(overrides)
    return params


def response(status, data=None):
    return ElasticsearchResponse(status=status, data=data, headers={})


def test_object_method_and_success_code_contract():
    spec = elasticsearch_object.object_argument_spec()

    assert spec["get_method"] == {
        "type": "str",
        "choices": ["GET", "POST"],
        "default": "GET",
    }
    assert spec["create_method"] == {
        "type": "str",
        "choices": ["POST", "PUT", "PATCH"],
        "default": "PUT",
    }
    assert spec["update_method"] == {
        "type": "str",
        "choices": ["POST", "PUT", "PATCH"],
        "default": "PUT",
    }
    assert spec["create_success_codes"]["default"] == [200, 201, 202]
    assert spec["update_success_codes"]["default"] == [200, 201, 202]


def test_object_create_check_mode_is_non_mutating_and_quotes_id():
    module = FakeModule(object_params(response_path=None), check_mode=True)
    client = Mock()
    client.request.return_value = response(404, {"error": "missing"})

    with pytest.raises(ModuleExit) as exit_result:
        elasticsearch_object.run_module(module, client)

    assert exit_result.value.result == {
        "changed": True,
        "object": {"description": "managed", "processors": []},
        "status": 404,
        "diff": {
            "before": {},
            "after": {"description": "managed", "processors": []},
        },
    }
    client.request.assert_called_once_with(
        "_ingest/pipeline/managed%2Fpipeline",
        method="GET",
        query={},
    )


def test_object_ignores_unknown_server_fields_for_idempotency():
    current = {
        "managed/pipeline": {
            "description": "managed",
            "processors": [],
            "server_managed_revision": 7,
        }
    }
    module = FakeModule(object_params())
    client = Mock()
    client.request.return_value = response(200, current)

    with pytest.raises(ModuleExit) as exit_result:
        elasticsearch_object.run_module(module, client)

    result = exit_result.value.result
    assert result["changed"] is False
    assert result["object"]["server_managed_revision"] == 7
    assert result["diff"]["before"] == result["diff"]["after"]
    client.request.assert_called_once()


def test_object_update_refreshes_managed_state():
    before = {
        "managed/pipeline": {"description": "old", "processors": []}
    }
    after = {
        "managed/pipeline": {"description": "managed", "processors": []}
    }
    module = FakeModule(object_params())
    client = Mock()
    client.request.side_effect = [
        response(200, before),
        response(200, {"acknowledged": True}),
        response(200, after),
    ]

    with pytest.raises(ModuleExit) as exit_result:
        elasticsearch_object.run_module(module, client)

    assert exit_result.value.result["changed"] is True
    assert exit_result.value.result["object"]["description"] == "managed"
    assert client.request.call_args_list[1].kwargs["method"] == "PUT"
    assert client.request.call_args_list[1].kwargs["data"] == module.params["payload"]


def test_object_delete_check_mode_preserves_observed_object():
    current = {
        "managed/pipeline": {
            "description": "managed",
            "password": "server-secret",
        }
    }
    module = FakeModule(object_params(state="absent"), check_mode=True)
    client = Mock()
    client.request.return_value = response(200, current)

    with pytest.raises(ModuleExit) as exit_result:
        elasticsearch_object.run_module(module, client)

    result = exit_result.value.result
    assert result["changed"] is True
    assert result["object"]["password"] == "<redacted>"
    assert result["diff"]["after"] == {}
    client.request.assert_called_once()


def test_object_uses_configurable_not_found_codes():
    module = FakeModule(
        object_params(
            response_path=None,
            not_found_codes=[404, 410],
        ),
        check_mode=True,
    )
    client = Mock()
    client.request.return_value = response(410, {"message": "gone"})

    with pytest.raises(ModuleExit) as exit_result:
        elasticsearch_object.run_module(module, client)

    assert exit_result.value.result["changed"] is True
    assert exit_result.value.result["status"] == 410


def test_object_redacts_configured_sensitive_fields_from_output_and_diff():
    current = {
        "managed/pipeline": {
            "attributes": {"name": "example", "pin": "1234"},
        }
    }
    module = FakeModule(
        object_params(
            payload={"attributes": {"name": "example", "pin": "5678"}},
            sensitive_fields=["attributes.pin"],
        ),
        check_mode=True,
    )
    client = Mock()
    client.request.return_value = response(200, current)

    with pytest.raises(ModuleExit) as exit_result:
        elasticsearch_object.run_module(module, client)

    result = exit_result.value.result
    assert result["changed"] is True
    assert result["object"]["attributes"]["pin"] == "<redacted>"
    assert result["diff"]["before"]["attributes"]["pin"] == "<redacted>"
    assert result["diff"]["after"]["attributes"]["pin"] == "<redacted>"


def test_object_api_failure_is_actionable_and_sanitized():
    module = FakeModule(object_params(response_path=None))
    client = Mock()
    client.request.return_value = response(
        401,
        {"error": "unauthorized", "api_key": "should-not-leak"},
    )

    with pytest.raises(ModuleFailure) as failure:
        elasticsearch_object.run_module(module, client)

    assert failure.value.result["status"] == 401
    assert failure.value.result["response"]["api_key"] == "<redacted>"
    assert "read" in failure.value.result["msg"]


@pytest.mark.parametrize("method", ["GET", "HEAD", "OPTIONS"])
def test_request_safe_methods_never_report_changed(method):
    module = FakeModule(
        {
            "path": "_cluster/health",
            "method": method,
            "body": None,
            "query": {},
            "success_codes": [200],
            "response_path": "status",
            "sensitive_fields": [],
        }
    )
    client = Mock()
    client.request.return_value = response(200, {"status": "green"})

    with pytest.raises(ModuleExit) as exit_result:
        elasticsearch_request.run_module(module, client)

    assert exit_result.value.result == {
        "changed": False,
        "response": "green",
        "status": 200,
    }


def test_request_mutating_method_is_skipped_in_check_mode():
    module = FakeModule(
        {
            "path": "_refresh",
            "method": "POST",
            "body": None,
            "query": {},
            "success_codes": [200],
            "response_path": None,
            "sensitive_fields": [],
        },
        check_mode=True,
    )
    client = Mock()

    with pytest.raises(ModuleExit) as exit_result:
        elasticsearch_request.run_module(module, client)

    assert exit_result.value.result == {
        "changed": True,
        "response": None,
        "status": None,
    }
    client.request.assert_not_called()


def test_request_redacts_sensitive_list_fields_from_success():
    module = FakeModule(
        {
            "path": "_items",
            "method": "GET",
            "body": None,
            "query": {},
            "success_codes": [200],
            "response_path": None,
            "sensitive_fields": ["items.pin"],
        }
    )
    client = Mock()
    client.request.return_value = response(
        200,
        {"items": [{"name": "one", "pin": "1111"}, {"name": "two", "pin": "2222"}]},
    )

    with pytest.raises(ModuleExit) as exit_result:
        elasticsearch_request.run_module(module, client)

    assert [item["pin"] for item in exit_result.value.result["response"]["items"]] == [
        "<redacted>",
        "<redacted>",
    ]


def test_request_redacts_sensitive_list_fields_from_failure():
    module = FakeModule(
        {
            "path": "_items",
            "method": "GET",
            "body": None,
            "query": {},
            "success_codes": [200],
            "response_path": None,
            "sensitive_fields": ["items.pin"],
        }
    )
    client = Mock()
    client.request.return_value = response(
        400,
        {"items": [{"pin": "must-not-leak"}], "error": "invalid"},
    )

    with pytest.raises(ModuleFailure) as failure:
        elasticsearch_request.run_module(module, client)

    assert failure.value.result["response"]["items"][0]["pin"] == "<redacted>"


def test_info_returns_extracted_read_only_result_in_check_mode():
    module = FakeModule(
        {
            "path": "/",
            "query": {},
            "response_path": "version.number",
            "success_codes": [200],
            "paginate": False,
            "page_size": 100,
            "max_pages": 100,
            "offset_parameter": "from",
            "page_size_parameter": "size",
            "sensitive_fields": [],
        },
        check_mode=True,
    )
    client = Mock()
    client.request.return_value = response(
        200,
        {"version": {"number": "8.11.1"}},
    )

    with pytest.raises(ModuleExit) as exit_result:
        elasticsearch_info.run_module(module, client)

    assert exit_result.value.result["changed"] is False
    assert exit_result.value.result["objects"] == "8.11.1"
    assert exit_result.value.result["status"] == 200


def test_info_redacts_sensitive_fields_from_success_and_failure():
    success_module = FakeModule(
        {
            "path": "_items",
            "query": {},
            "response_path": "items",
            "success_codes": [200],
            "paginate": False,
            "page_size": 100,
            "max_pages": 100,
            "offset_parameter": "from",
            "page_size_parameter": "size",
            "sensitive_fields": ["items.pin"],
        }
    )
    success_client = Mock()
    success_client.request.return_value = response(
        200,
        {"items": [{"name": "one", "pin": "must-not-leak"}]},
    )
    with pytest.raises(ModuleExit) as exit_result:
        elasticsearch_info.run_module(success_module, success_client)

    assert exit_result.value.result["objects"][0]["pin"] == "<redacted>"
    assert exit_result.value.result["response"]["items"][0]["pin"] == "<redacted>"

    failure_module = FakeModule(dict(success_module.params))
    failure_client = Mock()
    failure_client.request.return_value = response(
        403,
        {"items": [{"pin": "must-not-leak"}], "error": "forbidden"},
    )
    with pytest.raises(ModuleFailure) as failure:
        elasticsearch_info.run_module(failure_module, failure_client)

    assert failure.value.result["response"]["items"][0]["pin"] == "<redacted>"


def test_info_pagination_returns_objects_and_raw_pages():
    module = FakeModule(
        {
            "path": "_search",
            "query": {"track_total_hits": True},
            "response_path": "hits.hits",
            "success_codes": [200],
            "paginate": True,
            "page_size": 2,
            "max_pages": 3,
            "offset_parameter": "from",
            "page_size_parameter": "size",
            "sensitive_fields": ["pin"],
        }
    )
    client = Mock()
    pages = [
        {
            "hits": {
                "hits": [
                    {"_id": "1", "pin": "1111"},
                    {"_id": "2", "pin": "2222"},
                ]
            }
        },
        {"hits": {"hits": [{"_id": "3", "pin": "3333"}]}},
    ]
    client.paginate.return_value = (
        [
            {"_id": "1", "pin": "1111"},
            {"_id": "2", "pin": "2222"},
            {"_id": "3", "pin": "3333"},
        ],
        pages,
        200,
    )

    with pytest.raises(ModuleExit) as exit_result:
        elasticsearch_info.run_module(module, client)

    assert exit_result.value.result["objects"][-1]["_id"] == "3"
    assert all(
        item["pin"] == "<redacted>"
        for item in exit_result.value.result["objects"]
    )
    assert (
        exit_result.value.result["response"][0]["hits"]["hits"][0]["pin"]
        == "<redacted>"
    )
    assert exit_result.value.result["changed"] is False

# Copyright (c) 2026, zupersero
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from unittest.mock import Mock, call

import pytest

from ansible_collections.zupersero.elastic.plugins.module_utils.elasticsearch import (
    ElasticsearchResponse,
)
from ansible_collections.zupersero.elastic.plugins.module_utils.elasticsearch_services.index import (
    IndexService,
    normalize_index_settings,
)
from ansible_collections.zupersero.elastic.plugins.modules import index


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


def response(status, data=None):
    return ElasticsearchResponse(status=status, data=data, headers={})


def params(**overrides):
    values = {
        "name": "phase1/index",
        "settings": None,
        "mappings": None,
        "state": "present",
    }
    values.update(overrides)
    return values


def managed_index(
    *,
    settings=None,
    mappings=None,
    aliases=None,
    name="phase1/index",
):
    return {
        name: {
            "aliases": aliases or {},
            "mappings": mappings or {},
            "settings": settings or {
                "index": {
                    "number_of_shards": "1",
                    "number_of_replicas": "0",
                    "uuid": "server-managed",
                }
            },
        }
    }


def module_client(*responses):
    client = Mock()
    client.request.side_effect = responses
    client.index = IndexService(client)
    return client


def test_argument_spec_exposes_typed_options_and_marks_secrets():
    spec = index.index_argument_spec()

    assert spec["name"] == {"type": "str", "required": True}
    assert spec["settings"] == {"type": "dict"}
    assert spec["mappings"] == {"type": "dict"}
    assert spec["state"]["choices"] == ["present", "absent"]
    assert spec["password"]["no_log"] is True
    assert spec["api_key"]["no_log"] is True
    assert spec["bearer_token"]["no_log"] is True


def test_settings_normalization_accepts_namespaced_dotted_and_scalar_values():
    assert normalize_index_settings(
        {
            "index": {
                "number_of_replicas": 0,
                "blocks": {"read_only": False},
            },
            "index.refresh_interval": "5s",
        }
    ) == {
        "number_of_replicas": "0",
        "blocks.read_only": "false",
        "refresh_interval": "5s",
    }


def test_service_quotes_index_name_and_sends_typed_api_requests():
    transport = Mock()
    transport.request.side_effect = [
        response(200, managed_index()),
        response(200, {"acknowledged": True}),
        response(200, {"acknowledged": True}),
        response(200, {"acknowledged": True}),
        response(200, {"acknowledged": True}),
    ]
    service = IndexService(transport)

    read_response, current = service.get("phase1/index")
    create_response = service.create(
        "phase1/index",
        settings={"number_of_shards": 1},
        mappings={"properties": {"id": {"type": "keyword"}}},
    )
    settings_response = service.update_settings(
        "phase1/index",
        {"index.refresh_interval": "5s"},
    )
    mapping_response = service.update_mapping(
        "phase1/index",
        {"properties": {"message": {"type": "text"}}},
    )
    delete_response = service.delete("phase1/index")

    assert read_response.status == 200
    assert current["name"] == "phase1/index"
    assert create_response.status == settings_response.status == 200
    assert mapping_response.status == delete_response.status == 200
    assert transport.request.call_args_list == [
        call("phase1%2Findex"),
        call(
            "phase1%2Findex",
            method="PUT",
            data={
                "settings": {"number_of_shards": 1},
                "mappings": {"properties": {"id": {"type": "keyword"}}},
            },
        ),
        call(
            "phase1%2Findex/_settings",
            method="PUT",
            data={"settings": {"index.refresh_interval": "5s"}},
        ),
        call(
            "phase1%2Findex/_mapping",
            method="PUT",
            data={"properties": {"message": {"type": "text"}}},
        ),
        call("phase1%2Findex", method="DELETE"),
    ]


def test_create_check_mode_is_non_mutating():
    module = FakeModule(
        params(
            settings={"number_of_shards": 1},
            mappings={"properties": {"id": {"type": "keyword"}}},
        ),
        check_mode=True,
    )
    client = module_client(response(404, {"error": {"type": "index_not_found_exception"}}))

    with pytest.raises(ModuleExit) as exit_result:
        index.run_module(module, client)

    assert exit_result.value.result == {
        "changed": True,
        "index": {
            "name": "phase1/index",
            "settings": {"number_of_shards": 1},
            "mappings": {"properties": {"id": {"type": "keyword"}}},
        },
        "status": 404,
        "diff": {
            "before": {},
            "after": {
                "name": "phase1/index",
                "settings": {"number_of_shards": 1},
                "mappings": {"properties": {"id": {"type": "keyword"}}},
            },
        },
    }
    client.request.assert_called_once_with("phase1%2Findex")


def test_create_refreshes_and_returns_managed_index():
    module = FakeModule(
        params(
            settings={"number_of_shards": 1},
            mappings={"properties": {"id": {"type": "keyword"}}},
        )
    )
    created = managed_index(
        mappings={"properties": {"id": {"type": "keyword"}}},
    )
    client = module_client(
        response(404, {"error": "missing"}),
        response(200, {"acknowledged": True, "index": "phase1/index"}),
        response(200, created),
    )

    with pytest.raises(ModuleExit) as exit_result:
        index.run_module(module, client)

    result = exit_result.value.result
    assert result["changed"] is True
    assert result["status"] == 200
    assert result["index"]["name"] == "phase1/index"
    assert result["index"]["mappings"]["properties"]["id"]["type"] == "keyword"
    assert client.request.call_args_list[1] == call(
        "phase1%2Findex",
        method="PUT",
        data={
            "settings": {"number_of_shards": 1},
            "mappings": {"properties": {"id": {"type": "keyword"}}},
        },
    )


def test_existing_index_is_idempotent_with_server_fields_and_string_settings():
    module = FakeModule(
        params(
            settings={
                "number_of_shards": 1,
                "number_of_replicas": 0,
            },
            mappings={"properties": {"id": {"type": "keyword"}}},
        )
    )
    current = managed_index(
        mappings={
            "properties": {
                "id": {"type": "keyword"},
                "server_field": {"type": "date"},
            },
            "_meta": {"server_managed": True},
        },
    )
    client = module_client(response(200, current))

    with pytest.raises(ModuleExit) as exit_result:
        index.run_module(module, client)

    result = exit_result.value.result
    assert result["changed"] is False
    assert result["status"] == 200
    assert result["index"]["settings"]["index"]["uuid"] == "server-managed"
    assert "server_field" in result["index"]["mappings"]["properties"]
    assert result["diff"]["before"] == result["diff"]["after"]
    client.request.assert_called_once()


def test_update_check_mode_predicts_settings_and_mapping_without_mutation():
    module = FakeModule(
        params(
            settings={
                "number_of_shards": 1,
                "refresh_interval": "5s",
            },
            mappings={
                "properties": {
                    "id": {"type": "keyword"},
                    "message": {"type": "text"},
                }
            },
        ),
        check_mode=True,
    )
    current = managed_index(
        settings={
            "index": {
                "number_of_shards": "1",
                "refresh_interval": "1s",
            }
        },
        mappings={"properties": {"id": {"type": "keyword"}}},
    )
    client = module_client(response(200, current))

    with pytest.raises(ModuleExit) as exit_result:
        index.run_module(module, client)

    result = exit_result.value.result
    assert result["changed"] is True
    assert result["diff"]["before"]["settings"] == {
        "number_of_shards": "1",
        "refresh_interval": "1s",
    }
    assert result["diff"]["after"]["settings"]["refresh_interval"] == "5s"
    assert result["diff"]["after"]["mappings"]["properties"]["message"]["type"] == "text"
    client.request.assert_called_once()


def test_update_sends_only_changed_settings_then_mapping_and_refreshes():
    module = FakeModule(
        params(
            settings={
                "number_of_shards": 1,
                "refresh_interval": "5s",
            },
            mappings={
                "properties": {
                    "id": {"type": "keyword"},
                    "message": {"type": "text"},
                }
            },
        )
    )
    before = managed_index(
        settings={
            "index": {
                "number_of_shards": "1",
                "refresh_interval": "1s",
            }
        },
        mappings={"properties": {"id": {"type": "keyword"}}},
    )
    after = managed_index(
        settings={
            "index": {
                "number_of_shards": "1",
                "refresh_interval": "5s",
            }
        },
        mappings={
            "properties": {
                "id": {"type": "keyword"},
                "message": {"type": "text"},
            }
        },
    )
    client = module_client(
        response(200, before),
        response(200, {"acknowledged": True}),
        response(200, {"acknowledged": True}),
        response(200, after),
    )

    with pytest.raises(ModuleExit) as exit_result:
        index.run_module(module, client)

    result = exit_result.value.result
    assert result["changed"] is True
    assert result["index"]["settings"]["index"]["refresh_interval"] == "5s"
    assert client.request.call_args_list[1] == call(
        "phase1%2Findex/_settings",
        method="PUT",
        data={"settings": {"index.refresh_interval": "5s"}},
    )
    assert client.request.call_args_list[2] == call(
        "phase1%2Findex/_mapping",
        method="PUT",
        data=module.params["mappings"],
    )


def test_name_only_returns_read_outcome_without_changes():
    module = FakeModule(params())
    client = module_client(response(200, managed_index()))

    with pytest.raises(ModuleExit) as exit_result:
        index.run_module(module, client)

    result = exit_result.value.result
    assert result["changed"] is False
    assert result["index"]["name"] == "phase1/index"
    assert result["diff"] == {
        "before": {"name": "phase1/index"},
        "after": {"name": "phase1/index"},
    }


def test_delete_check_delete_and_already_absent_behaviors():
    current = managed_index()

    check_module = FakeModule(params(state="absent"), check_mode=True)
    check_client = module_client(response(200, current))
    with pytest.raises(ModuleExit) as check_exit:
        index.run_module(check_module, check_client)
    assert check_exit.value.result["changed"] is True
    assert check_exit.value.result["diff"]["after"] == {}
    check_client.request.assert_called_once()

    delete_module = FakeModule(params(state="absent"))
    delete_client = module_client(
        response(200, current),
        response(200, {"acknowledged": True}),
    )
    with pytest.raises(ModuleExit) as delete_exit:
        index.run_module(delete_module, delete_client)
    assert delete_exit.value.result["changed"] is True
    assert delete_exit.value.result["index"]["name"] == "phase1/index"
    assert delete_client.request.call_args_list[-1] == call(
        "phase1%2Findex",
        method="DELETE",
    )

    absent_module = FakeModule(params(state="absent"))
    absent_client = module_client(response(404, {"error": "missing"}))
    with pytest.raises(ModuleExit) as absent_exit:
        index.run_module(absent_module, absent_client)
    assert absent_exit.value.result["changed"] is False
    assert absent_exit.value.result["index"] is None


def test_api_failure_is_actionable_and_sanitized():
    module = FakeModule(params())
    client = module_client(
        response(
            403,
            {
                "error": "forbidden",
                "api_key": "must-not-leak",
            },
        )
    )

    with pytest.raises(ModuleFailure) as failure:
        index.run_module(module, client)

    assert "read index" in failure.value.result["msg"]
    assert "phase1%2Findex" in failure.value.result["msg"]
    assert failure.value.result["status"] == 403
    assert failure.value.result["response"]["api_key"] == "<redacted>"


def test_malformed_success_response_fails_with_context():
    module = FakeModule(params())
    client = module_client(
        response(200, {"different-index": {"settings": {}, "mappings": {}}})
    )

    with pytest.raises(ModuleFailure) as failure:
        index.run_module(module, client)

    assert "no matching index definition" in failure.value.result["msg"]
    assert failure.value.result["status"] == 200
    assert "different-index" in failure.value.result["response"]


def test_mapping_update_failure_preserves_elasticsearch_error_context():
    module = FakeModule(
        params(mappings={"properties": {"id": {"type": "long"}}})
    )
    client = module_client(
        response(
            200,
            managed_index(
                mappings={"properties": {"id": {"type": "keyword"}}},
            ),
        ),
        response(
            400,
            {
                "error": {
                    "type": "illegal_argument_exception",
                    "reason": "mapper cannot be changed",
                }
            },
        ),
    )

    with pytest.raises(ModuleFailure) as failure:
        index.run_module(module, client)

    assert "update index mapping" in failure.value.result["msg"]
    assert failure.value.result["status"] == 400
    assert (
        failure.value.result["response"]["error"]["type"]
        == "illegal_argument_exception"
    )

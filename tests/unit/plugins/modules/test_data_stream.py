# Copyright (c) 2026, zupersero
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from unittest.mock import Mock, call

import pytest

from ansible_collections.zupersero.elastic.plugins.module_utils.elasticsearch import (
    ElasticsearchResponse,
    FEATURE_MINIMUM_VERSIONS,
)
from ansible_collections.zupersero.elastic.plugins.module_utils.elasticsearch_services.data_stream import (
    DataStreamLifecycleService,
    DataStreamService,
)
from ansible_collections.zupersero.elastic.plugins.modules import (
    data_stream,
    data_stream_lifecycle,
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


def response(status, data=None):
    return ElasticsearchResponse(status=status, data=data, headers={})


def stream_params(**overrides):
    values = {
        "name": "phase1-events",
        "state": "present",
    }
    values.update(overrides)
    return values


def lifecycle_params(**overrides):
    values = {
        "name": "phase1-events",
        "enabled": None,
        "data_retention": None,
        "downsampling": None,
        "replace": False,
        "state": "present",
    }
    values.update(overrides)
    return values


def stream_api(name="phase1-events"):
    return {
        "data_streams": [
            {
                "name": name,
                "timestamp_field": {"name": "@timestamp"},
                "indices": [
                    {
                        "index_name": f".ds-{name}-2026.07.27-000001",
                        "index_uuid": "uuid",
                        "managed_by": "Data stream lifecycle",
                    }
                ],
                "generation": 1,
                "status": "GREEN",
                "template": "phase1-events-template",
                "next_generation_managed_by": "Data stream lifecycle",
                "prefer_ilm": True,
                "hidden": False,
                "system": False,
                "allow_custom_routing": False,
                "replicated": False,
                "rollover_on_write": False,
            }
        ]
    }


def lifecycle_api(
    lifecycle_marker=...,
    name="phase1-events",
    global_retention=None,
):
    candidate = {"name": name}
    if lifecycle_marker is ...:
        candidate["lifecycle"] = {
            "enabled": True,
            "data_retention": "7d",
            "effective_retention": "7d",
            "retention_determined_by": "data_stream_configuration",
            "downsampling": [{"after": "1d", "fixed_interval": "1h"}],
        }
    elif lifecycle_marker is not None:
        candidate["lifecycle"] = lifecycle_marker
    return {
        "global_retention": global_retention
        if global_retention is not None
        else {"default_retention": "30d", "max_retention": "90d"},
        "data_streams": [candidate],
    }


def stream_client(*responses):
    client = Mock()
    client.supports_feature.return_value = True
    client.request.side_effect = responses
    client.data_stream = DataStreamService(client)
    return client


def lifecycle_client(*responses):
    client = Mock()
    client.supports_feature.return_value = True
    client.request.side_effect = responses
    client.data_stream_lifecycle = DataStreamLifecycleService(client)
    return client


def test_argument_specs_features_and_secret_marking():
    stream_spec = data_stream.data_stream_argument_spec()
    lifecycle_spec = data_stream_lifecycle.data_stream_lifecycle_argument_spec()

    assert FEATURE_MINIMUM_VERSIONS["data_stream"] == (7, 9, 0)
    assert FEATURE_MINIMUM_VERSIONS["data_stream_lifecycle"] == (8, 11, 0)
    assert stream_spec["name"] == {"type": "str", "required": True}
    assert stream_spec["state"]["choices"] == ["present", "absent"]
    assert lifecycle_spec["enabled"] == {"type": "bool"}
    assert lifecycle_spec["data_retention"] == {"type": "str"}
    assert lifecycle_spec["downsampling"] == {
        "type": "list",
        "elements": "dict",
        "options": {
            "after": {"type": "str", "required": True},
            "fixed_interval": {"type": "str", "required": True},
        },
    }
    assert lifecycle_spec["replace"] == {"type": "bool", "default": False}
    for spec in (stream_spec, lifecycle_spec):
        assert spec["password"]["no_log"] is True
        assert spec["api_key"]["no_log"] is True
        assert spec["bearer_token"]["no_log"] is True


def test_services_quote_names_unwrap_responses_and_send_typed_requests():
    stream_transport = Mock()
    stream_transport.request.side_effect = [
        response(200, stream_api("phase1/events")),
        response(200, {"acknowledged": True}),
        response(200, {"acknowledged": True}),
    ]
    stream_service = DataStreamService(stream_transport)

    read_response, current_stream = stream_service.get("phase1/events")
    create_response = stream_service.create("phase1/events")
    delete_response = stream_service.delete("phase1/events")

    assert read_response.status == create_response.status == delete_response.status == 200
    assert current_stream["name"] == "phase1/events"
    assert stream_transport.request.call_args_list == [
        call("_data_stream/phase1%2Fevents"),
        call("_data_stream/phase1%2Fevents", method="PUT"),
        call("_data_stream/phase1%2Fevents", method="DELETE"),
    ]

    lifecycle_transport = Mock()
    lifecycle_transport.request.side_effect = [
        response(200, lifecycle_api(name="phase1/events")),
        response(200, {"acknowledged": True}),
        response(200, {"acknowledged": True}),
    ]
    lifecycle_service = DataStreamLifecycleService(lifecycle_transport)

    lifecycle_response, exists, lifecycle, global_retention = lifecycle_service.get(
        "phase1/events"
    )
    put_response = lifecycle_service.create_or_update(
        "phase1/events",
        current=lifecycle,
        desired={"name": "phase1/events", "data_retention": "14d"},
    )
    detach_response = lifecycle_service.delete("phase1/events")

    assert lifecycle_response.status == put_response.status == detach_response.status == 200
    assert exists is True
    assert lifecycle["effective_retention"] == "7d"
    assert global_retention == {
        "default_retention": "30d",
        "max_retention": "90d",
    }
    assert lifecycle_transport.request.call_args_list == [
        call("_data_stream/phase1%2Fevents/_lifecycle"),
        call(
            "_data_stream/phase1%2Fevents/_lifecycle",
            method="PUT",
            data={
                "enabled": True,
                "data_retention": "14d",
                "downsampling": [{"after": "1d", "fixed_interval": "1h"}],
            },
        ),
        call("_data_stream/phase1%2Fevents/_lifecycle", method="DELETE"),
    ]


def test_lifecycle_comparison_preservation_replacement_and_explicit_clear():
    current = lifecycle_api()["data_streams"][0]["lifecycle"]
    current["name"] = "phase1-events"

    unchanged, unchanged_diff = DataStreamLifecycleService.compare(
        current,
        {"name": "phase1-events", "data_retention": "7d"},
    )
    retention_changed, retention_diff = DataStreamLifecycleService.compare(
        current,
        {"name": "phase1-events", "data_retention": "14d"},
    )
    replaced, replacement_diff = DataStreamLifecycleService.compare(
        current,
        {"name": "phase1-events", "enabled": True},
        replace=True,
    )
    cleared, clear_diff = DataStreamLifecycleService.compare(
        {"name": "phase1-events", "enabled": True},
        {"name": "phase1-events", "downsampling": []},
    )

    assert unchanged is False
    assert unchanged_diff["before"] == unchanged_diff["after"]
    assert retention_changed is True
    assert retention_diff["after"]["data_retention"] == "14d"
    assert replaced is True
    assert replacement_diff["after"]["data_retention"] is None
    assert replacement_diff["after"]["downsampling"] is None
    assert cleared is False
    assert clear_diff["before"] == clear_diff["after"] == {"downsampling": []}
    assert DataStreamLifecycleService.payload(
        current,
        {"name": "phase1-events", "data_retention": "14d"},
    ) == {
        "enabled": True,
        "data_retention": "14d",
        "downsampling": [{"after": "1d", "fixed_interval": "1h"}],
    }
    assert DataStreamLifecycleService.payload(
        current,
        {"name": "phase1-events", "enabled": True},
        replace=True,
    ) == {"enabled": True}
    assert DataStreamLifecycleService.payload(
        current,
        {"name": "phase1-events", "downsampling": []},
    ) == {"enabled": True, "data_retention": "7d"}


def test_data_stream_check_create_refresh_and_idempotency():
    check_client = stream_client(response(404, {"error": "missing"}))
    with pytest.raises(ModuleExit) as check_exit:
        data_stream.run_module(
            FakeModule(stream_params(), check_mode=True),
            check_client,
        )
    assert check_exit.value.result["changed"] is True
    assert check_exit.value.result["data_stream"] == {"name": "phase1-events"}
    check_client.request.assert_called_once_with("_data_stream/phase1-events")

    create_client = stream_client(
        response(404, {"error": "missing"}),
        response(200, {"acknowledged": True}),
        response(200, stream_api()),
    )
    with pytest.raises(ModuleExit) as create_exit:
        data_stream.run_module(FakeModule(stream_params()), create_client)
    assert create_exit.value.result["changed"] is True
    assert create_exit.value.result["data_stream"]["generation"] == 1
    assert create_client.request.call_args_list[1] == call(
        "_data_stream/phase1-events",
        method="PUT",
    )

    idempotent_client = stream_client(response(200, stream_api()))
    with pytest.raises(ModuleExit) as idempotent_exit:
        data_stream.run_module(FakeModule(stream_params()), idempotent_client)
    assert idempotent_exit.value.result["changed"] is False
    assert idempotent_exit.value.result["diff"]["before"] == (
        idempotent_exit.value.result["diff"]["after"]
    )


def test_data_stream_delete_check_delete_and_repeated_delete():
    check_client = stream_client(response(200, stream_api()))
    with pytest.raises(ModuleExit) as check_exit:
        data_stream.run_module(
            FakeModule(stream_params(state="absent"), check_mode=True),
            check_client,
        )
    assert check_exit.value.result["changed"] is True
    check_client.request.assert_called_once()

    delete_client = stream_client(
        response(200, stream_api()),
        response(200, {"acknowledged": True}),
    )
    with pytest.raises(ModuleExit) as delete_exit:
        data_stream.run_module(
            FakeModule(stream_params(state="absent")),
            delete_client,
        )
    assert delete_exit.value.result["changed"] is True
    assert delete_client.request.call_args_list[-1] == call(
        "_data_stream/phase1-events",
        method="DELETE",
    )

    absent_client = stream_client(response(404, {"error": "missing"}))
    with pytest.raises(ModuleExit) as absent_exit:
        data_stream.run_module(
            FakeModule(stream_params(state="absent")),
            absent_client,
        )
    assert absent_exit.value.result["changed"] is False
    assert absent_exit.value.result["data_stream"] is None


def test_data_stream_successful_create_requires_observable_refresh():
    client = stream_client(
        response(404, {"error": "missing"}),
        response(200, {"acknowledged": True}),
        response(404, {"error": "still missing", "api_key": "must-not-leak"}),
    )

    with pytest.raises(ModuleFailure) as failure:
        data_stream.run_module(FakeModule(stream_params()), client)

    assert "not observable during refresh" in failure.value.result["msg"]
    assert failure.value.result["mutation_status"] == 200
    assert failure.value.result["status"] == 404
    assert failure.value.result["response"]["api_key"] == "<redacted>"


def test_lifecycle_missing_stream_and_attach_check_mode():
    missing_client = lifecycle_client(response(404, {"error": "missing"}))
    with pytest.raises(ModuleFailure, match="does not exist"):
        data_stream_lifecycle.run_module(
            FakeModule(lifecycle_params(data_retention="7d")),
            missing_client,
        )

    check_client = lifecycle_client(
        response(200, lifecycle_api(lifecycle_marker=None))
    )
    with pytest.raises(ModuleExit) as check_exit:
        data_stream_lifecycle.run_module(
            FakeModule(
                lifecycle_params(
                    data_retention="7d",
                    downsampling=[{"after": "1d", "fixed_interval": "1h"}],
                ),
                check_mode=True,
            ),
            check_client,
        )
    result = check_exit.value.result
    assert result["changed"] is True
    assert result["data_stream_exists"] is True
    assert result["data_stream_lifecycle"]["enabled"] is True
    assert result["global_retention"]["max_retention"] == "90d"
    check_client.request.assert_called_once()


def test_lifecycle_attach_refresh_read_and_idempotency():
    desired = lifecycle_params(
        data_retention="7d",
        downsampling=[{"after": "1d", "fixed_interval": "1h"}],
    )
    attach_client = lifecycle_client(
        response(200, lifecycle_api(lifecycle_marker=None)),
        response(200, {"acknowledged": True}),
        response(200, lifecycle_api()),
    )
    with pytest.raises(ModuleExit) as attach_exit:
        data_stream_lifecycle.run_module(FakeModule(desired), attach_client)
    assert attach_exit.value.result["changed"] is True
    assert (
        attach_exit.value.result["data_stream_lifecycle"]["effective_retention"]
        == "7d"
    )
    assert attach_client.request.call_args_list[1] == call(
        "_data_stream/phase1-events/_lifecycle",
        method="PUT",
        data={
            "data_retention": "7d",
            "downsampling": [{"after": "1d", "fixed_interval": "1h"}],
        },
    )

    read_client = lifecycle_client(response(200, lifecycle_api()))
    with pytest.raises(ModuleExit) as read_exit:
        data_stream_lifecycle.run_module(
            FakeModule(lifecycle_params()),
            read_client,
        )
    assert read_exit.value.result["changed"] is False
    assert read_exit.value.result["data_stream_lifecycle"]["enabled"] is True

    idempotent_client = lifecycle_client(response(200, lifecycle_api()))
    with pytest.raises(ModuleExit) as idempotent_exit:
        data_stream_lifecycle.run_module(FakeModule(desired), idempotent_client)
    assert idempotent_exit.value.result["changed"] is False
    assert idempotent_exit.value.result["diff"]["before"] == (
        idempotent_exit.value.result["diff"]["after"]
    )


def test_lifecycle_partial_update_preserves_omitted_fields():
    desired = lifecycle_params(data_retention="14d")
    check_client = lifecycle_client(response(200, lifecycle_api()))
    with pytest.raises(ModuleExit) as check_exit:
        data_stream_lifecycle.run_module(
            FakeModule(desired, check_mode=True),
            check_client,
        )
    predicted = check_exit.value.result["data_stream_lifecycle"]
    assert predicted["data_retention"] == "14d"
    assert predicted["downsampling"] == [{"after": "1d", "fixed_interval": "1h"}]
    assert "effective_retention" not in predicted
    check_client.request.assert_called_once()

    refreshed = lifecycle_api()
    refreshed["data_streams"][0]["lifecycle"]["data_retention"] = "14d"
    refreshed["data_streams"][0]["lifecycle"]["effective_retention"] = "14d"
    update_client = lifecycle_client(
        response(200, lifecycle_api()),
        response(200, {"acknowledged": True}),
        response(200, refreshed),
    )
    with pytest.raises(ModuleExit) as update_exit:
        data_stream_lifecycle.run_module(FakeModule(desired), update_client)
    assert update_exit.value.result["changed"] is True
    assert update_client.request.call_args_list[1].kwargs["data"] == {
        "enabled": True,
        "data_retention": "14d",
        "downsampling": [{"after": "1d", "fixed_interval": "1h"}],
    }


def test_lifecycle_authoritative_replace_clears_omitted_configuration():
    desired = lifecycle_params(replace=True, enabled=False)
    check_client = lifecycle_client(response(200, lifecycle_api()))
    with pytest.raises(ModuleExit) as check_exit:
        data_stream_lifecycle.run_module(
            FakeModule(desired, check_mode=True),
            check_client,
        )
    predicted = check_exit.value.result["data_stream_lifecycle"]
    assert predicted == {"enabled": False, "name": "phase1-events"}
    assert check_exit.value.result["diff"]["after"]["data_retention"] is None
    assert check_exit.value.result["diff"]["after"]["downsampling"] is None

    replaced_api = lifecycle_api(lifecycle_marker={"enabled": False})
    replace_client = lifecycle_client(
        response(200, lifecycle_api()),
        response(200, {"acknowledged": True}),
        response(200, replaced_api),
    )
    with pytest.raises(ModuleExit) as replace_exit:
        data_stream_lifecycle.run_module(FakeModule(desired), replace_client)
    assert replace_exit.value.result["changed"] is True
    assert replace_exit.value.result["data_stream_lifecycle"] == {
        "enabled": False,
        "name": "phase1-events",
    }
    assert replace_client.request.call_args_list[1].kwargs["data"] == {
        "enabled": False
    }

    idempotent_client = lifecycle_client(response(200, replaced_api))
    with pytest.raises(ModuleExit) as idempotent_exit:
        data_stream_lifecycle.run_module(FakeModule(desired), idempotent_client)
    assert idempotent_exit.value.result["changed"] is False


def test_lifecycle_detach_check_detach_and_repeated_detach_preserve_stream():
    check_client = lifecycle_client(response(200, lifecycle_api()))
    with pytest.raises(ModuleExit) as check_exit:
        data_stream_lifecycle.run_module(
            FakeModule(lifecycle_params(state="absent"), check_mode=True),
            check_client,
        )
    assert check_exit.value.result["changed"] is True
    assert check_exit.value.result["data_stream_lifecycle"] is None
    assert check_exit.value.result["data_stream_exists"] is True

    detach_client = lifecycle_client(
        response(200, lifecycle_api()),
        response(200, {"acknowledged": True}),
        response(
            200,
            lifecycle_api(
                lifecycle_marker=None,
                global_retention={"max_retention": "120d"},
            ),
        ),
    )
    with pytest.raises(ModuleExit) as detach_exit:
        data_stream_lifecycle.run_module(
            FakeModule(lifecycle_params(state="absent")),
            detach_client,
        )
    assert detach_exit.value.result["changed"] is True
    assert detach_exit.value.result["data_stream_lifecycle"] is None
    assert detach_exit.value.result["data_stream_exists"] is True
    assert detach_exit.value.result["global_retention"] == {
        "max_retention": "120d"
    }
    assert detach_client.request.call_args_list[1] == call(
        "_data_stream/phase1-events/_lifecycle",
        method="DELETE",
    )
    assert detach_client.request.call_args_list[2] == call(
        "_data_stream/phase1-events/_lifecycle"
    )

    absent_client = lifecycle_client(
        response(200, lifecycle_api(lifecycle_marker=None))
    )
    with pytest.raises(ModuleExit) as absent_exit:
        data_stream_lifecycle.run_module(
            FakeModule(lifecycle_params(state="absent")),
            absent_client,
        )
    assert absent_exit.value.result["changed"] is False
    assert absent_exit.value.result["data_stream_exists"] is True


def test_lifecycle_successful_detach_requires_absent_attachment_and_stream():
    lingering_client = lifecycle_client(
        response(200, lifecycle_api()),
        response(200, {"acknowledged": True}),
        response(200, lifecycle_api()),
    )
    with pytest.raises(ModuleFailure) as lingering_failure:
        data_stream_lifecycle.run_module(
            FakeModule(lifecycle_params(state="absent")),
            lingering_client,
        )
    assert "attachment remained observable" in lingering_failure.value.result["msg"]
    assert lingering_failure.value.result["mutation_status"] == 200
    assert lingering_failure.value.result["status"] == 200

    missing_stream_client = lifecycle_client(
        response(200, lifecycle_api()),
        response(200, {"acknowledged": True}),
        response(
            404,
            {"error": "stream disappeared", "api_key": "must-not-leak"},
        ),
    )
    with pytest.raises(ModuleFailure) as missing_failure:
        data_stream_lifecycle.run_module(
            FakeModule(lifecycle_params(state="absent")),
            missing_stream_client,
        )
    assert "data stream was not observable" in missing_failure.value.result["msg"]
    assert missing_failure.value.result["mutation_status"] == 200
    assert missing_failure.value.result["status"] == 404
    assert missing_failure.value.result["response"]["api_key"] == "<redacted>"


def test_version_api_and_malformed_response_failures_are_sanitized():
    old_stream_client = stream_client()
    old_stream_client.supports_feature.return_value = False
    with pytest.raises(ModuleFailure, match="7.9.0 or newer"):
        data_stream.run_module(FakeModule(stream_params()), old_stream_client)
    old_stream_client.request.assert_not_called()

    old_lifecycle_client = lifecycle_client()
    old_lifecycle_client.supports_feature.return_value = False
    with pytest.raises(ModuleFailure, match="8.11.0 or newer"):
        data_stream_lifecycle.run_module(
            FakeModule(lifecycle_params()),
            old_lifecycle_client,
        )
    old_lifecycle_client.request.assert_not_called()

    failure_client = lifecycle_client(
        response(
            403,
            {
                "error": "forbidden",
                "api_key": "must-not-leak",
                "token": "must-not-leak",
            },
        )
    )
    with pytest.raises(ModuleFailure) as failure:
        data_stream_lifecycle.run_module(
            FakeModule(lifecycle_params()),
            failure_client,
        )
    assert "read data stream lifecycle" in failure.value.result["msg"]
    assert failure.value.result["response"]["api_key"] == "<redacted>"
    assert failure.value.result["response"]["token"] == "<redacted>"

    malformed_stream_client = stream_client(
        response(200, {"data_streams": [{"name": "different"}]})
    )
    with pytest.raises(ModuleFailure, match="no matching data stream definition"):
        data_stream.run_module(
            FakeModule(stream_params()),
            malformed_stream_client,
        )

    malformed_lifecycle_client = lifecycle_client(
        response(
            200,
            {
                "global_retention": {},
                "data_streams": [{"name": "different"}],
                "password": "must-not-leak",
            },
        )
    )
    with pytest.raises(ModuleFailure) as malformed:
        data_stream_lifecycle.run_module(
            FakeModule(lifecycle_params()),
            malformed_lifecycle_client,
        )
    assert "no matching data stream" in malformed.value.result["msg"]
    assert malformed.value.result["response"]["password"] == "<redacted>"


def test_lifecycle_update_error_preserves_actionable_sanitized_context():
    client = lifecycle_client(
        response(200, lifecycle_api()),
        response(
            400,
            {
                "error": {
                    "type": "illegal_argument_exception",
                    "reason": "invalid data retention",
                },
                "api_key": "must-not-leak",
            },
        ),
    )
    with pytest.raises(ModuleFailure) as failure:
        data_stream_lifecycle.run_module(
            FakeModule(lifecycle_params(data_retention="not-a-duration")),
            client,
        )
    assert "update data stream lifecycle" in failure.value.result["msg"]
    assert failure.value.result["status"] == 400
    assert failure.value.result["response"]["api_key"] == "<redacted>"
    assert (
        failure.value.result["response"]["error"]["type"]
        == "illegal_argument_exception"
    )


def test_lifecycle_successful_mutations_require_observable_refresh():
    attach_client = lifecycle_client(
        response(200, lifecycle_api(lifecycle_marker=None)),
        response(200, {"acknowledged": True}),
        response(200, lifecycle_api(lifecycle_marker=None)),
    )
    with pytest.raises(ModuleFailure) as attach_failure:
        data_stream_lifecycle.run_module(
            FakeModule(lifecycle_params(data_retention="7d")),
            attach_client,
        )
    assert "no attachment was observable" in attach_failure.value.result["msg"]
    assert attach_failure.value.result["mutation_status"] == 200

    update_client = lifecycle_client(
        response(200, lifecycle_api()),
        response(200, {"acknowledged": True}),
        response(
            404,
            {"error": "stream disappeared", "token": "must-not-leak"},
        ),
    )
    with pytest.raises(ModuleFailure) as update_failure:
        data_stream_lifecycle.run_module(
            FakeModule(lifecycle_params(data_retention="14d")),
            update_client,
        )
    assert "no attachment was observable" in update_failure.value.result["msg"]
    assert update_failure.value.result["status"] == 404
    assert update_failure.value.result["response"]["token"] == "<redacted>"

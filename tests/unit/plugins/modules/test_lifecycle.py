# Copyright (c) 2026, zupersero
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from unittest.mock import Mock, call

import pytest

from ansible_collections.zupersero.elastic.plugins.module_utils.elasticsearch import (
    ElasticsearchResponse,
)
from ansible_collections.zupersero.elastic.plugins.module_utils.elasticsearch_services.lifecycle import (
    LifecycleService,
    validate_lifecycle_phases,
)
from ansible_collections.zupersero.elastic.plugins.modules import (
    index_lifecycle_policy,
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


def params(**overrides):
    values = {
        "name": "phase1/lifecycle",
        "phases": None,
        "metadata": None,
        "replace": False,
        "state": "present",
    }
    values.update(overrides)
    return values


def policy_api(body=None, name="phase1/lifecycle"):
    return {
        name: {
            "version": 2,
            "modified_date": "2026-07-27T12:00:00.000Z",
            "policy": body
            or {
                "phases": {
                    "hot": {
                        "min_age": "0ms",
                        "actions": {"rollover": {"max_docs": 1000}},
                    },
                    "delete": {
                        "min_age": "30d",
                        "actions": {
                            "delete": {"delete_searchable_snapshot": True}
                        },
                    },
                },
                "_meta": {"owner": "platform"},
            },
            "in_use_by": {
                "indices": [],
                "data_streams": [],
                "composable_templates": [],
            },
        }
    }


def module_client(*responses):
    client = Mock()
    client.request.side_effect = responses
    client.lifecycle = LifecycleService(client)
    return client


def test_argument_spec_and_phase_envelope_validation():
    spec = index_lifecycle_policy.lifecycle_policy_argument_spec()

    assert spec["name"] == {"type": "str", "required": True}
    assert spec["phases"] == {"type": "dict"}
    assert spec["metadata"] == {"type": "dict"}
    assert spec["replace"] == {"type": "bool", "default": False}
    assert spec["state"]["choices"] == ["present", "absent"]
    assert spec["password"]["no_log"] is True
    validate_lifecycle_phases(
        {
            "hot": {"actions": {"rollover": {"max_docs": 1000}}},
            "delete": {"min_age": "30d", "actions": {"delete": {}}},
        }
    )

    with pytest.raises(ValueError, match="unsupported phase names"):
        validate_lifecycle_phases({"archive": {"actions": {}}})
    with pytest.raises(ValueError, match="actions.rollover must be a dictionary"):
        validate_lifecycle_phases({"hot": {"actions": {"rollover": "1d"}}})


def test_service_quotes_unwraps_and_sends_typed_requests():
    transport = Mock()
    transport.request.side_effect = [
        response(200, policy_api()),
        response(200, {"acknowledged": True}),
        response(200, {"acknowledged": True}),
    ]
    service = LifecycleService(transport)

    read_response, current = service.get("phase1/lifecycle")
    update_response = service.create_or_update(
        "phase1/lifecycle",
        current=current,
        desired={
            "name": "phase1/lifecycle",
            "phases": {"warm": {"actions": {"forcemerge": {"max_num_segments": 1}}}},
        },
    )
    delete_response = service.delete("phase1/lifecycle")

    assert read_response.status == update_response.status == delete_response.status == 200
    assert current["name"] == "phase1/lifecycle"
    assert current["version"] == 2
    assert transport.request.call_args_list == [
        call("_ilm/policy/phase1%2Flifecycle"),
        call(
            "_ilm/policy/phase1%2Flifecycle",
            method="PUT",
            data={
                "policy": {
                    "phases": {
                        "hot": {
                            "min_age": "0ms",
                            "actions": {"rollover": {"max_docs": 1000}},
                        },
                        "warm": {
                            "actions": {
                                "forcemerge": {"max_num_segments": 1}
                            }
                        },
                        "delete": {
                            "min_age": "30d",
                            "actions": {
                                "delete": {"delete_searchable_snapshot": True}
                            },
                        },
                    },
                    "_meta": {"owner": "platform"},
                }
            },
        ),
        call("_ilm/policy/phase1%2Flifecycle", method="DELETE"),
    ]


def test_service_comparison_handles_server_defaults_and_authoritative_replace():
    current_policy = {
        "name": "phase1/lifecycle",
        "phases": {
            "hot": {
                "min_age": "0ms",
                "actions": {"rollover": {"max_docs": 1000}},
            },
            "delete": {
                "min_age": "30d",
                "actions": {"delete": {"delete_searchable_snapshot": True}},
            },
        },
        "_meta": {"owner": "platform"},
        "version": 4,
        "modified_date": "server",
        "in_use_by": {"indices": []},
    }

    changed, diff = LifecycleService.compare(
        current_policy,
        {
            "name": "phase1/lifecycle",
            "phases": {
                "hot": {"actions": {"rollover": {"max_docs": 1000}}},
                "delete": {
                    "min_age": "30d",
                    "actions": {"delete": {}},
                },
            },
            "_meta": {"owner": "platform"},
        },
        replace=True,
    )
    removal_changed, removal_diff = LifecycleService.compare(
        current_policy,
        {
            "name": "phase1/lifecycle",
            "phases": {"delete": {"min_age": "30d", "actions": {"delete": {}}}},
            "_meta": {},
        },
        replace=True,
    )

    assert changed is False
    assert diff["before"] == diff["after"]
    assert removal_changed is True
    assert removal_diff["before"] != removal_diff["after"]


def test_create_requires_phases_and_check_mode_is_non_mutating():
    missing_module = FakeModule(params())
    missing_client = module_client(response(404, {"error": "missing"}))
    with pytest.raises(ModuleFailure, match="phases is required"):
        index_lifecycle_policy.run_module(missing_module, missing_client)

    module = FakeModule(
        params(
            phases={
                "hot": {"actions": {"rollover": {"max_docs": 1000}}},
                "delete": {"min_age": "30d", "actions": {"delete": {}}},
            },
            metadata={"owner": "platform"},
        ),
        check_mode=True,
    )
    client = module_client(response(404, {"error": "missing"}))
    with pytest.raises(ModuleExit) as exit_result:
        index_lifecycle_policy.run_module(module, client)

    result = exit_result.value.result
    assert result["changed"] is True
    assert result["status"] == 404
    assert result["lifecycle_policy"]["name"] == "phase1/lifecycle"
    assert result["diff"]["before"] == {}
    client.request.assert_called_once_with("_ilm/policy/phase1%2Flifecycle")


def test_create_refreshes_managed_policy_and_existing_policy_is_idempotent():
    desired = params(
        phases={
            "hot": {"actions": {"rollover": {"max_docs": 1000}}},
            "delete": {"min_age": "30d", "actions": {"delete": {}}},
        },
        metadata={"owner": "platform"},
    )
    create_client = module_client(
        response(404, {"error": "missing"}),
        response(200, {"acknowledged": True}),
        response(200, policy_api()),
    )
    with pytest.raises(ModuleExit) as create_exit:
        index_lifecycle_policy.run_module(FakeModule(desired), create_client)

    assert create_exit.value.result["changed"] is True
    assert create_exit.value.result["lifecycle_policy"]["version"] == 2
    assert create_client.request.call_args_list[1] == call(
        "_ilm/policy/phase1%2Flifecycle",
        method="PUT",
        data={
            "policy": {
                "phases": desired["phases"],
                "_meta": {"owner": "platform"},
            }
        },
    )

    idempotent_client = module_client(response(200, policy_api()))
    with pytest.raises(ModuleExit) as idempotent_exit:
        index_lifecycle_policy.run_module(
            FakeModule(desired),
            idempotent_client,
        )
    assert idempotent_exit.value.result["changed"] is False
    assert idempotent_exit.value.result["diff"]["before"] == (
        idempotent_exit.value.result["diff"]["after"]
    )


def test_partial_update_check_predicts_preserved_state_without_mutation():
    module = FakeModule(
        params(
            phases={
                "warm": {
                    "min_age": "1d",
                    "actions": {"forcemerge": {"max_num_segments": 1}},
                }
            },
            metadata={"purpose": "integration"},
        ),
        check_mode=True,
    )
    client = module_client(response(200, policy_api()))

    with pytest.raises(ModuleExit) as exit_result:
        index_lifecycle_policy.run_module(module, client)

    predicted = exit_result.value.result["lifecycle_policy"]
    assert exit_result.value.result["changed"] is True
    assert predicted["phases"]["hot"]["actions"]["rollover"]["max_docs"] == 1000
    assert predicted["phases"]["warm"]["min_age"] == "1d"
    assert predicted["_meta"] == {
        "owner": "platform",
        "purpose": "integration",
    }
    assert "version" not in predicted
    client.request.assert_called_once()


def test_partial_update_sends_preserved_payload_and_refreshes():
    module = FakeModule(
        params(
            phases={"delete": {"min_age": "14d"}},
            metadata={"purpose": "integration"},
        )
    )
    after = policy_api()
    after["phase1/lifecycle"]["version"] = 3
    after["phase1/lifecycle"]["policy"]["phases"]["delete"]["min_age"] = "14d"
    after["phase1/lifecycle"]["policy"]["_meta"]["purpose"] = "integration"
    client = module_client(
        response(200, policy_api()),
        response(200, {"acknowledged": True}),
        response(200, after),
    )

    with pytest.raises(ModuleExit) as exit_result:
        index_lifecycle_policy.run_module(module, client)

    result = exit_result.value.result
    assert result["changed"] is True
    assert result["lifecycle_policy"]["version"] == 3
    payload = client.request.call_args_list[1].kwargs["data"]["policy"]
    assert payload["phases"]["hot"]["actions"]["rollover"]["max_docs"] == 1000
    assert payload["phases"]["delete"]["min_age"] == "14d"
    assert payload["_meta"] == {
        "owner": "platform",
        "purpose": "integration",
    }


def test_replace_check_clears_omitted_state_and_requires_phases():
    missing_client = module_client(response(200, policy_api()))
    with pytest.raises(ModuleFailure, match="phases is required"):
        index_lifecycle_policy.run_module(
            FakeModule(params(replace=True)),
            missing_client,
        )

    module = FakeModule(
        params(
            replace=True,
            phases={"delete": {"min_age": "7d", "actions": {"delete": {}}}},
            metadata={},
        ),
        check_mode=True,
    )
    client = module_client(response(200, policy_api()))
    with pytest.raises(ModuleExit) as exit_result:
        index_lifecycle_policy.run_module(module, client)

    predicted = exit_result.value.result["lifecycle_policy"]
    assert predicted["phases"] == module.params["phases"]
    assert predicted["_meta"] == {}
    assert "hot" not in predicted["phases"]


def test_read_delete_check_delete_and_repeated_delete():
    read_client = module_client(response(200, policy_api()))
    with pytest.raises(ModuleExit) as read_exit:
        index_lifecycle_policy.run_module(FakeModule(params()), read_client)
    assert read_exit.value.result["changed"] is False
    assert read_exit.value.result["lifecycle_policy"]["version"] == 2

    check_client = module_client(response(200, policy_api()))
    with pytest.raises(ModuleExit) as check_exit:
        index_lifecycle_policy.run_module(
            FakeModule(params(state="absent"), check_mode=True),
            check_client,
        )
    assert check_exit.value.result["changed"] is True
    check_client.request.assert_called_once()

    delete_client = module_client(
        response(200, policy_api()),
        response(200, {"acknowledged": True}),
    )
    with pytest.raises(ModuleExit) as delete_exit:
        index_lifecycle_policy.run_module(
            FakeModule(params(state="absent")),
            delete_client,
        )
    assert delete_exit.value.result["changed"] is True
    assert delete_client.request.call_args_list[-1] == call(
        "_ilm/policy/phase1%2Flifecycle",
        method="DELETE",
    )

    absent_client = module_client(response(404, {"error": "missing"}))
    with pytest.raises(ModuleExit) as absent_exit:
        index_lifecycle_policy.run_module(
            FakeModule(params(state="absent")),
            absent_client,
        )
    assert absent_exit.value.result["changed"] is False
    assert absent_exit.value.result["lifecycle_policy"] is None


def test_api_errors_malformed_responses_and_validation_are_sanitized():
    failure_client = module_client(
        response(403, {"error": "forbidden", "api_key": "must-not-leak"})
    )
    with pytest.raises(ModuleFailure) as failure:
        index_lifecycle_policy.run_module(FakeModule(params()), failure_client)
    assert "read index lifecycle policy" in failure.value.result["msg"]
    assert failure.value.result["response"]["api_key"] == "<redacted>"

    malformed_client = module_client(
        response(200, {"different-policy": {"policy": {"phases": {}}}})
    )
    with pytest.raises(ModuleFailure) as malformed:
        index_lifecycle_policy.run_module(FakeModule(params()), malformed_client)
    assert "no matching policy definition" in malformed.value.result["msg"]

    validation_client = module_client()
    with pytest.raises(ModuleFailure, match="unsupported fields"):
        index_lifecycle_policy.run_module(
            FakeModule(params(phases={"hot": {"unknown": {}}})),
            validation_client,
        )
    validation_client.request.assert_not_called()


def test_update_failure_preserves_sanitized_elasticsearch_context():
    module = FakeModule(
        params(phases={"delete": {"min_age": "not-a-duration"}})
    )
    client = module_client(
        response(200, policy_api()),
        response(
            400,
            {
                "error": {
                    "type": "illegal_argument_exception",
                    "reason": "invalid phase definition",
                },
                "token": "must-not-leak",
            },
        ),
    )

    with pytest.raises(ModuleFailure) as failure:
        index_lifecycle_policy.run_module(module, client)

    assert "update index lifecycle policy" in failure.value.result["msg"]
    assert failure.value.result["status"] == 400
    assert failure.value.result["response"]["token"] == "<redacted>"
    assert (
        failure.value.result["response"]["error"]["type"]
        == "illegal_argument_exception"
    )

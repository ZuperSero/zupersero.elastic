# Copyright (c) 2026, zupersero
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest.mock import Mock

import pytest

from ansible_collections.zupersero.elastic.plugins.module_utils.elasticsearch import (
    ElasticsearchResponse,
)
from ansible_collections.zupersero.elastic.plugins.module_utils.elasticsearch_services.role import (
    RoleService,
)
from ansible_collections.zupersero.elastic.plugins.modules import user_role


def test_normalize_role_sorts_unordered_privileges_and_preserves_security_fields():
    current = {
        "name": "reader",
        "cluster": ["monitor", "manage_ilm"],
        "indices": [{"names": ["b-*", "a-*"], "privileges": ["view_index_metadata", "read"]}],
        "run_as": ["z", "a"],
        "metadata": {"owner": "ops"},
    }
    changed, diff = RoleService.compare(
        current,
        {
            "cluster": ["manage_ilm", "monitor"],
            "indices": [{"names": ["a-*", "b-*"], "privileges": ["read", "view_index_metadata"]}],
            "run_as": ["a", "z"],
        },
    )
    assert changed is False
    assert diff["before"]["metadata"] == {"owner": "ops"}


def test_normalize_role_accepts_api_camel_case_fields():
    normalized = RoleService.payload(
        {"name": "reader", "runAs": ["analyst"], "transientMetadata": {"enabled": True}},
        {},
    )
    assert normalized["run_as"] == ["analyst"]
    assert normalized["transient_metadata"] == {"enabled": True}


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
        "name": "data_reader",
        "cluster": None,
        "indices": None,
        "applications": None,
        "run_as": None,
        "metadata": None,
        "transient_metadata": None,
        "global_privileges": None,
        "state": "present",
    }
    values.update(overrides)
    return values


def role_api(body=None, name="data_reader"):
    return {
        name: body
        or {
            "cluster": ["monitor"],
            "indices": [{"names": ["logs-*"], "privileges": ["read"]}],
            "applications": [],
            "run_as": ["elastic"],
            "metadata": {"owner": "qa"},
            "transient_metadata": {"enabled": True},
        }
    }


def client(*responses):
    transport = Mock()
    transport.request.side_effect = responses
    transport.role = RoleService(transport)
    return transport


def test_create_check_mode_is_non_mutating_and_predicts_fields():
    module = FakeModule(
        params(cluster=["monitor"], run_as=["elastic"], metadata={"owner": "qa"}),
        check_mode=True,
    )
    transport = client(response(404, {}))
    with pytest.raises(ModuleExit) as result:
        user_role.run_module(module, transport)
    assert result.value.result["changed"] is True
    predicted = result.value.result["role"]
    assert predicted["name"] == "data_reader"
    assert predicted["cluster"] == ["monitor"]
    assert predicted["indices"] == []
    assert predicted["metadata"] == {"owner": "qa"}
    transport.request.assert_called_once_with("_security/role/data_reader")


def test_create_then_idempotent_rerun():
    create_client = client(
        response(404, {}),
        response(200, {}),
        response(200, role_api()),
    )
    with pytest.raises(ModuleExit) as created:
        user_role.run_module(
            FakeModule(
                params(
                    cluster=["monitor"],
                    indices=[{"names": ["logs-*"], "privileges": ["read"]}],
                    run_as=["elastic"],
                    metadata={"owner": "qa"},
                )
            ),
            create_client,
        )
    assert created.value.result["changed"] is True

    idempotent_client = client(response(200, role_api()))
    with pytest.raises(ModuleExit) as unchanged:
        user_role.run_module(
            FakeModule(params(cluster=["monitor"], run_as=["elastic"])),
            idempotent_client,
        )
    assert unchanged.value.result["changed"] is False


def test_update_ignores_list_reordering():
    reordered_client = client(response(200, role_api()))
    with pytest.raises(ModuleExit) as result:
        user_role.run_module(
            FakeModule(
                params(
                    indices=[{"names": ["logs-*"], "privileges": ["read"]}],
                    cluster=["monitor"],
                )
            ),
            reordered_client,
        )
    assert result.value.result["changed"] is False


def test_partial_update_check_mode_predicts_preserved_fields_without_mutation():
    module = FakeModule(params(metadata={"owner": "platform"}), check_mode=True)
    transport = client(response(200, role_api()))
    with pytest.raises(ModuleExit) as result:
        user_role.run_module(module, transport)
    predicted = result.value.result["role"]
    assert predicted["metadata"] == {"owner": "platform"}
    assert predicted["cluster"] == ["monitor"]
    assert predicted["run_as"] == ["elastic"]
    transport.request.assert_called_once()


def test_update_detects_real_changes():
    after = role_api()
    after["data_reader"]["cluster"] = ["monitor", "manage_own_api_key"]
    update_client = client(
        response(200, role_api()),
        response(200, {}),
        response(200, after),
    )
    with pytest.raises(ModuleExit) as result:
        user_role.run_module(
            FakeModule(params(cluster=["monitor", "manage_own_api_key"])),
            update_client,
        )
    assert result.value.result["changed"] is True
    put_call = update_client.request.call_args_list[1]
    assert sorted(put_call.kwargs["data"]["cluster"]) == ["manage_own_api_key", "monitor"]


def test_delete_lifecycle_and_idempotent_absent():
    delete_client = client(response(200, role_api()), response(200, {}))
    with pytest.raises(ModuleExit) as deleted:
        user_role.run_module(FakeModule(params(state="absent")), delete_client)
    assert deleted.value.result["changed"] is True
    assert deleted.value.result["role"]["name"] == "data_reader"

    absent_client = client(response(404, {}))
    with pytest.raises(ModuleExit) as absent:
        user_role.run_module(FakeModule(params(state="absent")), absent_client)
    assert absent.value.result["changed"] is False
    assert absent.value.result["role"] is None


def test_delete_check_mode_is_non_mutating():
    transport = client(response(200, role_api()))
    with pytest.raises(ModuleExit) as result:
        user_role.run_module(FakeModule(params(state="absent"), check_mode=True), transport)
    assert result.value.result["changed"] is True
    transport.request.assert_called_once()


def test_read_failure_is_sanitized():
    with pytest.raises(ModuleFailure) as failure:
        user_role.run_module(
            FakeModule(params()),
            client(response(403, {"error": "forbidden", "token": "secret"})),
        )
    assert "read role" in failure.value.result["msg"]
    assert failure.value.result["response"]["token"] == "<redacted>"

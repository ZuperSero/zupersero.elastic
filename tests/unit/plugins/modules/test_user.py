# Copyright (c) 2026, zupersero
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest.mock import Mock

import pytest

from ansible_collections.zupersero.elastic.plugins.module_utils.elasticsearch import (
    ElasticsearchResponse,
)
from ansible_collections.zupersero.elastic.plugins.module_utils.elasticsearch_services.user import (
    UserService,
)
from ansible_collections.zupersero.elastic.plugins.modules import user


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
        "username": "example_user",
        "password": None,
        "password_hash": None,
        "roles": None,
        "full_name": None,
        "email": None,
        "metadata": None,
        "enabled": None,
        "update_password": "on_create",
        "state": "present",
    }
    values.update(overrides)
    return values


def user_api(body=None, name="example_user"):
    return {
        name: body
        or {
            "roles": ["superuser"],
            "full_name": "Example User",
            "email": "example@example.com",
            "metadata": {"owner": "qa"},
            "enabled": True,
        }
    }


def client(*responses):
    transport = Mock()
    transport.request.side_effect = responses
    transport.user = UserService(transport)
    return transport


def test_create_requires_password_or_password_hash():
    with pytest.raises(ModuleFailure, match="requires either password or password_hash"):
        user.run_module(FakeModule(params()), client(response(404, {})))


def test_create_check_mode_is_non_mutating_and_predicts_fields():
    module = FakeModule(
        params(password="s3cret", roles=["superuser"], metadata={"owner": "qa"}),
        check_mode=True,
    )
    transport = client(response(404, {}))
    with pytest.raises(ModuleExit) as result:
        user.run_module(module, transport)
    assert result.value.result["changed"] is True
    assert result.value.result["user"]["username"] == "example_user"
    assert result.value.result["user"]["roles"] == ["superuser"]
    assert result.value.result["user"]["metadata"]["owner"] == "qa"
    assert "password" not in result.value.result["user"]
    transport.request.assert_called_once_with("_security/user/example_user")


def test_create_then_idempotent_rerun():
    create_client = client(
        response(404, {}),
        response(200, {}),
        response(200, user_api()),
    )
    with pytest.raises(ModuleExit) as created:
        user.run_module(
            FakeModule(
                params(
                    password="s3cret",
                    roles=["superuser"],
                    full_name="Example User",
                    email="example@example.com",
                    metadata={"owner": "qa"},
                    enabled=True,
                )
            ),
            create_client,
        )
    assert created.value.result["changed"] is True
    put_call = create_client.request.call_args_list[1]
    assert put_call.kwargs["data"]["password"] == "s3cret"
    assert put_call.kwargs["data"]["roles"] == ["superuser"]

    idempotent_client = client(response(200, user_api()))
    with pytest.raises(ModuleExit) as unchanged:
        user.run_module(FakeModule(params(username="example_user")), idempotent_client)
    assert unchanged.value.result["changed"] is False
    assert unchanged.value.result["user"]["email"] == "example@example.com"


def test_partial_update_check_mode_predicts_preserved_fields_without_mutation():
    module = FakeModule(params(email="updated@example.com"), check_mode=True)
    transport = client(response(200, user_api()))
    with pytest.raises(ModuleExit) as result:
        user.run_module(module, transport)
    predicted = result.value.result["user"]
    assert predicted["email"] == "updated@example.com"
    assert predicted["roles"] == ["superuser"]
    assert predicted["metadata"] == {"owner": "qa"}
    transport.request.assert_called_once()


def test_password_rotation_forces_change_without_other_diffs():
    update_client = client(
        response(200, user_api()),
        response(200, {}),
        response(200, user_api()),
    )
    with pytest.raises(ModuleExit) as result:
        user.run_module(
            FakeModule(params(password="newpass", update_password="always")),
            update_client,
        )
    assert result.value.result["changed"] is True
    put_call = update_client.request.call_args_list[1]
    assert put_call.kwargs["data"]["password"] == "newpass"
    assert put_call.kwargs["data"]["roles"] == ["superuser"]


def test_password_not_applied_on_update_without_always():
    # Same password supplied but update_password stays on_create: no-op update.
    idempotent_client = client(response(200, user_api()))
    with pytest.raises(ModuleExit) as result:
        user.run_module(
            FakeModule(params(password="ignored-on-update")),
            idempotent_client,
        )
    assert result.value.result["changed"] is False
    idempotent_client.request.assert_called_once()


def test_delete_lifecycle_and_idempotent_absent():
    delete_client = client(response(200, user_api()), response(200, {}))
    with pytest.raises(ModuleExit) as deleted:
        user.run_module(FakeModule(params(state="absent")), delete_client)
    assert deleted.value.result["changed"] is True
    assert deleted.value.result["user"]["username"] == "example_user"

    absent_client = client(response(404, {}))
    with pytest.raises(ModuleExit) as absent:
        user.run_module(FakeModule(params(state="absent")), absent_client)
    assert absent.value.result["changed"] is False
    assert absent.value.result["user"] is None


def test_delete_check_mode_is_non_mutating():
    transport = client(response(200, user_api()))
    with pytest.raises(ModuleExit) as result:
        user.run_module(FakeModule(params(state="absent"), check_mode=True), transport)
    assert result.value.result["changed"] is True
    transport.request.assert_called_once()


def test_read_failure_is_sanitized():
    with pytest.raises(ModuleFailure) as failure:
        user.run_module(
            FakeModule(params()),
            client(response(403, {"error": "forbidden", "token": "secret"})),
        )
    assert "read user" in failure.value.result["msg"]
    assert failure.value.result["response"]["token"] == "<redacted>"

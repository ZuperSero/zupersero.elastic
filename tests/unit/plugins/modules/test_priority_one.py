from __future__ import annotations

from unittest.mock import Mock, call

import pytest

from ansible_collections.zupersero.elastic.plugins.module_utils.elasticsearch import (
    ElasticsearchResponse,
)
from ansible_collections.zupersero.elastic.plugins.module_utils.elasticsearch_services.administration import (
    ClusterSettingsService,
    IndexAliasService,
)
from ansible_collections.zupersero.elastic.plugins.module_utils.elasticsearch_services.security import (
    ApiKeyService,
    RoleMappingService,
)
from ansible_collections.zupersero.elastic.plugins.module_utils.elasticsearch_services.snapshot import (
    SnapshotLifecyclePolicyService,
    SnapshotRepositoryService,
)
from ansible_collections.zupersero.elastic.plugins.modules import (
    cluster_settings,
    index_alias,
    role_mapping,
    snapshot_repository,
)


class ExitResult(Exception):
    def __init__(self, result):
        self.result = result


class Failure(Exception):
    pass


class FakeModule:
    def __init__(self, params, check_mode=False):
        self.params = params
        self.check_mode = check_mode

    def exit_json(self, **result):
        raise ExitResult(result)

    def fail_json(self, **result):
        raise Failure(result["msg"])


def response(status=200, data=None):
    return ElasticsearchResponse(status=status, data=data, headers={})


def test_priority_one_services_quote_paths_and_shape_requests():
    transport = Mock()
    transport.request.side_effect = [
        response(
            data={"logs-1": {"aliases": {"current/logs": {"is_write_index": True}}}}
        ),
        response(),
        response(data={"persistent": {}, "transient": {}}),
        response(),
        response(data={"repo/a": {"type": "fs", "settings": {"location": "/tmp"}}}),
        response(),
        response(),
        response(
            data={
                "daily/a": {
                    "name": "<daily-{now/d}>",
                    "schedule": "0 0 1 * * ?",
                    "repository": "repo",
                }
            }
        ),
        response(),
        response(),
        response(
            data={
                "mapping/a": {
                    "enabled": True,
                    "roles": ["reader"],
                    "rules": {"field": {"username": "*"}},
                }
            }
        ),
        response(),
        response(),
        response(data={"api_keys": [{"id": "key/a", "name": "key"}]}),
        response(),
        response(),
        response(),
    ]
    alias = IndexAliasService(transport)
    assert alias.get("current/logs")[1] == {"logs-1": {"is_write_index": True}}
    alias.update("current/logs", {}, {"logs-1": {}})
    cluster = ClusterSettingsService(transport)
    cluster.get()
    cluster.update({"persistent": {"x": 1}})
    repository = SnapshotRepositoryService(transport)
    assert repository.get("repo/a")[1]["type"] == "fs"
    repository.put("repo/a", {"type": "fs"}, True)
    repository.delete("repo/a")
    slm = SnapshotLifecyclePolicyService(transport)
    assert slm.get("daily/a")[1]["snapshot_name"] == "<daily-{now/d}>"
    slm.put("daily/a", {"snapshot_name": "daily"})
    slm.delete("daily/a")
    mapping = RoleMappingService(transport)
    assert mapping.get("mapping/a")[1]["enabled"] is True
    mapping.put("mapping/a", {"enabled": True})
    mapping.delete("mapping/a")
    keys = ApiKeyService(transport)
    assert keys.get("key/a")[1]["id"] == "key/a"
    keys.create({"name": "key"})
    keys.update("key/a", {"metadata": {}})
    keys.invalidate("key/a")
    assert (
        call(
            "_snapshot/repo%2Fa",
            method="PUT",
            query={"verify": "true"},
            data={"type": "fs"},
        )
        in transport.request.call_args_list
    )
    assert (
        call("_slm/policy/daily%2Fa", method="PUT", data={"name": "daily"})
        in transport.request.call_args_list
    )


def test_alias_check_mode_predicts_without_mutation():
    client = Mock()
    client.index_alias.get.return_value = (response(404, {}), {})
    client.index_alias.path.return_value = "_alias/current"
    module = FakeModule(
        {"name": "current", "indices": {"logs": {}}, "state": "present"},
        check_mode=True,
    )
    with pytest.raises(ExitResult) as result:
        index_alias.run_module(module, client)
    assert result.value.result["changed"] is True
    client.index_alias.update.assert_not_called()


def test_api_key_name_lookup_returns_only_active_matches():
    transport = Mock()
    transport.request.return_value = response(
        data={
            "api_keys": [
                {"id": "active", "name": "deploy", "invalidated": False},
                {"id": "old", "name": "deploy", "invalidated": True},
                {"id": "other", "name": "other", "invalidated": False},
            ]
        }
    )
    service = ApiKeyService(transport)
    result, matches = service.find_by_name("deploy")
    assert result.status == 200
    assert matches == [{"id": "active", "name": "deploy", "invalidated": False}]
    transport.request.assert_called_once_with("_security/api_key", query={"name": "deploy"})


def test_cluster_settings_preserves_omitted_namespace_in_check_mode():
    client = Mock()
    client.cluster_settings.path = "_cluster/settings"
    client.cluster_settings.get.return_value = response(
        data={"persistent": {"old": "1"}, "transient": {"keep": "2"}}
    )
    module = FakeModule(
        {"persistent": {"new": 3}, "transient": None, "replace": False}, check_mode=True
    )
    with pytest.raises(ExitResult) as result:
        cluster_settings.run_module(module, client)
    assert result.value.result["cluster_settings"]["persistent"] == {
        "old": "1",
        "new": "3",
    }
    assert result.value.result["cluster_settings"]["transient"] == {"keep": "2"}


def test_named_resources_validate_and_predict_creation():
    client = Mock()
    client.snapshot_repository.get.return_value = (response(404, {}), None)
    client.snapshot_repository.path.return_value = "_snapshot/repo"
    module = FakeModule(
        {
            "name": "repo",
            "type": "fs",
            "settings": {"location": "/tmp"},
            "verify": True,
            "replace": False,
            "state": "present",
        },
        check_mode=True,
    )
    with pytest.raises(ExitResult) as result:
        snapshot_repository.run_module(module, client)
    assert result.value.result["changed"] is True
    client.snapshot_repository.put.assert_not_called()

    invalid = FakeModule(
        {
            "name": "mapping",
            "enabled": True,
            "roles": [],
            "role_templates": [],
            "rules": {},
            "metadata": None,
            "replace": False,
            "state": "present",
        }
    )
    client.role_mapping.get.return_value = (response(404, {}), None)
    client.role_mapping.path.return_value = "_security/role_mapping/mapping"
    with pytest.raises(Failure, match="roles or role_templates"):
        role_mapping.run_module(invalid, client)

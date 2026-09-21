from types import SimpleNamespace

from ansible_collections.zupersero.elastic.plugins.module_utils.elasticsearch_services.role import (
    RoleService,
)


def test_role_path_quotes_names():
    assert RoleService.path("data reader") == "_security/role/data%20reader"


def test_role_get_unwraps_named_entry():
    client = SimpleNamespace(
        request=lambda path: SimpleNamespace(
            status=200,
            data={
                "data_reader": {
                    "cluster": ["monitor"],
                    "indices": [],
                    "run_as": [],
                    "metadata": {},
                    "transient_metadata": {"enabled": True},
                }
            },
        )
    )
    response, role = RoleService(client).get("data_reader")
    assert response.status == 200
    assert role["name"] == "data_reader"
    assert role["cluster"] == ["monitor"]


def test_role_get_falls_back_to_first_entry_when_key_mismatched():
    client = SimpleNamespace(
        request=lambda path: SimpleNamespace(
            status=200,
            data={"some_other_key": {"cluster": []}},
        )
    )
    read_response, role = RoleService(client).get("data_reader")
    assert read_response.status == 200
    assert role["name"] == "data_reader"


def test_role_payload_preserves_omitted_fields():
    current = {
        "name": "data_reader",
        "cluster": ["monitor"],
        "indices": [{"names": ["logs-*"], "privileges": ["read"]}],
        "applications": [],
        "run_as": ["elastic"],
        "metadata": {"owner": "qa"},
        "transient_metadata": {"enabled": True},
    }
    desired = {"cluster": ["monitor", "manage_own_api_key"]}
    payload = RoleService.payload(current, desired)
    assert payload["cluster"] == ["monitor", "manage_own_api_key"]
    assert payload["run_as"] == ["elastic"]
    assert payload["metadata"] == {"owner": "qa"}


def test_role_payload_defaults_omitted_fields_on_creation():
    payload = RoleService.payload(None, {"cluster": ["monitor"]})
    assert payload["cluster"] == ["monitor"]
    assert payload["indices"] == []
    assert payload["applications"] == []
    assert payload["run_as"] == []
    assert payload["metadata"] == {}
    assert payload["transient_metadata"] == {"enabled": True}


def test_role_compare_ignores_list_ordering():
    current = {
        "name": "data_reader",
        "cluster": ["monitor", "manage_own_api_key"],
        "indices": [
            {"names": ["logs-*"], "privileges": ["read", "view_index_metadata"]}
        ],
        "applications": [],
        "run_as": ["elastic"],
        "metadata": {},
        "transient_metadata": {"enabled": True},
    }
    desired = {
        "cluster": ["manage_own_api_key", "monitor"],
        "indices": [
            {"names": ["logs-*"], "privileges": ["view_index_metadata", "read"]}
        ],
    }
    changed, diff = RoleService.compare(current, desired)
    assert changed is False
    assert diff["before"] == diff["after"]


def test_role_compare_detects_real_changes():
    current = {
        "name": "data_reader",
        "cluster": ["monitor"],
        "indices": [],
        "applications": [],
        "run_as": [],
        "metadata": {},
        "transient_metadata": {"enabled": True},
    }
    changed, diff = RoleService.compare(current, {"cluster": ["monitor", "manage_own_api_key"]})
    assert changed is True
    assert diff["after"]["cluster"] == ["manage_own_api_key", "monitor"]


def test_role_payload_normalizes_legacy_index_alias_and_bool_coercion():
    payload = RoleService.payload(
        None,
        {
            "indices": [
                {"index": ["logs-*"], "privileges": ["read"], "allow_restricted_indices": 1}
            ]
        },
    )
    entry = payload["indices"][0]
    assert entry["names"] == ["logs-*"]
    assert "index" not in entry
    assert entry["allow_restricted_indices"] is True

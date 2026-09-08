from ansible_collections.zupersero.elastic.plugins.modules import user_role


def test_normalize_role_sorts_unordered_privileges_and_preserves_security_fields():
    normalized = user_role.normalize_role_data(
        {
            "name": "reader",
            "cluster": ["monitor", "manage_ilm"],
            "indices": [{"names": ["b-*", "a-*"], "privileges": ["view_index_metadata", "read"]}],
            "run_as": ["z", "a"],
            "metadata": {"owner": "ops"},
        }
    )
    assert normalized["cluster"] == ["manage_ilm", "monitor"]
    assert normalized["indices"][0]["names"] == ["a-*", "b-*"]
    assert normalized["indices"][0]["privileges"] == ["read", "view_index_metadata"]
    assert normalized["run_as"] == ["a", "z"]


def test_normalize_role_accepts_api_camel_case_fields():
    normalized = user_role.normalize_role_data(
        {"name": "reader", "runAs": ["analyst"], "transientMetadata": {"enabled": True}}
    )
    assert normalized["run_as"] == ["analyst"]
    assert normalized["transient_metadata"] == {"enabled": True}

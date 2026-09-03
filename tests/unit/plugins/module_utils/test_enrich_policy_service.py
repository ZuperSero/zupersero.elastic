from types import SimpleNamespace

from ansible_collections.zupersero.elastic.plugins.module_utils.elasticsearch_services.enrich import (
    EnrichPolicyService,
    validate_enrich_policy,
)


def test_policy_wire_round_trip():
    policy = {
        "name": "company lookup",
        "policy_type": "match",
        "source_indices": ["companies"],
        "match_field": "id",
        "enrich_fields": ["name"],
    }
    wire = EnrichPolicyService._to_wire(policy)
    assert wire == {
        "match": {
            "indices": ["companies"],
            "match_field": "id",
            "enrich_fields": ["name"],
        }
    }
    assert EnrichPolicyService._from_wire("company lookup", wire) == policy


def test_policy_payload_preserves_omitted_fields():
    current = {
        "name": "company",
        "policy_type": "match",
        "source_indices": ["companies"],
        "match_field": "id",
        "enrich_fields": ["name", "address"],
    }
    desired = {"name": "company", "enrich_fields": ["name"]}
    assert EnrichPolicyService.payload(current, desired)["match"] == {
        "indices": ["companies"],
        "match_field": "id",
        "enrich_fields": ["name"],
    }


def test_policy_path_quotes_names():
    assert EnrichPolicyService.path("company lookup") == "_enrich/policy/company%20lookup"
    assert EnrichPolicyService.execute_path("company/lookup") == "_enrich/policy/company%2Flookup/_execute"


def test_policy_validation_rejects_empty_fields():
    try:
        validate_enrich_policy("match", [], "id", ["name"])
    except ValueError as exc:
        assert "source_indices" in str(exc)
    else:
        raise AssertionError("expected validation failure")


def test_get_handles_empty_and_config_wrapped_responses():
    client = SimpleNamespace(
        request=lambda path: SimpleNamespace(
            status=200,
            data={
                "policies": [
                    {
                        "config": {
                            "match": {
                                "name": "company",
                                "indices": ["companies"],
                                "match_field": "id",
                                "enrich_fields": ["name"],
                            }
                        }
                    }
                ],
            },
        )
    )
    response, policy = EnrichPolicyService(client).get("company")
    assert response.status == 200
    assert policy["name"] == "company"
    assert policy["source_indices"] == ["companies"]
